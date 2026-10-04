import hashlib
import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.audit.services import AuditService
from apps.orchards.models import Device
from apps.sensitive.services import SensitiveDetectionService
from .models import SensorReading


class IoTValidationService:
    RANGES = {
        "temperature": (Decimal("-50"), Decimal("80")),
        "humidity": (Decimal("0"), Decimal("100")),
        "soil_moisture": (Decimal("0"), Decimal("100")),
        "light": (Decimal("0"), Decimal("200000")),
    }
    REQUIRED = ("device_code", "collection_time")

    @classmethod
    def parse_decimal(cls, payload, field, errors):
        value = payload.get(field)
        if value in (None, ""):
            return None
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            errors.append(f"{field} 不是有效数值")
            return None
        if not parsed.is_finite():
            errors.append(f"{field} 不是有限数值")
            return None
        low, high = cls.RANGES[field]
        if parsed < low or parsed > high:
            errors.append(f"{field} 超出合理范围 {low}~{high}")
        return parsed

    @staticmethod
    def parse_boolean(value, field, errors):
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off", ""}:
                return False
        errors.append(f"{field} 不是有效布尔值")
        return False

    @classmethod
    @transaction.atomic
    def ingest(cls, payload, *, source_type=SensorReading.SourceTypes.HTTP, request=None):
        missing = [field for field in cls.REQUIRED if not payload.get(field)]
        if missing:
            raise ValidationError({"missing_fields": missing})
        try:
            device = Device.objects.select_related("orchard", "plot").get(device_code=payload["device_code"])
        except Device.DoesNotExist as exc:
            raise ValidationError({"device_code": "未知设备"}) from exc
        collection_time = parse_datetime(str(payload.get("collection_time")))
        if collection_time is None:
            raise ValidationError({"collection_time": "时间戳格式错误"})
        if timezone.is_naive(collection_time):
            collection_time = timezone.make_aware(collection_time, timezone.get_current_timezone())
        errors = []
        now = timezone.now()
        if collection_time > now + timedelta(minutes=5):
            errors.append("采集时间明显晚于当前时间")
        if collection_time < now - timedelta(days=90):
            errors.append("采集数据早于允许范围 90 天")
        values = {field: cls.parse_decimal(payload, field, errors) for field in cls.RANGES}
        pest_alarm = cls.parse_boolean(payload.get("pest_alarm", False), "pest_alarm", errors)
        device_status = str(payload.get("device_status", Device.DeviceStatus.ONLINE))
        if device_status not in Device.DeviceStatus.values:
            errors.append("device_status 不是允许的设备状态")
            device_status = Device.DeviceStatus.ABNORMAL
        fingerprint_payload = {key: payload.get(key) for key in sorted(payload)}
        fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        if SensorReading.objects.filter(device=device, payload_fingerprint=fingerprint).exists():
            errors.append("重复数据")
        reading = SensorReading.objects.create(
            orchard=device.orchard,
            plot=device.plot,
            device=device,
            collection_time=collection_time,
            temperature=values["temperature"],
            humidity=values["humidity"],
            soil_moisture=values["soil_moisture"],
            light=values["light"],
            pest_alarm=pest_alarm,
            device_status=device_status,
            is_valid=not errors,
            is_abnormal=bool(errors) or pest_alarm,
            abnormal_reason="；".join(errors) if errors else ("虫情告警" if pest_alarm else ""),
            source_type=source_type,
            raw_payload=payload,
            payload_fingerprint=fingerprint,
        )
        device.last_seen_at = now
        device.status = Device.DeviceStatus.ABNORMAL if reading.is_abnormal else Device.DeviceStatus.ONLINE
        device.save(update_fields=["last_seen_at", "status", "updated_at"])
        SensitiveDetectionService.scan_mapping(
            {"device_code": device.device_code, "collection_time": collection_time.isoformat(), "plot_location": device.plot.location_description if device.plot else ""},
            source_type="SensorReading",
            source_object_id=reading.pk,
            tags={"device_code": "IoT设备标识", "collection_time": "采集时间", "plot_location": "地块位置"},
        )
        AuditService.log(
            "IOT_DATA_INGEST",
            request=request,
            orchard=device.orchard,
            object_type="SensorReading",
            object_id=str(reading.pk),
            result="FAILURE" if errors else "SUCCESS",
            message=reading.abnormal_reason or "IoT 数据接入成功",
        )
        return reading
