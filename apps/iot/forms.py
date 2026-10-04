from django import forms

from apps.accounts.forms import StyledFormMixin


class ReadingFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(required=False, label="关键词")
    orchard = forms.ModelChoiceField(queryset=None, required=False, label="果园")
    device = forms.ModelChoiceField(queryset=None, required=False, label="设备")
    status = forms.ChoiceField(required=False, label="数据状态", choices=(("", "全部"), ("normal", "正常"), ("abnormal", "异常")))

    def __init__(self, *args, user=None, **kwargs):
        from apps.dlp.services import AccessControlService
        from apps.orchards.models import Device, Orchard

        super().__init__(*args, **kwargs)
        orchards = AccessControlService.orchard_queryset(user, Orchard.objects.all())
        self.fields["q"].widget.attrs["placeholder"] = "设备编号关键词"
        self.fields["orchard"].queryset = orchards
        self.fields["orchard"].empty_label = "全部果园"
        self.fields["device"].queryset = Device.objects.filter(orchard__in=orchards)
        self.fields["device"].empty_label = "全部设备"
