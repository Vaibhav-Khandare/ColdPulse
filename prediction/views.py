from django.shortcuts import render
from monitoring.models import TemperatureReading


def prediction_home(request):
    """Prediction overview — shows recent model outputs."""
    recent = TemperatureReading.objects.order_by("-timestamp")[:10]
    total = TemperatureReading.objects.count()
    high_risk = TemperatureReading.objects.filter(risk_level="HIGH").count()
    return render(request, "prediction/index.html", {
        "recent": recent,
        "total": total,
        "high_risk": high_risk,
    })