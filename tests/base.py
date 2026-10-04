from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.dashboard.models import SystemConfig
from apps.dlp.models import AccessPolicy
from apps.iot.models import SensorReading
from apps.masking.models import MaskingRule
from apps.orchards.models import Device, Orchard, Plot
from apps.sensitive.models import SensitiveFieldDefinition, SensitiveRule


PASSWORD = "Test@123456"
DEVICE_TOKEN = "test-device-token"


class BaseDataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.roles = {}
        labels = {
            "SUPER_ADMIN": "超级管理员",
            "SECURITY_ADMIN": "安全管理员",
            "ORCHARD_ADMIN": "果园管理员",
            "NORMAL_USER": "普通用户",
        }
        for code, name in labels.items():
            cls.roles[code] = Role.objects.create(code=code, name=name)
        cls.orchard1 = Orchard.objects.create(name="测试苹果园", code="TEST-A", location="哈尔滨市松北区测试基地", contact_name="张三", contact_phone="13812345678", status="ACTIVE")
        cls.orchard2 = Orchard.objects.create(name="未授权梨园", code="TEST-B", location="五常市测试基地", contact_name="李四", contact_phone="13987654321", status="ACTIVE")
        cls.plot1 = Plot.objects.create(orchard=cls.orchard1, name="A区", code="A01", location_description="苹果园东侧", latitude="45.781328", longitude="126.621378", status="ACTIVE")
        cls.plot2 = Plot.objects.create(orchard=cls.orchard2, name="B区", code="B01", location_description="梨园西侧", latitude="45.881328", longitude="126.721378", status="ACTIVE")
        cls.device1 = Device.objects.create(device_code="ORCHARD-A01-DEVICE-0001", device_name="温湿度传感器", device_type="temperature", orchard=cls.orchard1, plot=cls.plot1, status="ONLINE")
        cls.device1.set_token(DEVICE_TOKEN); cls.device1.save()
        cls.device2 = Device.objects.create(device_code="ORCHARD-B01-DEVICE-0002", device_name="梨园传感器", device_type="humidity", orchard=cls.orchard2, plot=cls.plot2, status="ONLINE")
        cls.device2.set_token(DEVICE_TOKEN); cls.device2.save()
        cls.admin = User.objects.create_user("admin_test", password=PASSWORD, role=cls.roles["SUPER_ADMIN"], is_superuser=True, is_staff=True)
        cls.security = User.objects.create_user("security_test", password=PASSWORD, role=cls.roles["SECURITY_ADMIN"])
        cls.orchard_admin = User.objects.create_user("orchard_test", password=PASSWORD, role=cls.roles["ORCHARD_ADMIN"])
        cls.normal = User.objects.create_user("normal_test", password=PASSWORD, role=cls.roles["NORMAL_USER"])
        cls.other = User.objects.create_user("other_test", password=PASSWORD, role=cls.roles["NORMAL_USER"])
        cls.orchard_admin.assigned_orchards.add(cls.orchard1)
        cls.normal.assigned_orchards.add(cls.orchard1)
        cls.other.assigned_orchards.add(cls.orchard1)
        cls.security.assigned_orchards.add(cls.orchard1, cls.orchard2)
        for key, value in {"query_rate_limit": 30, "sensitive_query_rate_limit": 10, "export_limit": 200, "risk_alert_threshold": 60, "failed_login_threshold": 3, "device_offline_timeout": 30}.items():
            SystemConfig.objects.create(key=key, name=key, value=str(value), value_type="INTEGER")
        AccessPolicy.objects.create(name="normal-view", role=cls.roles["NORMAL_USER"], orchard=cls.orchard1, operation="VIEW", effect="ALLOW")
        AccessPolicy.objects.create(name="normal-export", role=cls.roles["NORMAL_USER"], orchard=cls.orchard1, operation="EXPORT", effect="ALLOW")
        AccessPolicy.objects.create(name="normal-deny-raw", role=cls.roles["NORMAL_USER"], operation="RAW_VIEW", effect="DENY", priority=1)
        AccessPolicy.objects.create(name="orchard-update", role=cls.roles["ORCHARD_ADMIN"], orchard=cls.orchard1, operation="UPDATE", effect="ALLOW")
        SensitiveFieldDefinition.objects.create(name="手机号", field_name="contact_phone", field_type="phone", sensitivity_level="IMPORTANT", enabled=True)
        SensitiveFieldDefinition.objects.create(name="设备编号", field_name="device_code", field_type="device_code", sensitivity_level="SENSITIVE", enabled=True)
        SensitiveFieldDefinition.objects.create(name="坐标", field_name="coordinate", field_type="coordinate", sensitivity_level="IMPORTANT", enabled=True)
        SensitiveRule.objects.create(name="手机号正则", match_type="REGEX", pattern=r"(?<!\d)1[3-9]\d{9}(?!\d)", field_type="phone", sensitivity_level="IMPORTANT", priority=1)
        SensitiveRule.objects.create(name="设备编号字段", match_type="FIELD_NAME", pattern="device_code", field_type="device_code", sensitivity_level="SENSITIVE", priority=2)
        MaskingRule.objects.create(name="普通用户手机号", field_type="phone", masking_type="MASK", sensitivity_level="IMPORTANT", role=cls.roles["NORMAL_USER"], scene="ALL", priority=1)
        MaskingRule.objects.create(name="普通用户设备号", field_type="device_code", masking_type="MASK", sensitivity_level="SENSITIVE", role=cls.roles["NORMAL_USER"], scene="ALL", priority=1)
        MaskingRule.objects.create(name="普通用户时间", field_type="collection_time", masking_type="MASK", sensitivity_level="SENSITIVE", role=cls.roles["NORMAL_USER"], scene="ALL", priority=1)

    @classmethod
    def create_reading(cls, **overrides):
        defaults = {
            "orchard": cls.orchard1,
            "plot": cls.plot1,
            "device": cls.device1,
            "temperature": 26.5,
            "humidity": 62.1,
            "soil_moisture": 45.8,
            "light": 35000,
            "pest_alarm": False,
            "device_status": "ONLINE",
            "collection_time": timezone.now() - timedelta(minutes=1),
            "is_valid": True,
            "is_abnormal": False,
            "source_type": "HTTP",
            "payload_fingerprint": "fixture-" + str(SensorReading.objects.count()),
        }
        defaults.update(overrides)
        return SensorReading.objects.create(**defaults)


class BaseDataTestCase(BaseDataMixin, TestCase):
    """Shared isolated database fixture for cross-app business tests."""
