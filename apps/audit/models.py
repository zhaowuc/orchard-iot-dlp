from django.conf import settings
from django.db import models

from config.models import TimeStampedModel
from apps.sensitive.models import SensitivityLevel


class AuditLog(TimeStampedModel):
    class Results(models.TextChoices):
        SUCCESS = "SUCCESS", "成功"
        FAILURE = "FAILURE", "失败"
        BLOCKED = "BLOCKED", "已阻止"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs")
    username_snapshot = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    http_method = models.CharField(max_length=12, blank=True)
    action = models.CharField(max_length=80, db_index=True)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    orchard = models.ForeignKey("orchards.Orchard", null=True, blank=True, on_delete=models.SET_NULL)
    result = models.CharField(max_length=12, choices=Results.choices, default=Results.SUCCESS, db_index=True)
    record_count = models.PositiveIntegerField(default=0)
    sensitivity_level = models.CharField(max_length=16, choices=SensitivityLevel.choices, blank=True)
    risk_score = models.PositiveSmallIntegerField(default=0)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "created_at"]), models.Index(fields=["user", "created_at"])]


class RiskEvent(TimeStampedModel):
    class Levels(models.TextChoices):
        LOW = "LOW", "低风险"
        MEDIUM = "MEDIUM", "中风险"
        HIGH = "HIGH", "高风险"
        CRITICAL = "CRITICAL", "严重风险"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="risk_events")
    event_type = models.CharField(max_length=80, db_index=True)
    score = models.PositiveSmallIntegerField(db_index=True)
    risk_level = models.CharField(max_length=16, choices=Levels.choices, db_index=True)
    reason = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    related_audit_log = models.ForeignKey(AuditLog, null=True, blank=True, on_delete=models.SET_NULL, related_name="risk_events")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["risk_level", "created_at"])]


class SecurityAlert(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "待处理"
        PROCESSING = "PROCESSING", "处理中"
        RESOLVED = "RESOLVED", "已解决"
        IGNORED = "IGNORED", "已忽略"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="security_alerts")
    event = models.OneToOneField(RiskEvent, on_delete=models.CASCADE, related_name="alert")
    risk_level = models.CharField(max_length=16, choices=RiskEvent.Levels.choices, db_index=True)
    score = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    handler = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="handled_alerts")
    handling_comment = models.TextField(blank=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

