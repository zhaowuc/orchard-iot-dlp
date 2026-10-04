from django.db import models

from config.models import TimeStampedModel


class SystemConfig(TimeStampedModel):
    class ValueTypes(models.TextChoices):
        INTEGER = "INTEGER", "整数"
        FLOAT = "FLOAT", "小数"
        BOOLEAN = "BOOLEAN", "布尔值"
        STRING = "STRING", "字符串"

    key = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=500)
    value_type = models.CharField(max_length=16, choices=ValueTypes.choices, default=ValueTypes.INTEGER)
    description = models.TextField(blank=True)
    editable = models.BooleanField(default=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.name

    def typed_value(self):
        if self.value_type == self.ValueTypes.INTEGER:
            return int(self.value)
        if self.value_type == self.ValueTypes.FLOAT:
            return float(self.value)
        if self.value_type == self.ValueTypes.BOOLEAN:
            return self.value.lower() in {"1", "true", "yes", "on"}
        return self.value

    @classmethod
    def get_value(cls, key, default=None):
        try:
            return cls.objects.get(key=key).typed_value()
        except (cls.DoesNotExist, TypeError, ValueError):
            return default
