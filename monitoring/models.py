from django.db import models

class TemperatureReading(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    room_id = models.CharField(max_length=50, default="ROOM_01")
    internal_temp_c = models.FloatField(null=True, blank=True)
    ambient_temp_c = models.FloatField()
    ambient_humidity_pct = models.FloatField(null=True, blank=True)
    door_open = models.BooleanField(default=False)
    power_status = models.BooleanField(default=True)
    compressor_status = models.BooleanField(default=True)
    predicted_temp_30m = models.FloatField(null=True, blank=True)
    risk_level = models.CharField(max_length=20, default="SAFE")
    alert_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.room_id} at {self.internal_temp_c}°C ({self.timestamp.strftime('%H:%M:%S')})"