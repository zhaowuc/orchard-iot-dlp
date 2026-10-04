import json
from django.core.management import call_command
from django.utils import timezone

from .models import SensorReading
from tests.base import BaseDataTestCase, DEVICE_TOKEN


class IoTTests(BaseDataTestCase):
    def payload(self, **updates):
        data = {"device_code": self.device1.device_code, "temperature": 26.5, "humidity": 62.1, "soil_moisture": 45.8, "light": 35000, "pest_alarm": False, "device_status": "ONLINE", "collection_time": timezone.now().isoformat()}
        data.update(updates)
        return data

    def post(self, payload, token=DEVICE_TOKEN):
        return self.client.post("/api/iot/data/", data=json.dumps(payload), content_type="application/json", HTTP_X_DEVICE_TOKEN=token)

    def test_normal_data_is_saved(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201)
        self.assertTrue(SensorReading.objects.get().is_valid)

    def test_abnormal_humidity_is_saved_and_marked(self):
        response = self.post(self.payload(humidity=150))
        self.assertEqual(response.status_code, 201)
        reading = SensorReading.objects.get()
        self.assertTrue(reading.is_abnormal)
        self.assertIn("humidity", reading.abnormal_reason)

    def test_unknown_device_is_rejected(self):
        self.assertEqual(self.post(self.payload(device_code="UNKNOWN")).status_code, 404)

    def test_invalid_token_is_rejected(self):
        self.assertEqual(self.post(self.payload(), token="wrong").status_code, 403)

    def test_duplicate_is_retained_and_marked(self):
        payload = self.payload()
        self.assertEqual(self.post(payload).status_code, 201)
        self.assertEqual(self.post(payload).status_code, 201)
        self.assertEqual(SensorReading.objects.count(), 2)
        self.assertTrue(SensorReading.objects.order_by("id").last().is_abnormal)
        self.assertIn("重复数据", SensorReading.objects.order_by("id").last().abnormal_reason)

    def test_simulator_command_creates_records(self):
        call_command("simulate_iot", count=2, interval=0)
        self.assertEqual(SensorReading.objects.count(), 2)

