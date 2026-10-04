from django import forms

from apps.accounts.forms import StyledFormMixin
from .models import SensitiveFieldDefinition, SensitiveRule


class FieldDefinitionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SensitiveFieldDefinition
        fields = ["name", "field_name", "field_type", "business_tag", "sensitivity_level", "description", "enabled"]


class SensitiveRuleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SensitiveRule
        fields = ["name", "match_type", "pattern", "field_type", "sensitivity_level", "priority", "enabled", "description"]

