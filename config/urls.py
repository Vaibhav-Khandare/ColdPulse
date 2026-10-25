from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("admin/", admin.site.urls),
    path("monitoring/", include("monitoring.urls")),
    path("prediction/", include("prediction.urls")),
]