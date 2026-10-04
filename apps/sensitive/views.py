from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Role
from apps.audit.services import AuditService
from config.view_utils import render_table, role_required
from .forms import FieldDefinitionForm, SensitiveRuleForm
from .models import SensitiveDetectionRecord, SensitiveFieldDefinition, SensitiveRule, SensitivityLevel


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def field_list(request):
    return render_table(request, title="敏感字段字典", subtitle="维护果园业务字段的类型、语义标签和保护等级", queryset=SensitiveFieldDefinition.objects.all(), columns=[{"label": "字段", "value": "name"}, {"label": "字段名", "value": "field_name"}, {"label": "类型", "value": "field_type", "badge": True}, {"label": "等级", "value": "sensitivity_level", "badge": True}, {"label": "启用", "value": lambda o: "ACTIVE" if o.enabled else "INACTIVE", "badge": True}], search_fields=("name", "field_name", "business_tag"), filters=[{"param": "sensitivity_level", "label": "敏感等级", "choices": SensitivityLevel.choices}], create_url="sensitive:field_create", extra={"edit_url_name": "sensitive:field_edit"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def field_edit(request, pk=None):
    obj = get_object_or_404(SensitiveFieldDefinition, pk=pk) if pk else None
    form = FieldDefinitionForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        AuditService.log("SENSITIVE_FIELD_MODIFY", user=request.user, request=request, object_type="SensitiveFieldDefinition", object_id=str(saved.pk), message=f"维护敏感字段 {saved.field_name}")
        messages.success(request, "敏感字段定义已保存。")
        return redirect("sensitive:fields")
    return render(request, "shared/form.html", {"title": "编辑字段定义" if obj else "新增字段定义", "form": form, "back_url": "sensitive:fields"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def rule_list(request):
    return render_table(request, title="敏感识别规则", subtitle="字段名、正则表达式与业务语义组合识别", queryset=SensitiveRule.objects.all(), columns=[{"label": "规则", "value": "name"}, {"label": "匹配方式", "value": "match_type", "badge": True}, {"label": "字段类型", "value": "field_type"}, {"label": "等级", "value": "sensitivity_level", "badge": True}, {"label": "优先级", "value": "priority"}], search_fields=("name", "pattern", "field_type"), filters=[{"param": "sensitivity_level", "label": "敏感等级", "choices": SensitivityLevel.choices}], create_url="sensitive:rule_create", extra={"edit_url_name": "sensitive:rule_edit"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def rule_edit(request, pk=None):
    obj = get_object_or_404(SensitiveRule, pk=pk) if pk else None
    form = SensitiveRuleForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        AuditService.log("SENSITIVE_RULE_MODIFY", user=request.user, request=request, object_type="SensitiveRule", object_id=str(saved.pk), message=f"维护识别规则 {saved.name}")
        messages.success(request, "识别规则已保存。")
        return redirect("sensitive:rules")
    return render(request, "shared/form.html", {"title": "编辑识别规则" if obj else "新增识别规则", "form": form, "back_url": "sensitive:rules"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def detection_list(request):
    qs = SensitiveDetectionRecord.objects.select_related("matched_rule", "adjusted_by")
    return render_table(request, title="敏感识别记录", subtitle="仅保存指纹与命中信息，不复制原始敏感值", queryset=qs, columns=[{"label": "来源", "value": "source_type"}, {"label": "字段", "value": "field_name"}, {"label": "字段类型", "value": "field_type"}, {"label": "等级", "value": "sensitivity_level", "badge": True}, {"label": "命中规则", "value": lambda o: o.matched_rule.name if o.matched_rule else "字段字典"}, {"label": "时间", "value": lambda o: o.created_at.strftime("%m-%d %H:%M")}], search_fields=("source_type", "field_name", "business_tag"), filters=[{"param": "sensitivity_level", "label": "敏感等级", "choices": SensitivityLevel.choices}])

