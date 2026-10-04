from django.conf import settings
from django.db import models

from config.models import TimeStampedModel
from apps.sensitive.models import SensitivityLevel


class MaskingRule(TimeStampedModel):
    class MaskingTypes(models.TextChoices):
        MASK = "MASK", "掩码"
        GENERALIZE = "GENERALIZE", "泛化"
        HASH = "HASH", "哈希摘要"
        TOKEN = "TOKEN", "Token 替换"
        RANDOM = "RANDOM", "随机替换"

    class Scenes(models.TextChoices):
        WEB_VIEW = "WEB_VIEW", "网页查看"
        EXPORT = "EXPORT", "导出"
        API = "API", "接口"
        ALL = "ALL", "全部"

    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=50, db_index=True)
    masking_type = models.CharField(max_length=20, choices=MaskingTypes.choices)
    sensitivity_level = models.CharField(max_length=16, choices=SensitivityLevel.choices)
    role = models.ForeignKey("accounts.Role", null=True, blank=True, on_delete=models.CASCADE, related_name="masking_rules")
    scene = models.CharField(max_length=16, choices=Scenes.choices, default=Scenes.ALL)
    config = models.JSONField(default=dict, blank=True)
    priority = models.PositiveIntegerField(default=100)
    enabled = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["priority", "id"]

    def __str__(self):
        return self.name


class MaskingRecord(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="masking_records")
    rule = models.ForeignKey(MaskingRule, null=True, blank=True, on_delete=models.SET_NULL, related_name="records")
    field_type = models.CharField(max_length=50, db_index=True)
    scene = models.CharField(max_length=16, choices=MaskingRule.Scenes.choices)
    source_type = models.CharField(max_length=80, blank=True)
    source_object_id = models.CharField(max_length=80, blank=True)
    original_fingerprint = models.CharField(max_length=64)
    result_preview = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

