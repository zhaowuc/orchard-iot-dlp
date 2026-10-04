import hashlib
import math
import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.audit.models import AuditLog, RiskEvent, SecurityAlert
from apps.audit.services import RiskScoringService
from apps.dashboard.models import SystemConfig
from apps.dlp.export_services import ExportSecurityService
from apps.dlp.models import AccessPolicy, ExportRequest
from apps.iot.models import SensorReading
from apps.masking.models import MaskingRule
from apps.orchards.models import DataSource, Device, Gateway, Orchard, Plot
from apps.sensitive.models import SensitiveDetectionRecord, SensitiveFieldDefinition, SensitiveRule, SensitivityLevel


DEMO_PASSWORD = "Demo@123456"
DEMO_DEVICE_TOKEN = "orchard-device-demo-token"


class Command(BaseCommand):
    help = "幂等创建本科答辩所需的完整演示数据"

    @transaction.atomic
    def handle(self, *args, **options):
        roles = self.seed_roles()
        orchards, plots, devices = self.seed_assets()
        users = self.seed_users(roles, orchards)
        self.seed_configs()
        self.seed_sensitive(roles)
        self.seed_policies(roles, orchards)
        self.seed_readings(devices, target=1800)
        self.seed_detection_records(orchards, devices)
        self.seed_security_history(users, orchards)
        self.seed_export(users["user"], orchards[0])
        self.stdout.write(self.style.SUCCESS("Demo 初始化完成：3 个果园、12 个地块、24 个设备、至少 1800 条传感器数据"))
        self.stdout.write(f"演示账号：admin/security/orchard_admin/user，统一密码：{DEMO_PASSWORD}")
        self.stdout.write(f"设备 API Token：{DEMO_DEVICE_TOKEN}")

    def seed_roles(self):
        labels = {
            Role.Codes.SUPER_ADMIN: ("超级管理员", "全局管理和原始敏感数据权限"),
            Role.Codes.SECURITY_ADMIN: ("安全管理员", "规则、审计、风险、告警和导出审批"),
            Role.Codes.ORCHARD_ADMIN: ("果园管理员", "仅管理授权果园业务资产"),
            Role.Codes.NORMAL_USER: ("普通用户", "授权范围只读，敏感字段默认脱敏"),
        }
        return {code: Role.objects.update_or_create(code=code, defaults={"name": name, "description": desc})[0] for code, (name, desc) in labels.items()}

    def seed_assets(self):
        specs = [
            ("北方红苹果示范园", "ORCH-NORTH", "哈尔滨市松北区智慧农业示范基地", "王建国", "13812345678"),
            ("寒地蓝莓生态园", "ORCH-BERRY", "尚志市帽儿山镇蓝莓基地", "李春梅", "13987654321"),
            ("绿色梨园试验站", "ORCH-PEAR", "五常市拉林镇果树试验区", "赵海峰", "13611223344"),
        ]
        orchards, plots, devices = [], [], []
        types = list(Device.Types.values[:5])
        for oi, (name, code, location, contact, phone) in enumerate(specs):
            orchard, _ = Orchard.objects.update_or_create(code=code, defaults={"name": name, "location": location, "contact_name": contact, "contact_phone": phone, "description": "智慧果园物联网数据安全演示场景", "status": "ACTIVE"})
            orchards.append(orchard)
            gateway, _ = Gateway.objects.update_or_create(gateway_code=f"GW-{oi+1:02d}", defaults={"orchard": orchard, "name": f"{name}主网关", "protocol": "MQTT", "status": "ACTIVE", "last_seen_at": timezone.now()})
            DataSource.objects.update_or_create(name=f"{name} HTTP 接入", orchard=orchard, defaults={"source_type": "HTTP", "endpoint": "/api/iot/data/", "status": "ACTIVE", "config": {"auth": "X-Device-Token"}})
            for pi in range(4):
                plot, _ = Plot.objects.update_or_create(orchard=orchard, code=f"{code}-P{pi+1:02d}", defaults={"name": f"{chr(65+pi)} 区地块", "location_description": f"{location}{chr(65+pi)}区", "latitude": 45.75 + oi * 0.08 + pi * 0.005, "longitude": 126.60 + oi * 0.1 + pi * 0.006, "area": 18 + pi * 3, "status": "ACTIVE"})
                plots.append(plot)
            for di in range(8):
                plot = plots[oi * 4 + di % 4]
                device_code = f"{code}-DEVICE-{di+1:04d}"
                device, created = Device.objects.get_or_create(device_code=device_code, defaults={"device_name": f"{plot.name}{types[di % len(types)]}传感器{di+1}", "device_type": types[di % len(types)], "orchard": orchard, "plot": plot, "gateway": gateway, "status": Device.DeviceStatus.ONLINE, "last_seen_at": timezone.now(), "manufacturer": "果安物联实验室"})
                if created or not device.token_hash:
                    device.set_token(DEMO_DEVICE_TOKEN)
                    device.save(update_fields=["token_hash", "updated_at"])
                devices.append(device)
        return orchards, plots, devices

    def seed_users(self, roles, orchards):
        specs = {
            "admin": ("系统管理员", Role.Codes.SUPER_ADMIN, True),
            "security": ("安全管理员", Role.Codes.SECURITY_ADMIN, False),
            "orchard_admin": ("果园管理员", Role.Codes.ORCHARD_ADMIN, False),
            "user": ("数据查看员", Role.Codes.NORMAL_USER, False),
        }
        result = {}
        for username, (display_name, role_code, is_superuser) in specs.items():
            user, created = User.objects.get_or_create(username=username, defaults={"display_name": display_name, "email": f"{username}@demo.local", "role": roles[role_code], "is_active": True, "is_staff": is_superuser, "is_superuser": is_superuser})
            user.display_name, user.role, user.is_active = display_name, roles[role_code], True
            user.is_staff, user.is_superuser = is_superuser, is_superuser
            user.set_password(DEMO_PASSWORD)
            user.save()
            user.assigned_orchards.set(orchards if role_code in {Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN} else [orchards[0]])
            result[username] = user
        return result

    def seed_configs(self):
        configs = {
            "query_rate_limit": ("普通查询每分钟上限", "30", "INTEGER", "超过后阻止并形成风险事件"),
            "sensitive_query_rate_limit": ("敏感查询每分钟上限", "10", "INTEGER", "敏感查询独立限频"),
            "export_limit": ("普通用户自动导出上限", "200", "INTEGER", "超过记录数进入审批"),
            "risk_alert_threshold": ("自动告警风险阈值", "60", "INTEGER", "达到后自动创建安全告警"),
            "failed_login_threshold": ("连续登录失败阈值", "5", "INTEGER", "10 分钟窗口"),
            "device_offline_timeout": ("设备离线超时/分钟", "30", "INTEGER", "用于设备状态判断"),
        }
        for key, (name, value, value_type, description) in configs.items():
            SystemConfig.objects.update_or_create(key=key, defaults={"name": name, "value": value, "value_type": value_type, "description": description, "editable": True})

    def seed_sensitive(self, roles):
        fields = [
            ("联系人", "contact_name", "contact", "人员信息", "SENSITIVE"), ("手机号", "contact_phone", "phone", "联系方式", "IMPORTANT"),
            ("用户账号", "username", "username", "账号信息", "SENSITIVE"), ("设备编号", "device_code", "device_code", "IoT设备标识", "SENSITIVE"),
            ("地块位置", "plot_location", "location", "地理位置", "SENSITIVE"), ("纬度", "latitude", "coordinate", "地理坐标", "IMPORTANT"),
            ("经度", "longitude", "coordinate", "地理坐标", "IMPORTANT"), ("采集时间", "collection_time", "collection_time", "时间信息", "SENSITIVE"),
            ("告警信息", "abnormal_reason", "alert", "安全告警", "INTERNAL"), ("经营统计", "business_statistics", "statistics", "经营信息", "IMPORTANT"),
        ]
        for name, field_name, field_type, tag, level in fields:
            SensitiveFieldDefinition.objects.update_or_create(field_name=field_name, defaults={"name": name, "field_type": field_type, "business_tag": tag, "sensitivity_level": level, "description": f"果园业务{name}字段", "enabled": True})
            SensitiveRule.objects.update_or_create(name=f"{name}字段名规则", defaults={"match_type": "FIELD_NAME", "pattern": field_name, "field_type": field_type, "sensitivity_level": level, "priority": 20, "enabled": True})
        SensitiveRule.objects.update_or_create(name="中国大陆手机号正则", defaults={"match_type": "REGEX", "pattern": r"(?<!\d)1[3-9]\d{9}(?!\d)", "field_type": "phone", "sensitivity_level": "IMPORTANT", "priority": 5, "enabled": True})
        normal = roles[Role.Codes.NORMAL_USER]
        for field_type, masking_type, level in [("phone", "MASK", "IMPORTANT"), ("device_code", "MASK", "SENSITIVE"), ("username", "MASK", "SENSITIVE"), ("coordinate", "GENERALIZE", "IMPORTANT"), ("collection_time", "MASK", "SENSITIVE"), ("location", "GENERALIZE", "SENSITIVE")]:
            MaskingRule.objects.update_or_create(name=f"普通用户-{field_type}-动态脱敏", defaults={"field_type": field_type, "masking_type": masking_type, "sensitivity_level": level, "role": normal, "scene": "ALL", "config": {}, "priority": 10, "enabled": True})

    def seed_policies(self, roles, orchards):
        for role_code in (Role.Codes.ORCHARD_ADMIN, Role.Codes.NORMAL_USER):
            role = roles[role_code]
            for operation in ("VIEW", "EXPORT"):
                AccessPolicy.objects.update_or_create(name=f"{role_code}-{orchards[0].code}-{operation}", defaults={"role": role, "orchard": orchards[0], "operation": operation, "effect": "ALLOW", "priority": 20, "enabled": True})
        AccessPolicy.objects.update_or_create(name="果园管理员资产维护", defaults={"role": roles[Role.Codes.ORCHARD_ADMIN], "orchard": orchards[0], "operation": "UPDATE", "effect": "ALLOW", "priority": 20, "enabled": True})
        AccessPolicy.objects.update_or_create(name="普通用户禁止原文", defaults={"role": roles[Role.Codes.NORMAL_USER], "operation": "RAW_VIEW", "effect": "DENY", "priority": 1, "enabled": True})

    def seed_readings(self, devices, target):
        existing = SensorReading.objects.count()
        if existing >= target:
            return
        rng = random.Random(20260811)
        now = timezone.now()
        readings = []
        for index in range(existing, target):
            device = devices[index % len(devices)]
            moment = now - timedelta(minutes=(target - index) * 20)
            day_wave = math.sin((moment.hour + moment.minute / 60) / 24 * math.pi * 2)
            temp = 22 + 6 * day_wave + rng.uniform(-1.1, 1.1)
            humidity = 67 - 10 * day_wave + rng.uniform(-2.2, 2.2)
            soil = 49 - (index % 90) * .05 + rng.uniform(-1, 1)
            light = max(0, 42000 * max(day_wave, 0) + rng.uniform(0, 2500))
            abnormal = index % 211 == 0
            payload = {"device_code": device.device_code, "temperature": round(temp, 2), "humidity": 150 if abnormal else round(humidity, 2), "soil_moisture": round(max(18, soil), 2), "light": round(light, 2), "pest_alarm": index % 397 == 0, "device_status": "ONLINE", "collection_time": moment.isoformat()}
            fingerprint = hashlib.sha256(str(payload).encode()).hexdigest()
            readings.append(SensorReading(orchard=device.orchard, plot=device.plot, device=device, temperature=payload["temperature"], humidity=payload["humidity"], soil_moisture=payload["soil_moisture"], light=payload["light"], pest_alarm=payload["pest_alarm"], device_status="ONLINE", collection_time=moment, is_valid=not abnormal, is_abnormal=abnormal or payload["pest_alarm"], abnormal_reason="humidity 超出合理范围 0~100" if abnormal else "虫情告警" if payload["pest_alarm"] else "", source_type="SIMULATOR", raw_payload=payload, payload_fingerprint=fingerprint))
        SensorReading.objects.bulk_create(readings, batch_size=500)

    def seed_detection_records(self, orchards, devices):
        for orchard in orchards:
            samples = [("contact_name", orchard.contact_name, "contact", "SENSITIVE"), ("contact_phone", orchard.contact_phone, "phone", "IMPORTANT"), ("plot_location", orchard.location, "location", "SENSITIVE")]
            for field_name, value, field_type, level in samples:
                SensitiveDetectionRecord.objects.get_or_create(source_type="Orchard", source_object_id=str(orchard.pk), field_name=field_name, value_fingerprint=hashlib.sha256(value.encode()).hexdigest(), defaults={"field_type": field_type, "is_sensitive": True, "sensitivity_level": level, "business_tag": "果园业务"})
        for device in devices:
            SensitiveDetectionRecord.objects.get_or_create(source_type="Device", source_object_id=str(device.pk), field_name="device_code", value_fingerprint=hashlib.sha256(device.device_code.encode()).hexdigest(), defaults={"field_type": "device_code", "is_sensitive": True, "sensitivity_level": "SENSITIVE", "business_tag": "IoT设备标识"})

    def seed_security_history(self, users, orchards):
        if not AuditLog.objects.exists():
            for idx in range(30):
                AuditLog.objects.create(user=users["user" if idx % 3 else "security"], username_snapshot=users["user" if idx % 3 else "security"].username, action="DATA_QUERY" if idx % 4 else "MASKING_PREVIEW", object_type="SensorReading", object_id=str(idx + 1), orchard=orchards[0], result="SUCCESS", record_count=20 + idx, sensitivity_level="SENSITIVE", risk_score=0, message="演示历史审计记录")
        if not RiskEvent.objects.exists():
            RiskScoringService.create_event("历史高频敏感查询", ["high_frequency_query", "sensitive_access", "repeated_anomaly"], user=users["user"], details={"demo": True})
            event = RiskScoringService.create_event("历史异常批量导出", ["large_export", "important_data", "sensitive_access", "repeated_anomaly"], user=users["user"], details={"demo": True})
            alert = SecurityAlert.objects.filter(event=event).first()
            if alert:
                alert.status, alert.handler, alert.handling_comment, alert.handled_at = "RESOLVED", users["security"], "已确认演示异常批量导出并完成处置。", timezone.now()
                alert.save()
        if not SecurityAlert.objects.filter(status=SecurityAlert.Status.PENDING).exists():
            RiskScoringService.create_event("待处理跨果园导出告警", ["unauthorized_orchard", "large_export", "important_data", "repeated_anomaly"], user=users["user"], details={"demo": True, "requires_handling": True})

    def seed_export(self, user, orchard):
        if ExportRequest.objects.filter(user=user, filters__demo=True).exists():
            return
        request = ExportRequest.objects.create(export_id=uuid.uuid4(), user=user, orchard=orchard, filters={"demo": True}, estimated_count=25, sensitive_count=50, status="APPROVED", requested_ip="127.0.0.1", sensitivity_level="SENSITIVE")
        ExportSecurityService.generate(request)
