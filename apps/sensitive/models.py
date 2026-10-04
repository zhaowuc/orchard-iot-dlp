from django.conf import settings
from django.db import models

from config.models import TimeStampedModel


class SensitivityLevel(models.TextChoices):
    PUBLIC = "PUBLIC", "公开"
    INTERNAL = "INTERNAL", "内部"
    SENSITIVE = "SENSITIVE", "敏感"
    IMPORTANT = "IMPORTANT", "重要"


class SensitiveFieldDefinition(TimeStampedModel):
    name = models.CharField(max_length=100)
    field_name = models.CharField(max_length=100, unique=True)
    field_type = models.CharField(max_length=50, db_index=True)
    business_tag = models.CharField(max_length=80, blank=True)
    sensitivity_level = models.CharField(max_length=16, choices=SensitivityLevel.choices, default=SensitivityLevel.SENSITIVE, db_index=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return f"{self.name} / {self.get_sensitivity_level_display()}"


class SensitiveRule(TimeStampedModel):
    class MatchTypes(models.TextChoices):
        FIELD_NAME = "FIELD_NAME", "字段名称"
        REGEX = "REGEX", "正则表达式"
        BUSINESS_TAG = "BUSINESS_TAG", "业务标签"

    name = models.CharField(max_length=100)
    match_type = models.CharField(max_length=20, choices=MatchTypes.choices)
    pattern = models.CharField(max_length=500)
    field_type = models.CharField(max_length=50)
    sensitivity_level = models.CharField(max_length=16, choices=SensitivityLevel.choices)
    priority = models.PositiveIntegerField(default=100)
    enabled = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "id"]

    def __str__(self):
        return self.name


class SensitiveDetectionRecord(TimeStampedModel):
    source_type = models.CharField(max_length=80, db_index=True)
    source_object_id = models.CharField(max_length=80, blank=True)
    field_name = models.CharField(max_length=100, db_index=True)
    field_type = models.CharField(max_length=50)
    value_fingerprint = models.CharField(max_length=64, blank=True)
    is_sensitive = models.BooleanField(default=True, db_index=True)
    sensitivity_level = models.CharField(max_length=16, choices=SensitivityLevel.choices, db_index=True)
    matched_rule = models.ForeignKey(SensitiveRule, null=True, blank=True, on_delete=models.SET_NULL, related_name="detection_records")
    business_tag = models.CharField(max_length=80, blank=True)
    manually_adjusted = models.BooleanField(default=False)
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="adjusted_detections")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["sensitivity_level", "created_at"])]

