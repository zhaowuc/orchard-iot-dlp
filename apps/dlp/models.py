import uuid

from django.conf import settings
from django.db import models

from config.models import TimeStampedModel
from apps.sensitive.models import SensitivityLevel


class AccessPolicy(TimeStampedModel):
    class Operations(models.TextChoices):
        VIEW = "VIEW", "查看"
        RAW_VIEW = "RAW_VIEW", "查看原文"
        CREATE = "CREATE", "新增"
        UPDATE = "UPDATE", "修改"
        DELETE = "DELETE", "删除"
        EXPORT = "EXPORT", "导出"
        MANAGE_SECURITY = "MANAGE_SECURITY", "安全管理"

    class Effects(models.TextChoices):
        ALLOW = "ALLOW", "允许"
        DENY = "DENY", "拒绝"

    name = models.CharField(max_length=100)
    role = models.ForeignKey("accounts.Role", on_delete=models.CASCADE, related_name="access_policies")
    orchard = models.ForeignKey("orchards.Orchard", null=True, blank=True, on_delete=models.CASCADE, related_name="access_policies")
    plot = models.ForeignKey("orchards.Plot", null=True, blank=True, on_delete=models.CASCADE, related_name="access_policies")
    device = models.ForeignKey("orchards.Device", null=True, blank=True, on_delete=models.CASCADE, related_name="access_policies")
    sensitivity_level = models.CharField(max_length=16, choices=SensitivityLevel.choices, blank=True)
    operation = models.CharField(max_length=24, choices=Operations.choices)
    effect = models.CharField(max_length=8, choices=Effects.choices, default=Effects.ALLOW)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=100)
    enabled = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["priority", "id"]


class QueryMonitor(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="query_monitors")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=500)
    orchard = models.ForeignKey("orchards.Orchard", null=True, blank=True, on_delete=models.SET_NULL)
    plot = models.ForeignKey("orchards.Plot", null=True, blank=True, on_delete=models.SET_NULL)
    record_count = models.PositiveIntegerField(default=0)
    sensitive_count = models.PositiveIntegerField(default=0)
    blocked = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]


class ExportRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "待审批"
        APPROVED = "APPROVED", "已批准"
        REJECTED = "REJECTED", "已拒绝"
        COMPLETED = "COMPLETED", "已完成"
        EXPIRED = "EXPIRED", "已过期"

    export_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="export_requests")
    orchard = models.ForeignKey("orchards.Orchard", null=True, blank=True, on_delete=models.SET_NULL)
    plot = models.ForeignKey("orchards.Plot", null=True, blank=True, on_delete=models.SET_NULL)
    device = models.ForeignKey("orchards.Device", null=True, blank=True, on_delete=models.SET_NULL)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    sensitivity_level = models.CharField(max_length=16, choices=SensitivityLevel.choices, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    estimated_count = models.PositiveIntegerField(default=0)
    sensitive_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_ip = models.GenericIPAddressField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_export_requests")
    decision_comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ExportRecord(TimeStampedModel):
    export_id = models.UUIDField(unique=True, db_index=True)
    request = models.OneToOneField(ExportRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name="record")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="export_records")
    username_snapshot = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    record_count = models.PositiveIntegerField(default=0)
    sensitive_count = models.PositiveIntegerField(default=0)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_export_records")
    exported_at = models.DateTimeField(null=True, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]

