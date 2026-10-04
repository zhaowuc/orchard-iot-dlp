import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.services import AuditService
from config.view_utils import render_table, role_required
from .export_services import ExportSecurityService
from .forms import AccessPolicyForm, ExportDecisionForm, ExportFilterForm
from .models import AccessPolicy, ExportRecord, ExportRequest, QueryMonitor


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def policy_list(request):
    return render_table(request, title="访问策略", subtitle="基于角色与果园、地块、设备、敏感等级的属性访问控制", queryset=AccessPolicy.objects.select_related("role", "orchard", "plot", "device"), columns=[{"label": "策略", "value": "name"}, {"label": "角色", "value": lambda o: o.role.name}, {"label": "数据范围", "value": lambda o: o.device.device_code if o.device else o.plot.name if o.plot else o.orchard.name if o.orchard else "全局"}, {"label": "操作", "value": "operation", "badge": True}, {"label": "效果", "value": "effect", "badge": True}, {"label": "优先级", "value": "priority"}], search_fields=("name", "role__name", "orchard__name"), create_url="dlp:policy_create", extra={"edit_url_name": "dlp:policy_edit"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def policy_edit(request, pk=None):
    obj = get_object_or_404(AccessPolicy, pk=pk) if pk else None
    form = AccessPolicyForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        AuditService.log("ACCESS_POLICY_MODIFY", user=request.user, request=request, object_type="AccessPolicy", object_id=str(saved.pk), message=f"维护访问策略 {saved.name}")
        messages.success(request, "访问策略已保存。")
        return redirect("dlp:policies")
    return render(request, "shared/form.html", {"title": "编辑访问策略" if obj else "新增访问策略", "form": form, "back_url": "dlp:policies"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def query_list(request):
    return render_table(request, title="查询行为监控", subtitle="60 秒窗口内统计普通与敏感查询频率", queryset=QueryMonitor.objects.select_related("user", "orchard", "plot"), columns=[{"label": "用户", "value": lambda o: o.user.username if o.user else "匿名"}, {"label": "路径", "value": "path"}, {"label": "果园", "value": lambda o: o.orchard.name if o.orchard else "—"}, {"label": "记录数", "value": "record_count"}, {"label": "敏感数", "value": "sensitive_count"}, {"label": "结果", "value": lambda o: "BLOCKED" if o.blocked else "SUCCESS", "badge": True}, {"label": "时间", "value": lambda o: o.created_at.strftime("%m-%d %H:%M:%S")}], search_fields=("user__username", "path", "orchard__name"))


def export_center(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    form = ExportFilterForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        export_request, record = ExportSecurityService.request_export(request, form.cleaned_data)
        if record:
            messages.success(request, "导出文件已生成，可在导出记录中安全下载。")
        else:
            messages.warning(request, "该导出涉及较多敏感数据，已进入安全审批。")
        return redirect("dlp:exports")
    requests = ExportRequest.objects.select_related("user", "orchard", "approved_by")
    records = ExportRecord.objects.select_related("user", "approved_by")
    if not request.user.has_role(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN):
        requests = requests.filter(user=request.user)
        records = records.filter(user=request.user)
    return render(request, "dlp/exports.html", {"title": "安全导出中心", "form": form, "export_requests": requests[:30], "export_records": records[:30]})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
@transaction.atomic
def export_decide(request, export_id):
    obj = get_object_or_404(ExportRequest.objects.select_for_update(), export_id=export_id, status=ExportRequest.Status.PENDING)
    form = ExportDecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        approve = form.cleaned_data["decision"] == "APPROVE"
        obj.status = ExportRequest.Status.APPROVED if approve else ExportRequest.Status.REJECTED
        obj.approved_by = request.user
        obj.decision_comment = form.cleaned_data["comment"]
        obj.decided_at = timezone.now()
        obj.save(update_fields=["status", "approved_by", "decision_comment", "decided_at", "updated_at"])
        AuditService.log("EXPORT_APPROVAL", user=request.user, request=request, object_type="ExportRequest", object_id=str(obj.export_id), orchard=obj.orchard, result="SUCCESS", message=f"{'批准' if approve else '拒绝'}导出：{obj.decision_comment}")
        if approve:
            ExportSecurityService.generate(obj, request=request)
        messages.success(request, "导出审批已处理。")
        return redirect("dlp:exports")
    return render(request, "shared/form.html", {"title": f"处理导出申请 {obj.export_id}", "form": form, "back_url": "dlp:exports"})


def export_download(request, export_id):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    record = get_object_or_404(ExportRecord, export_id=export_id)
    if record.user_id != request.user.id and not request.user.has_role(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN):
        AuditService.log("UNAUTHORIZED_EXPORT_DOWNLOAD", user=request.user, request=request, result="BLOCKED", object_type="ExportRecord", object_id=str(export_id), message="试图下载其他用户导出文件")
        raise PermissionDenied("无权下载该导出文件")
    export_request = record.request
    if not export_request or export_request.status != ExportRequest.Status.COMPLETED:
        raise PermissionDenied("导出文件当前不可下载")
    if export_request.expires_at and export_request.expires_at <= timezone.now():
        export_request.status = ExportRequest.Status.EXPIRED
        export_request.save(update_fields=["status", "updated_at"])
        raise PermissionDenied("导出文件已过期")
    base = Path(settings.MEDIA_ROOT).resolve()
    path = (base / record.file_path).resolve()
    if base not in path.parents or not path.is_file():
        raise PermissionDenied("导出文件不可用")
    if not record.file_hash or hashlib.sha256(path.read_bytes()).hexdigest() != record.file_hash:
        AuditService.log("EXPORT_INTEGRITY_FAILURE", user=request.user, request=request, result="BLOCKED", object_type="ExportRecord", object_id=str(export_id), message="导出文件哈希校验失败")
        raise PermissionDenied("导出文件完整性校验失败")
    AuditService.log("EXPORT_DOWNLOAD", user=request.user, request=request, object_type="ExportRecord", object_id=str(export_id), record_count=record.record_count, message="下载安全导出文件")
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type="text/csv; charset=utf-8")
