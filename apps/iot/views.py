import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.dlp.services import AccessControlService, QueryLimitService
from apps.masking.models import MaskingRule
from apps.masking.services import MaskingService
from apps.orchards.models import Device
from config.view_utils import paginate
from .forms import ReadingFilterForm
from .models import SensorReading
from .services import IoTValidationService


def _scoped_readings(user):
    orchards = AccessControlService.orchard_queryset(user)
    return SensorReading.objects.filter(orchard__in=orchards).select_related("orchard", "plot", "device")


@login_required
def reading_list(request):
    qs = _scoped_readings(request.user)
    form = ReadingFilterForm(request.GET or None, user=request.user)
    if form.is_valid():
        data = form.cleaned_data
        if data.get("q"):
            qs = qs.filter(device__device_code__icontains=data["q"])
        if data.get("orchard"):
            qs = qs.filter(orchard=data["orchard"])
        if data.get("device"):
            qs = qs.filter(device=data["device"])
        if data.get("status") == "abnormal":
            qs = qs.filter(is_abnormal=True)
        if data.get("status") == "normal":
            qs = qs.filter(is_abnormal=False)
    total = qs.count()
    sensitive_count = min(total * 2, 10000)
    QueryLimitService.record_and_check(request, record_count=min(total, 1000), sensitive_count=min(sensitive_count, 1000))
    page_obj = paginate(request, qs, 25)
    device_level = MaskingService.level_for_field("device_code", "device_code", "SENSITIVE")
    time_level = MaskingService.level_for_field("collection_time", "collection_time", "SENSITIVE")
    rows = []
    for reading in page_obj.object_list:
        rows.append({
            "object": reading,
            "device_code": MaskingService.apply(reading.device.device_code, "device_code", user=request.user, scene=MaskingRule.Scenes.WEB_VIEW, sensitivity_level=device_level, orchard=reading.orchard, source_type="SensorReading", source_object_id=reading.pk),
            "collection_time": MaskingService.apply(reading.collection_time.strftime("%Y-%m-%d %H:%M:%S"), "collection_time", user=request.user, scene=MaskingRule.Scenes.WEB_VIEW, sensitivity_level=time_level, orchard=reading.orchard, source_type="SensorReading", source_object_id=reading.pk),
        })
    return render(request, "iot/readings.html", {"title": "实时与历史数据", "form": form, "rows": rows, "page_obj": page_obj, "total": total})


@csrf_exempt
@require_POST
def ingest_api(request):
    if request.content_type != "application/json":
        return JsonResponse({"ok": False, "error": "Content-Type 必须为 application/json"}, status=415)
    if len(request.body) > 64 * 1024:
        return JsonResponse({"ok": False, "error": "请求体超过 64 KiB 限制"}, status=413)
    try:
        payload = json.loads(
            request.body.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"非法数值 {value}")),
        )
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "JSON 格式错误"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "JSON 顶层必须是对象"}, status=400)
    device = Device.objects.filter(device_code=payload.get("device_code", "")).first()
    if not device:
        return JsonResponse({"ok": False, "error": "未知设备"}, status=404)
    token = request.headers.get("X-Device-Token", "")
    if not device.check_token(token):
        return JsonResponse({"ok": False, "error": "设备认证失败"}, status=403)
    try:
        reading = IoTValidationService.ingest(payload, source_type=SensorReading.SourceTypes.HTTP, request=request)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=400)
    return JsonResponse({"ok": True, "id": reading.pk, "is_valid": reading.is_valid, "is_abnormal": reading.is_abnormal, "abnormal_reason": reading.abnormal_reason}, status=201)


@require_GET
@login_required
def readings_api(request):
    qs = _scoped_readings(request.user)[:100]
    QueryLimitService.record_and_check(request, record_count=len(qs), sensitive_count=len(qs) * 2)
    data = []
    device_level = MaskingService.level_for_field("device_code", "device_code", "SENSITIVE")
    time_level = MaskingService.level_for_field("collection_time", "collection_time", "SENSITIVE")
    for reading in qs:
        data.append({
            "id": reading.pk,
            "orchard": reading.orchard.name,
            "device_code": MaskingService.apply(reading.device.device_code, "device_code", user=request.user, scene=MaskingRule.Scenes.API, sensitivity_level=device_level, orchard=reading.orchard, source_type="SensorReading", source_object_id=reading.pk),
            "temperature": float(reading.temperature) if reading.temperature is not None else None,
            "humidity": float(reading.humidity) if reading.humidity is not None else None,
            "soil_moisture": float(reading.soil_moisture) if reading.soil_moisture is not None else None,
            "light": float(reading.light) if reading.light is not None else None,
            "collection_time": MaskingService.apply(reading.collection_time.strftime("%Y-%m-%d %H:%M:%S"), "collection_time", user=request.user, scene=MaskingRule.Scenes.API, sensitivity_level=time_level, orchard=reading.orchard, source_type="SensorReading", source_object_id=reading.pk),
            "is_abnormal": reading.is_abnormal,
            "abnormal_reason": reading.abnormal_reason,
        })
    return JsonResponse({"count": len(data), "results": data})
