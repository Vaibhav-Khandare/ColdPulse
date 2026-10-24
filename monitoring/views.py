from django.http import HttpResponse


def index(request):
    return HttpResponse("ColdPulse Monitoring is running.")