from django.conf import settings
from django.db import models

from config.models import TimeStampedModel


class SensorReading(TimeStampedModel):
    class SourceTypes(models.TextChoices):
        HTTP = "HTTP", "HTTP 接口"
        MQTT = "MQTT", "MQTT"
        SIMULATOR = "SIMULATOR", "模拟器"
        IMPORT = "IMPORT", "导入"

    orchard = models.ForeignKey("orchards.Orchard", on_delete=models.CASCADE, related_name="sensor_readings")
    plot = models.ForeignKey("orchards.Plot", null=True, blank=True, on_delete=models.SET_NULL, related_name="sensor_readings")
    device = models.ForeignKey("orchards.Device", on_delete=models.CASCADE, related_name="sensor_readings")
    temperature = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    humidity = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    soil_moisture = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    light = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pest_alarm = models.BooleanField(default=False)
    device_status = models.CharField(max_length=20, default="ONLINE")
    collection_time = models.DateTimeField(db_index=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_valid = models.BooleanField(default=True, db_index=True)
    is_abnormal = models.BooleanField(default=False, db_index=True)
    abnormal_reason = models.TextField(blank=True)
    source_type = models.CharField(max_length=16, choices=SourceTypes.choices, default=SourceTypes.HTTP, db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    payload_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["-collection_time"]
        indexes = [
            models.Index(fields=["orchard", "collection_time"]),
            models.Index(fields=["device", "collection_time"]),
            models.Index(fields=["is_abnormal", "collection_time"]),
        ]

    def __str__(self):
        return f"{self.device.device_code} @ {self.collection_time:%Y-%m-%d %H:%M:%S}"

