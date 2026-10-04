from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Role
from apps.audit.services import AuditService
from config.view_utils import render_table, role_required
from .forms import MaskingPreviewForm, MaskingRuleForm
from .models import MaskingRecord, MaskingRule
from .services import MaskingService


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def rule_list(request):
    return render_table(request, title="动态脱敏策略", subtitle="按角色、场景和数据等级实时选择脱敏强度", queryset=MaskingRule.objects.select_related("role"), columns=[{"label": "规则", "value": "name"}, {"label": "字段类型", "value": "field_type", "badge": True}, {"label": "算法", "value": "masking_type", "badge": True}, {"label": "等级", "value": "sensitivity_level", "badge": True}, {"label": "角色", "value": lambda o: o.role.name if o.role else "全部角色"}, {"label": "场景", "value": "scene", "badge": True}], search_fields=("name", "field_type"), create_url="masking:rule_create", extra={"edit_url_name": "masking:rule_edit"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def rule_edit(request, pk=None):
    obj = get_object_or_404(MaskingRule, pk=pk) if pk else None
    form = MaskingRuleForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        AuditService.log("MASKING_RULE_MODIFY", user=request.user, request=request, object_type="MaskingRule", object_id=str(saved.pk), message=f"维护脱敏规则 {saved.name}")
        messages.success(request, "脱敏规则已保存。")
        return redirect("masking:rules")
    return render(request, "shared/form.html", {"title": "编辑脱敏规则" if obj else "新增脱敏规则", "form": form, "back_url": "masking:rules"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def preview(request):
    form = MaskingPreviewForm(request.POST or None, initial={"field_type": "phone", "masking_type": "MASK", "test_value": "13812345678"})
    result = None
    if request.method == "POST" and form.is_valid():
        result = MaskingService.transform(form.cleaned_data["test_value"], form.cleaned_data["field_type"], form.cleaned_data["masking_type"])
        AuditService.log("MASKING_PREVIEW", user=request.user, request=request, message=f"预览 {form.cleaned_data['field_type']} 脱敏效果")
    return render(request, "masking/preview.html", {"title": "脱敏预览", "form": form, "result": result})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def record_list(request):
    return render_table(request, title="脱敏命中记录", subtitle="记录脱敏动作与原文指纹，不存储原文副本", queryset=MaskingRecord.objects.select_related("user", "rule"), columns=[{"label": "用户", "value": lambda o: o.user.username if o.user else "系统"}, {"label": "字段类型", "value": "field_type", "badge": True}, {"label": "场景", "value": "scene", "badge": True}, {"label": "规则", "value": lambda o: o.rule.name if o.rule else "默认规则"}, {"label": "结果预览", "value": "result_preview"}, {"label": "时间", "value": lambda o: o.created_at.strftime("%m-%d %H:%M")}], search_fields=("field_type", "source_type", "user__username"))

