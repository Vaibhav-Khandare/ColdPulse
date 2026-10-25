from django.urls import path
from .views import TemperatureReadingCreateView, dashboard_view, live_dashboard_api

urlpatterns = [
    path('api/readings/', TemperatureReadingCreateView.as_view(), name='reading-create'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('api/live/', live_dashboard_api, name='api-live'),
]