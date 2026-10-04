from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from config.view_utils import render_table, role_required
from .forms import AlertHandlingForm
from .models import AuditLog, RiskEvent, SecurityAlert
from .services import AuditService


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def audit_list(request):
    return render_table(request, title="操作审计日志", subtitle="登录、查询、规则、导出、权限和告警处置的统一证据链", queryset=AuditLog.objects.select_related("user", "orchard"), columns=[{"label": "用户", "value": lambda o: o.username_snapshot or "系统"}, {"label": "动作", "value": "action", "badge": True}, {"label": "路径/对象", "value": lambda o: o.request_path or f"{o.object_type}:{o.object_id}"}, {"label": "结果", "value": "result", "badge": True}, {"label": "风险分", "value": "risk_score"}, {"label": "说明", "value": "message"}, {"label": "时间", "value": lambda o: o.created_at.strftime("%m-%d %H:%M:%S")}], search_fields=("username_snapshot", "action", "request_path", "message"), filters=[{"param": "result", "label": "结果", "choices": AuditLog.Results.choices}])


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def risk_list(request):
    return render_table(request, title="风险事件", subtitle="0-100 分可解释规则评分，点击记录查看分项原因", queryset=RiskEvent.objects.select_related("user", "related_audit_log"), columns=[{"label": "用户", "value": lambda o: o.user.username if o.user else "未知/系统"}, {"label": "事件", "value": "event_type"}, {"label": "风险等级", "value": "risk_level", "badge": True}, {"label": "得分", "value": "score", "badge": True}, {"label": "原因", "value": "reason"}, {"label": "时间", "value": lambda o: o.created_at.strftime("%m-%d %H:%M:%S")}], search_fields=("user__username", "event_type", "reason"), filters=[{"param": "risk_level", "label": "风险等级", "choices": RiskEvent.Levels.choices}])


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
def alert_list(request):
    return render_table(request, title="安全告警", subtitle="高风险事件自动生成告警，由安全管理员闭环处置", queryset=SecurityAlert.objects.select_related("user", "event", "handler"), columns=[{"label": "标题", "value": "title"}, {"label": "用户", "value": lambda o: o.user.username if o.user else "未知/系统"}, {"label": "风险", "value": "risk_level", "badge": True}, {"label": "得分", "value": "score", "badge": True}, {"label": "状态", "value": "status", "badge": True}, {"label": "处理人", "value": lambda o: o.handler.username if o.handler else "—"}], search_fields=("title", "description", "user__username"), filters=[{"param": "status", "label": "处理状态", "choices": SecurityAlert.Status.choices}], extra={"detail_url_name": "audit:alert_handle"})


@role_required(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
@transaction.atomic
def alert_handle(request, pk):
    alert = get_object_or_404(SecurityAlert.objects.select_for_update().select_related("event", "user"), pk=pk)
    original_status = alert.status
    original_comment = alert.handling_comment
    form = AlertHandlingForm(request.POST or None, instance=alert)
    if request.method == "POST" and form.is_valid():
        if original_status == form.cleaned_data["status"] and original_comment == form.cleaned_data["handling_comment"]:
            messages.info(request, "该告警已处于相同处理状态，无需重复提交。")
            return redirect("audit:alerts")
        saved = form.save(commit=False)
        saved.handler = request.user
        saved.handled_at = timezone.now() if saved.status in {SecurityAlert.Status.RESOLVED, SecurityAlert.Status.IGNORED} else None
        saved.save()
        AuditService.log("ALERT_HANDLE", user=request.user, request=request, object_type="SecurityAlert", object_id=str(saved.pk), risk_score=saved.score, message=f"告警状态更新为 {saved.status}：{saved.handling_comment}")
        messages.success(request, "告警处置结果已保存并写入审计日志。")
        return redirect("audit:alerts")
    breakdown = alert.event.details.get("breakdown", []) if isinstance(alert.event.details, dict) else []
    return render(request, "audit/alert_detail.html", {"title": "安全告警处置", "alert": alert, "form": form, "breakdown": breakdown})
