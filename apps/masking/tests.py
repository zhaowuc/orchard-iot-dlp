from django.test import RequestFactory

from apps.dlp.export_services import ExportSecurityService
from .models import MaskingRule
from .services import MaskingService
from tests.base import BaseDataTestCase


class MaskingTests(BaseDataTestCase):
    def test_admin_receives_raw_phone(self):
        result = MaskingService.apply("13812345678", "phone", user=self.admin, sensitivity_level="IMPORTANT", orchard=self.orchard1, record=False)
        self.assertEqual(result, "13812345678")

    def test_normal_user_receives_masked_phone(self):
        result = MaskingService.apply("13812345678", "phone", user=self.normal, sensitivity_level="IMPORTANT", orchard=self.orchard1, record=False)
        self.assertEqual(result, "138****5678")

    def test_masking_examples(self):
        self.assertEqual(MaskingService.transform("ORCHARD-A01-DEVICE-0001", "device_code", "MASK"), "ORCHARD-A01-****-0001")
        self.assertEqual(MaskingService.transform("orchard_admin_001", "username", "MASK"), "orc***********001")
        self.assertEqual(MaskingService.transform("45.781328,126.621378", "coordinate", "GENERALIZE"), "45.78**,126.62**")
        self.assertEqual(MaskingService.transform("2026-08-11 18:32:16", "collection_time", "MASK"), "2026-08-11 **:**:**")

    def test_api_does_not_leak_to_normal_user(self):
        self.create_reading()
        self.client.force_login(self.normal)
        result = self.client.get("/data/api/readings/").json()["results"][0]
        self.assertNotEqual(result["device_code"], self.device1.device_code)
        self.assertIn("****", result["device_code"])

