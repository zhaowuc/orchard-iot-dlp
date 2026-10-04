from django import forms

from apps.accounts.forms import StyledFormMixin
from .models import SystemConfig


class SystemConfigForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SystemConfig
        fields = ["name", "value", "value_type", "description", "editable"]

    def clean(self):
        cleaned = super().clean()
        value = cleaned.get("value", "")
        value_type = cleaned.get("value_type")
        try:
            if value_type == SystemConfig.ValueTypes.INTEGER:
                parsed = int(value)
                if parsed < 0:
                    raise ValueError
            elif value_type == SystemConfig.ValueTypes.FLOAT:
                parsed = float(value)
                if not (-1e12 < parsed < 1e12):
                    raise ValueError
            elif value_type == SystemConfig.ValueTypes.BOOLEAN and str(value).lower() not in {"0", "1", "true", "false", "yes", "no", "on", "off"}:
                raise ValueError
        except (TypeError, ValueError):
            self.add_error("value", "参数值与所选类型不匹配，数值参数不得为负数")
        return cleaned
