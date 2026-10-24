from django.shortcuts import render
from rest_framework import generics
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import TemperatureReading
from .serializers import TemperatureReadingSerializer


class TemperatureReadingCreateView(generics.CreateAPIView):
    queryset = TemperatureReading.objects.all()
    serializer_class = TemperatureReadingSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "dashboard",
            {
                "type": "send_reading",
                "data": {
                    "room_id": instance.room_id,
                    "internal_temp_c": instance.internal_temp_c,
                    "ambient_temp_c": instance.ambient_temp_c,
                    "ambient_humidity_pct": instance.ambient_humidity_pct,
                    "door_open": instance.door_open,
                    "power_status": instance.power_status,
                    "compressor_status": instance.compressor_status,
                    "predicted_temp_30m": instance.predicted_temp_30m,
                    "risk_level": instance.risk_level,
                    "timestamp": instance.timestamp.isoformat(),
                },
            },
        )


def dashboard_view(request):
    return render(request, "monitoring/dashboard.html")