import logging
import json

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings

from rest_framework import generics
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import TemperatureReading
from .serializers import TemperatureReadingSerializer


logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  ROOM / PROFILE CONFIG
# ═══════════════════════════════════════════════════════════
PROFILES = {
    "pharma": {"room_id": "PHARMA_01", "unit_name": "PHARMA_01",
               "min_c": 2.0, "max_c": 8.0, "alert_c": 6.0},
    "food":   {"room_id": "FOOD_01",   "unit_name": "FOOD_01",
               "min_c": 0.0, "max_c": 5.0, "alert_c": 4.0},
}

# Generic display thresholds (used when reading.risk_level is missing)
PHARMA_MIN_C = 2.0
PHARMA_MAX_C = 8.0


def _limits_for(room_id: str):
    for cfg in PROFILES.values():
        if cfg["room_id"] == room_id:
            return cfg["min_c"], cfg["max_c"], cfg["alert_c"]
    return PHARMA_MIN_C, PHARMA_MAX_C, 6.0


def _risk_from_reading(reading):
    """Prefer stored risk_level; fall back to a range check."""
    if reading is None or reading.internal_temp_c is None:
        return "SAFE"
    if getattr(reading, "risk_level", None):
        return str(reading.risk_level).upper().replace(" ", "_")   # SAFE / MEDIUM_RISK / HIGH_RISK
    t = reading.internal_temp_c
    lo, hi, _ = _limits_for(reading.room_id)
    if lo <= t <= hi:
        return "SAFE"
    if (lo - t <= 1.0) or (t - hi <= 1.0):
        return "MEDIUM"
    return "HIGH"


def _payload_from_reading(reading, default_room="ROOM_01"):
    """Build the JSON payload the frontend consumes."""
    if reading is None:
        return {
            "unit_name":            default_room,
            "internal_temp_c":      None,
            "ambient_temp_c":       None,
            "ambient_humidity_pct": None,
            "predicted_temp_30m":   None,
            "risk_level":           "SAFE",
            "power_status":         True,
            "door_open":            False,
            "compressor_status":    True,
            "timestamp":            None,
            "status":               "waiting",
        }
    return {
        "unit_name":            getattr(reading, "room_id", default_room) or default_room,
        "internal_temp_c":      reading.internal_temp_c,
        "ambient_temp_c":       reading.ambient_temp_c,
        "ambient_humidity_pct": reading.ambient_humidity_pct,
        "predicted_temp_30m":   reading.predicted_temp_30m,
        "risk_level":           _risk_from_reading(reading),
        "power_status":         reading.power_status,
        "door_open":            reading.door_open,
        "compressor_status":    reading.compressor_status,
        "timestamp":            reading.timestamp.isoformat() if reading.timestamp else None,
        "status":               "ok",
    }


# ═══════════════════════════════════════════════════════════
#  INGEST — POST /monitoring/api/readings/
#  Both simulators POST here. Room_id in payload decides which profile.
# ═══════════════════════════════════════════════════════════
class TemperatureReadingCreateView(generics.CreateAPIView):
    queryset = TemperatureReading.objects.all()
    serializer_class = TemperatureReadingSerializer

    def perform_create(self, serializer):
        instance = serializer.save()

        # ─── email alert on threshold crossing (per-room thresholds) ───
        try:
            self._maybe_send_alert(instance)
        except Exception as e:
            logger.error(f"Alert pipeline error: {e}")

        # ─── WebSocket broadcast (unchanged behavior) ───
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "dashboard",
                {
                    "type": "send_reading",
                    "data": {
                        "room_id":             instance.room_id,
                        "internal_temp_c":     instance.internal_temp_c,
                        "ambient_temp_c":      instance.ambient_temp_c,
                        "ambient_humidity_pct":instance.ambient_humidity_pct,
                        "door_open":           instance.door_open,
                        "power_status":        instance.power_status,
                        "compressor_status":   instance.compressor_status,
                        "predicted_temp_30m":  instance.predicted_temp_30m,
                        "risk_level":          instance.risk_level,
                        "timestamp":           instance.timestamp.isoformat(),
                    },
                },
            )
        except Exception as e:
            logger.error(f"WebSocket broadcast error: {e}")

    def _maybe_send_alert(self, instance):
        """Send one email per crossing, scoped to the same room_id."""
        _, _, alert_c = _limits_for(instance.room_id)

        prev_reading = (
            TemperatureReading.objects
            .filter(room_id=instance.room_id)
            .exclude(pk=instance.pk)
            .order_by("-timestamp")
            .first()
        )

        curr_actual = instance.internal_temp_c or 0.0
        curr_pred   = instance.predicted_temp_30m or 0.0

        prev_actual = prev_reading.internal_temp_c if prev_reading else 0.0
        prev_pred   = (prev_reading.predicted_temp_30m or 0.0) if prev_reading else 0.0

        actual_crossed = (curr_actual > alert_c) and (prev_reading is None or prev_actual <= alert_c)
        pred_crossed   = (curr_pred > alert_c)   and (prev_pred <= alert_c)

        if (actual_crossed or pred_crossed) and not instance.alert_sent:
            try:
                send_mail(
                    subject=f"ColdPulse Alert — {instance.room_id}",
                    message=(
                        f"Cold storage temperature is increasing.\n\n"
                        f"Room: {instance.room_id}\n"
                        f"Current: {instance.internal_temp_c} °C\n"
                        f"Predicted 30m: {instance.predicted_temp_30m} °C\n"
                        f"Threshold: {alert_c} °C\n"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=["rutujasayare@gmail.com"],
                    fail_silently=False,
                )
                instance.alert_sent = True
                instance.save(update_fields=["alert_sent"])
                logger.info(f"Email alert sent for {instance.room_id}.")
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")


# ═══════════════════════════════════════════════════════════
#  DASHBOARD — passes BOTH rooms' latest readings as `initial_*`
# ═══════════════════════════════════════════════════════════
def dashboard_view(request):
    """Renders the ColdPulse dashboard, seeded with both rooms' latest readings."""
    def snap(room_id):
        r = TemperatureReading.objects.filter(room_id=room_id).order_by("-timestamp").first()
        return _payload_from_reading(r, default_room=room_id)

    return render(request, "monitoring/dashboard.html", {
        "initial_pharma": snap(PROFILES["pharma"]["room_id"]),
        "initial_food":   snap(PROFILES["food"]["room_id"]),
        # keep `initial` too, in case any old template still references it
        "initial": snap(PROFILES["pharma"]["room_id"]),
    })


dashboard = dashboard_view   # backwards-compat alias


# ═══════════════════════════════════════════════════════════
#  LIVE POLLING — ?profile=pharma|food picks the right simulator
# ═══════════════════════════════════════════════════════════
@require_GET
def live_dashboard_api(request):
    """Polling JSON endpoint consumed by dashboard JS every 5 s."""
    profile = (request.GET.get("profile") or "pharma").lower()
    cfg = PROFILES.get(profile, PROFILES["pharma"])

    latest = (
        TemperatureReading.objects
        .filter(room_id=cfg["room_id"])
        .order_by("-timestamp")
        .first()
    )
    return JsonResponse(_payload_from_reading(latest, default_room=cfg["room_id"]))