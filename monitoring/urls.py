from django.urls import path
from .views import TemperatureReadingCreateView, dashboard_view

urlpatterns = [
    path('api/readings/', TemperatureReadingCreateView.as_view(), name='reading-create'),
    path('dashboard/', dashboard_view, name='dashboard'),
]