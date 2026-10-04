from django.contrib.auth.hashers import check_password, make_password
from django.db import models

from config.models import TimeStampedModel


class StatusChoices(models.TextChoices):
    ACTIVE = "ACTIVE", "启用"
    INACTIVE = "INACTIVE", "停用"


class Orchard(TimeStampedModel):
    name = models.CharField("果园名称", max_length=100)
    code = models.CharField("果园编码", max_length=40, unique=True)
    location = models.CharField("位置", max_length=255)
    contact_name = models.CharField("联系人", max_length=60)
    contact_phone = models.CharField("联系电话", max_length=20)
    description = models.TextField("说明", blank=True)
    status = models.CharField(max_length=16, choices=StatusChoices.choices, default=StatusChoices.ACTIVE, db_index=True)

    class Meta:
        ordering = ["code"]
        indexes = [models.Index(fields=["status", "name"])]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Plot(TimeStampedModel):
    orchard = models.ForeignKey(Orchard, on_delete=models.CASCADE, related_name="plots")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=40)
    location_description = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    area = models.DecimalField("面积/亩", max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=16, choices=StatusChoices.choices, default=StatusChoices.ACTIVE, db_index=True)

    class Meta:
        ordering = ["orchard", "code"]
        constraints = [models.UniqueConstraint(fields=["orchard", "code"], name="unique_plot_code_per_orchard")]

    def __str__(self):
        return f"{self.orchard.name} / {self.name}"


class Gateway(TimeStampedModel):
    orchard = models.ForeignKey(Orchard, on_delete=models.CASCADE, related_name="gateways")
    name = models.CharField(max_length=100)
    gateway_code = models.CharField(max_length=60, unique=True)
    protocol = models.CharField(max_length=20, default="MQTT")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=StatusChoices.choices, default=StatusChoices.ACTIVE, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.gateway_code})"


class Device(TimeStampedModel):
    class Types(models.TextChoices):
        TEMPERATURE = "temperature", "温度"
        HUMIDITY = "humidity", "湿度"
        SOIL = "soil", "土壤墒情"
        LIGHT = "light", "光照"
        PEST = "pest", "虫情"
        GATEWAY = "gateway", "网关"
        OTHER = "other", "其他"

    class DeviceStatus(models.TextChoices):
        ONLINE = "ONLINE", "在线"
        OFFLINE = "OFFLINE", "离线"
        ABNORMAL = "ABNORMAL", "异常"
        DISABLED = "DISABLED", "禁用"

    device_code = models.CharField(max_length=80, unique=True)
    device_name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=20, choices=Types.choices, default=Types.OTHER)
    orchard = models.ForeignKey(Orchard, on_delete=models.CASCADE, related_name="devices")
    plot = models.ForeignKey(Plot, null=True, blank=True, on_delete=models.SET_NULL, related_name="devices")
    gateway = models.ForeignKey(Gateway, null=True, blank=True, on_delete=models.SET_NULL, related_name="devices")
    status = models.CharField(max_length=16, choices=DeviceStatus.choices, default=DeviceStatus.OFFLINE, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    token_hash = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["orchard", "device_code"]
        indexes = [models.Index(fields=["orchard", "status"]), models.Index(fields=["plot", "device_type"])]

    def __str__(self):
        return f"{self.device_name} ({self.device_code})"

    def set_token(self, raw_token):
        self.token_hash = make_password(raw_token)

    def check_token(self, raw_token):
        return bool(self.token_hash and raw_token and check_password(raw_token, self.token_hash))


class DataSource(TimeStampedModel):
    class SourceTypes(models.TextChoices):
        HTTP = "HTTP", "HTTP"
        MQTT = "MQTT", "MQTT"
        SIMULATOR = "SIMULATOR", "模拟器"

    name = models.CharField(max_length=100)
    orchard = models.ForeignKey(Orchard, on_delete=models.CASCADE, related_name="data_sources")
    source_type = models.CharField(max_length=16, choices=SourceTypes.choices)
    endpoint = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=StatusChoices.choices, default=StatusChoices.ACTIVE, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

