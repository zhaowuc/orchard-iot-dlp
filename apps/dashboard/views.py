from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog, RiskEvent, SecurityAlert
from apps.audit.services import AuditService
from apps.dlp.models import ExportRecord
from apps.dlp.services import AccessControlService
from apps.iot.models import SensorReading
from apps.masking.models import MaskingRecord
from apps.orchards.models import Device
from apps.sensitive.models import SensitiveDetectionRecord
from config.view_utils import render_table, role_required
from .forms import SystemConfigForm
from .models import SystemConfig


def _days(request):
    try:
        value = int(request.GET.get("days", 7))
    except ValueError:
        value = 7
    return value if value in {1, 7, 30} else 7


def _dashboard_payload(user, days=7):
    now = timezone.now()
    start = now - timedelta(days=days)
    today = timezone.localdate()
    orchards = AccessControlService.orchard_queryset(user)
    devices = Device.objects.filter(orchard__in=orchards)
    readings = SensorReading.objects.filter(orchard__in=orchards)
    can_manage_security = user.has_role(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
    risks = RiskEvent.objects.all() if can_manage_security else RiskEvent.objects.filter(user=user)
    alerts = SecurityAlert.objects.all() if can_manage_security else SecurityAlert.objects.filter(user=user)
    masking = MaskingRecord.objects.all() if can_manage_security else MaskingRecord.objects.filter(user=user)
    offline_timeout = SystemConfig.get_value("device_offline_timeout", 30)
    online_cutoff = now - timedelta(minutes=offline_timeout)
    online_devices = devices.filter(last_seen_at__gte=online_cutoff).exclude(status__in=[Device.DeviceStatus.DISABLED, Device.DeviceStatus.ABNORMAL])
    abnormal_devices = devices.filter(status=Device.DeviceStatus.ABNORMAL)
    disabled_devices = devices.filter(status=Device.DeviceStatus.DISABLED)
    offline_count = devices.count() - online_devices.count() - abnormal_devices.count() - disabled_devices.count()
    cards = {
        "device_total": devices.count(),
        "device_online": online_devices.count(),
        "device_offline": max(offline_count, 0),
        "today_readings": readings.filter(collection_time__date=today).count(),
        "sensitive_fields": SensitiveDetectionRecord.objects.filter(is_sensitive=True).values("field_name").distinct().count(),
        "today_masking": masking.filter(created_at__date=today).count(),
        "today_risks": risks.filter(created_at__date=today).count(),
        "pending_alerts": alerts.filter(status=SecurityAlert.Status.PENDING).count(),
    }
    trend = list(
        readings.filter(collection_time__gte=start)
        .annotate(day=TruncDate("collection_time"))
        .values("day")
        .annotate(temperature=Avg("temperature"), humidity=Avg("humidity"), soil=Avg("soil_moisture"), light=Avg("light"))
        .order_by("day")
    )
    risk_trend = list(risks.filter(created_at__gte=start).annotate(day=TruncDate("created_at")).values("day").annotate(count=Count("id")).order_by("day"))
    alert_trend = list(alerts.filter(created_at__gte=start).annotate(day=TruncDate("created_at")).values("day").annotate(count=Count("id")).order_by("day"))
    sensitive_distribution = list(SensitiveDetectionRecord.objects.values("sensitivity_level").annotate(count=Count("id")).order_by("sensitivity_level"))
    device_distribution = [
        {"status": "ONLINE", "count": online_devices.count()},
        {"status": "OFFLINE", "count": max(offline_count, 0)},
        {"status": "ABNORMAL", "count": abnormal_devices.count()},
        {"status": "DISABLED", "count": disabled_devices.count()},
    ]
    charts = {
        "labels": [item["day"].isoformat() for item in trend],
        "temperature": [round(float(item["temperature"] or 0), 2) for item in trend],
        "humidity": [round(float(item["humidity"] or 0), 2) for item in trend],
        "soil": [round(float(item["soil"] or 0), 2) for item in trend],
        "light": [round(float(item["light"] or 0), 2) for item in trend],
        "risk_trend": [{"date": x["day"].isoformat(), "count": x["count"]} for x in risk_trend],
        "alert_trend": [{"date": x["day"].isoformat(), "count": x["count"]} for x in alert_trend],
        "sensitive_distribution": sensitive_distribution,
        "device_distribution": device_distribution,
    }
    return cards, charts


@login_required
def index(request):
    days = _days(request)
    cards, charts = _dashboard_payload(request.user, days)
    can_manage_security = request.user.has_role(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)
    recent = {
        "alerts": SecurityAlert.objects.select_related("user").all()[:5] if can_manage_security else SecurityAlert.objects.none(),
        "audits": AuditLog.objects.filter(risk_score__gte=30).select_related("user")[:5] if can_manage_security else AuditLog.objects.filter(user=request.user, risk_score__gte=30)[:5],
        "exports": ExportRecord.objects.select_related("user")[:5] if can_manage_security else ExportRecord.objects.filter(user=request.user)[:5],
        "abnormal_readings": SensorReading.objects.filter(is_abnormal=True, orchard__in=AccessControlService.orchard_queryset(request.user)).select_related("device")[:5],
    }
    return render(request, "dashboard/index.html", {"cards": cards, "charts": charts, "days": days, "recent": recent, "can_manage_security": can_manage_security})


@login_required
def chart_api(request):
    cards, charts = _dashboard_payload(request.user, _days(request))
    return JsonResponse({"cards": cards, "charts": charts})


@role_required(Role.Codes.SUPER_ADMIN)
def config_list(request):
    return render_table(request, title="系统参数", subtitle="安全阈值集中配置，业务服务实时读取最新值", queryset=SystemConfig.objects.all(), columns=[{"label": "参数", "value": "name"}, {"label": "键", "value": "key"}, {"label": "值", "value": "value", "badge": True}, {"label": "类型", "value": "value_type"}, {"label": "说明", "value": "description"}], search_fields=("name", "key", "description"), extra={"edit_url_name": "dashboard:config_edit"})


@role_required(Role.Codes.SUPER_ADMIN)
def config_edit(request, pk):
    obj = get_object_or_404(SystemConfig, pk=pk, editable=True)
    form = SystemConfigForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        AuditService.log("SYSTEM_CONFIG_MODIFY", user=request.user, request=request, object_type="SystemConfig", object_id=str(saved.pk), message=f"更新系统参数 {saved.key}={saved.value}")
        messages.success(request, "系统参数已更新，相关业务逻辑将立即读取新值。")
        return redirect("dashboard:configs")
    return render(request, "shared/form.html", {"title": f"编辑系统参数：{obj.name}", "form": form, "back_url": "dashboard:configs"})
