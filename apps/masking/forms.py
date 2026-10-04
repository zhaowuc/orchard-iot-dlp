from django import forms

from apps.accounts.forms import StyledFormMixin
from .models import MaskingRule


class MaskingRuleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MaskingRule
        fields = ["name", "field_type", "masking_type", "sensitivity_level", "role", "scene", "config", "priority", "enabled"]


class MaskingPreviewForm(StyledFormMixin, forms.Form):
    field_type = forms.ChoiceField(choices=(("phone", "手机号"), ("device_code", "设备编号"), ("username", "用户账号"), ("coordinate", "坐标"), ("collection_time", "采集时间"), ("location", "位置")))
    masking_type = forms.ChoiceField(choices=MaskingRule.MaskingTypes.choices)
    test_value = forms.CharField(max_length=255)

