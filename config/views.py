from django.shortcuts import render
from monitoring.models import TemperatureReading


def landing(request):
    """Root landing page — entry point with links to Monitoring and Prediction."""
    latest = TemperatureReading.objects.order_by("-timestamp").first()
    total = TemperatureReading.objects.count()
    context = {
        "latest": latest,
        "total_readings": total,
    }
    return render(request, "landing.html", context)