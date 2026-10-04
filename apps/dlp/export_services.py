import csv
import hashlib
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.audit.services import AuditService, BehaviorBaselineService, RiskScoringService
from apps.iot.models import SensorReading
from apps.masking.models import MaskingRule
from apps.masking.services import MaskingService
from apps.sensitive.models import SensitivityLevel
from .models import ExportRecord, ExportRequest
from .services import AccessControlService


class ExportSecurityService:
    FORMULA_PREFIXES = ("=", "+", "-", "@")

    @classmethod
    def safe_csv_cell(cls, value):
        if value is None:
            return ""
        text = str(value)
        if text.startswith(cls.FORMULA_PREFIXES) or text[:1] in {"\t", "\r"}:
            return "'" + text
        return value

    @classmethod
    def filtered_queryset(cls, user, filters):
        qs = SensorReading.objects.filter(orchard__in=AccessControlService.orchard_queryset(user)).select_related("orchard", "plot", "device")
        for key in ("orchard", "plot", "device"):
            if filters.get(key):
                qs = qs.filter(**{key: filters[key]})
        if filters.get("start_time"):
            qs = qs.filter(collection_time__gte=filters["start_time"])
        if filters.get("end_time"):
            qs = qs.filter(collection_time__lte=filters["end_time"])
        return qs

    @classmethod
    @transaction.atomic
    def request_export(cls, request, filters):
        from apps.dashboard.models import SystemConfig

        serialized_filters = {
            k: (v.pk if hasattr(v, "pk") else v.isoformat() if hasattr(v, "isoformat") else v)
            for k, v in filters.items() if v
        }
        recent = ExportRequest.objects.filter(
            user=request.user,
            filters=serialized_filters,
            created_at__gte=timezone.now() - timedelta(seconds=10),
            status__in=[ExportRequest.Status.PENDING, ExportRequest.Status.APPROVED, ExportRequest.Status.COMPLETED],
        ).select_related("record").first()
        if recent:
            return recent, getattr(recent, "record", None)
        qs = cls.filtered_queryset(request.user, filters)
        count = qs.count()
        export_limit = SystemConfig.get_value("export_limit", 200)
        level = filters.get("sensitivity_level") or SensitivityLevel.SENSITIVE
        needs_approval = request.user.role_code == "NORMAL_USER" and (count > export_limit or level == SensitivityLevel.IMPORTANT)
        export_request = ExportRequest.objects.create(
            user=request.user,
            orchard=filters.get("orchard"),
            plot=filters.get("plot"),
            device=filters.get("device"),
            start_time=filters.get("start_time"),
            end_time=filters.get("end_time"),
            sensitivity_level=level,
            filters=serialized_filters,
            estimated_count=count,
            sensitive_count=count * 2,
            requested_ip=request.META.get("REMOTE_ADDR"),
            status=ExportRequest.Status.PENDING if needs_approval else ExportRequest.Status.APPROVED,
        )
        AuditService.log("EXPORT_REQUEST", user=request.user, request=request, object_type="ExportRequest", object_id=str(export_request.export_id), orchard=export_request.orchard, record_count=count, sensitivity_level=level, message="导出进入审批" if needs_approval else "小规模导出自动批准")
        if needs_approval:
            factors = ["large_export", "sensitive_access"] + BehaviorBaselineService.extra_factors(request.user, orchard=export_request.orchard, export_size=count)
            RiskScoringService.create_event("大规模敏感数据导出申请", factors, user=request.user, details={"export_id": str(export_request.export_id), "record_count": count})
            return export_request, None
        return export_request, cls.generate(export_request, request=request)

    @classmethod
    @transaction.atomic
    def generate(cls, export_request, request=None):
        if export_request.status != ExportRequest.Status.APPROVED:
            raise PermissionDenied("只有已批准的导出申请可以生成文件")
        if export_request.expires_at and export_request.expires_at <= timezone.now():
            export_request.status = ExportRequest.Status.EXPIRED
            export_request.save(update_fields=["status", "updated_at"])
            raise PermissionDenied("导出申请已过期")
        filters = {
            "orchard": export_request.orchard,
            "plot": export_request.plot,
            "device": export_request.device,
            "start_time": export_request.start_time,
            "end_time": export_request.end_time,
        }
        qs = cls.filtered_queryset(export_request.user, filters)
        export_id = export_request.export_id or uuid.uuid4()
        export_dir = Path(settings.MEDIA_ROOT) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"orchard_export_{export_id}.csv"
        device_level = MaskingService.level_for_field("device_code", "device_code", SensitivityLevel.SENSITIVE)
        time_level = MaskingService.level_for_field("collection_time", "collection_time", SensitivityLevel.SENSITIVE)
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["# EXPORT_ID", str(export_id)])
            writer.writerow(["# USER", cls.safe_csv_cell(export_request.user.username)])
            writer.writerow(["# EXPORT_TIME", timezone.localtime().isoformat()])
            writer.writerow([])
            writer.writerow(["果园", "地块", "设备编号", "温度", "湿度", "土壤墒情", "光照", "虫情告警", "设备状态", "采集时间", "数据状态", "异常原因"])
            for reading in qs.iterator(chunk_size=500):
                writer.writerow([
                    cls.safe_csv_cell(reading.orchard.name),
                    cls.safe_csv_cell(reading.plot.name if reading.plot else ""),
                    MaskingService.apply(reading.device.device_code, "device_code", user=export_request.user, scene=MaskingRule.Scenes.EXPORT, sensitivity_level=device_level, orchard=reading.orchard, source_type="SensorReading", source_object_id=reading.pk),
                    reading.temperature,
                    reading.humidity,
                    reading.soil_moisture,
                    reading.light,
                    "是" if reading.pest_alarm else "否",
                    reading.device_status,
                    MaskingService.apply(reading.collection_time.strftime("%Y-%m-%d %H:%M:%S"), "collection_time", user=export_request.user, scene=MaskingRule.Scenes.EXPORT, sensitivity_level=time_level, orchard=reading.orchard, source_type="SensorReading", source_object_id=reading.pk),
                    "异常" if reading.is_abnormal else "正常",
                    cls.safe_csv_cell(reading.abnormal_reason),
                ])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record, _ = ExportRecord.objects.update_or_create(
            export_id=export_id,
            defaults={
                "request": export_request,
                "user": export_request.user,
                "username_snapshot": export_request.user.username,
                "ip_address": export_request.requested_ip,
                "filters": export_request.filters,
                "record_count": qs.count(),
                "sensitive_count": qs.count() * 2,
                "approved_by": export_request.approved_by,
                "exported_at": timezone.now(),
                "file_path": str(path.relative_to(settings.MEDIA_ROOT)),
                "file_hash": digest,
            },
        )
        export_request.status = ExportRequest.Status.COMPLETED
        export_request.save(update_fields=["status", "updated_at"])
        AuditService.log("EXPORT_GENERATE", user=export_request.user, request=request, object_type="ExportRecord", object_id=str(record.export_id), orchard=export_request.orchard, record_count=record.record_count, sensitivity_level=export_request.sensitivity_level, message="安全导出文件生成完成")
        return record
