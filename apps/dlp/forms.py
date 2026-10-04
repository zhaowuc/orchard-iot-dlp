from django import forms

from apps.accounts.forms import StyledFormMixin
from apps.orchards.models import Device, Orchard, Plot
from apps.sensitive.models import SensitivityLevel
from .models import AccessPolicy


class AccessPolicyForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AccessPolicy
        fields = ["name", "role", "orchard", "plot", "device", "sensitivity_level", "operation", "effect", "start_time", "end_time", "priority", "enabled"]


class ExportFilterForm(StyledFormMixin, forms.Form):
    orchard = forms.ModelChoiceField(queryset=Orchard.objects.none(), required=False, label="果园")
    plot = forms.ModelChoiceField(queryset=Plot.objects.none(), required=False, label="地块")
    device = forms.ModelChoiceField(queryset=Device.objects.none(), required=False, label="设备")
    start_time = forms.DateTimeField(required=False, label="开始时间", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    end_time = forms.DateTimeField(required=False, label="结束时间", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    sensitivity_level = forms.ChoiceField(required=False, label="敏感等级", choices=(("", "自动判断"),) + tuple(SensitivityLevel.choices))

    def __init__(self, *args, user=None, **kwargs):
        from .services import AccessControlService

        super().__init__(*args, **kwargs)
        orchards = AccessControlService.orchard_queryset(user)
        self.fields["orchard"].queryset = orchards
        self.fields["plot"].queryset = Plot.objects.filter(orchard__in=orchards)
        self.fields["device"].queryset = Device.objects.filter(orchard__in=orchards)

    def clean(self):
        cleaned = super().clean()
        orchard = cleaned.get("orchard")
        plot = cleaned.get("plot")
        device = cleaned.get("device")
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and start > end:
            self.add_error("end_time", "结束时间不能早于开始时间")
        if orchard and plot and plot.orchard_id != orchard.pk:
            self.add_error("plot", "地块必须属于所选果园")
        if orchard and device and device.orchard_id != orchard.pk:
            self.add_error("device", "设备必须属于所选果园")
        if plot and device and device.plot_id != plot.pk:
            self.add_error("device", "设备必须属于所选地块")
        return cleaned


class ExportDecisionForm(StyledFormMixin, forms.Form):
    decision = forms.ChoiceField(choices=(("APPROVE", "批准"), ("REJECT", "拒绝")), widget=forms.RadioSelect)
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), label="处理意见")
