from rest_framework import serializers
from .models import TemperatureReading


class TemperatureReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemperatureReading
        fields = "__all__"