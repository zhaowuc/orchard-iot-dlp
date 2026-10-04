from django import forms

from .models import Role, User


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class RoleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Role
        fields = ["name", "code", "description"]


class UserForm(StyledFormMixin, forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput, help_text="新建用户必须填写；编辑时留空表示不修改。")

    class Meta:
        model = User
        fields = ["username", "display_name", "email", "phone", "role", "assigned_orchards", "is_active", "password"]
        widgets = {"assigned_orchards": forms.SelectMultiple(attrs={"size": 6})}

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user

