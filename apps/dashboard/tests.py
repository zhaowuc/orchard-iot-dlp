from django.test import override_settings

from apps.audit.models import RiskEvent, SecurityAlert
from apps.audit.services import RiskScoringService
from apps.iot.models import SensorReading
from .views import _dashboard_payload
from tests.base import BaseDataTestCase


class DashboardTests(BaseDataTestCase):
    def test_dashboard_statistics_match_database(self):
        self.create_reading()
        RiskScoringService.create_event("测试风险", ["large_export", "important_data", "sensitive_access"], user=self.normal)
        cards, charts = _dashboard_payload(self.admin, 7)
        self.assertEqual(cards["device_total"], 2)
        self.assertEqual(cards["today_readings"], 1)
        self.assertEqual(cards["pending_alerts"], SecurityAlert.objects.filter(status="PENDING").count())
        self.assertIn("temperature", charts)

    def test_dashboard_requires_authentication(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_dashboard_html_uses_real_counts(self):
        self.create_reading()
        self.client.force_login(self.admin)
        response = self.client.get("/")
        self.assertContains(response, "今日采集数据")
        self.assertContains(response, "真实 SensorReading")

    def test_dashboard_api_requires_authentication(self):
        self.assertEqual(self.client.get("/api/dashboard/summary/").status_code, 302)

    @override_settings(DEBUG=False)
    def test_production_404_uses_custom_error_page(self):
        self.client.force_login(self.admin)
        response = self.client.get("/missing-production-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "页面不存在", status_code=404)
