from django import forms

from apps.accounts.forms import StyledFormMixin
from .models import SecurityAlert


class AlertHandlingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SecurityAlert
        fields = ["status", "handling_comment"]
        widgets = {"handling_comment": forms.Textarea(attrs={"rows": 5})}

