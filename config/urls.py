from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("monitoring/", include("monitoring.urls")),   # ← adjust to your app name
]