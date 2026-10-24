from django.urls import path
from django.http import HttpResponse

app_name = "prediction"


def index(request):
    return HttpResponse("ColdPulse Prediction is running.")


urlpatterns = [
    path("", index, name="index"),
]