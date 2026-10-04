from django import forms

from apps.accounts.forms import StyledFormMixin
from .models import DataSource, Device, Gateway, Orchard, Plot


class OrchardForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Orchard
        fields = ["name", "code", "location", "contact_name", "contact_phone", "description", "status"]


class PlotForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Plot
        fields = ["orchard", "name", "code", "location_description", "latitude", "longitude", "area", "status"]


class GatewayForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Gateway
        fields = ["orchard", "name", "gateway_code", "protocol", "ip_address", "status", "description"]


class DeviceForm(StyledFormMixin, forms.ModelForm):
    demo_token = forms.CharField(required=False, widget=forms.PasswordInput, help_text="留空则保持现有令牌；令牌只保存哈希。")

    class Meta:
        model = Device
        fields = ["device_code", "device_name", "device_type", "orchard", "plot", "gateway", "status", "manufacturer", "description", "demo_token"]

    def clean(self):
        cleaned = super().clean()
        orchard = cleaned.get("orchard")
        plot = cleaned.get("plot")
        gateway = cleaned.get("gateway")
        if orchard and plot and plot.orchard_id != orchard.pk:
            self.add_error("plot", "地块必须属于所选果园")
        if orchard and gateway and gateway.orchard_id != orchard.pk:
            self.add_error("gateway", "网关必须属于所选果园")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.cleaned_data.get("demo_token"):
            obj.set_token(self.cleaned_data["demo_token"])
        if commit:
            obj.save()
        return obj


class DataSourceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DataSource
        fields = ["name", "orchard", "source_type", "endpoint", "status", "config", "description"]
