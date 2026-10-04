from .models import SensitiveDetectionRecord
from .services import SensitiveDetectionService
from tests.base import BaseDataTestCase


class SensitiveDetectionTests(BaseDataTestCase):
    def test_phone_regex_detection(self):
        result = SensitiveDetectionService.detect("value", "13812345678", source_type="test", source_object_id="1")
        self.assertTrue(result["is_sensitive"])
        self.assertEqual(result["field_type"], "phone")
        self.assertEqual(result["sensitivity_level"], "IMPORTANT")

    def test_device_field_detection(self):
        result = SensitiveDetectionService.detect("device_code", "ORCHARD-A01-DEVICE-0001", source_type="test", source_object_id="2")
        self.assertEqual(result["sensitivity_level"], "SENSITIVE")
        self.assertTrue(SensitiveDetectionRecord.objects.filter(field_name="device_code").exists())

    def test_public_unknown_field(self):
        result = SensitiveDetectionService.detect("temperature", "26.5", source_type="test")
        self.assertFalse(result["is_sensitive"])
        self.assertEqual(result["sensitivity_level"], "PUBLIC")

    def test_four_level_classification_choices(self):
        from .models import SensitivityLevel
        self.assertEqual(set(SensitivityLevel.values), {"PUBLIC", "INTERNAL", "SENSITIVE", "IMPORTANT"})

