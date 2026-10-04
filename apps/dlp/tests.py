import tempfile
from pathlib import Path

from django.test import RequestFactory, override_settings

from apps.audit.models import AuditLog, RiskEvent
from apps.dashboard.models import SystemConfig
from .export_services import ExportSecurityService
from .models import ExportRecord, ExportRequest, QueryMonitor
from .services import QueryLimitService
from tests.base import BaseDataTestCase


class DLPTests(BaseDataTestCase):
    def request_for(self, user, path="/dlp/exports/"):
        request = RequestFactory().post(path)
        request.user = user
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        return request

    def test_query_limit_creates_risk_and_blocks(self):
        SystemConfig.objects.filter(key="query_rate_limit").update(value="1")
        request = self.request_for(self.normal, "/data/readings/")
        QueryLimitService.record_and_check(request, record_count=1)
        with self.assertRaisesMessage(Exception, "查询频率超过"):
            QueryLimitService.record_and_check(request, record_count=1)
        self.assertTrue(QueryMonitor.objects.filter(blocked=True).exists())
        self.assertTrue(RiskEvent.objects.filter(event_type="查询频率异常").exists())

    def test_small_export_is_generated_and_masked(self):
        self.create_reading()
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(MEDIA_ROOT=temp):
                export_request, record = ExportSecurityService.request_export(self.request_for(self.normal), {"orchard": self.orchard1, "plot": None, "device": None, "start_time": None, "end_time": None, "sensitivity_level": "SENSITIVE"})
                self.assertEqual(export_request.status, "COMPLETED")
                content = (Path(temp) / record.file_path).read_text(encoding="utf-8-sig")
                self.assertIn("ORCHARD-A01-****-0001", content)
                self.assertNotIn(self.device1.device_code, content)
                self.assertIn("EXPORT_ID", content)

    def test_large_export_enters_approval(self):
        SystemConfig.objects.filter(key="export_limit").update(value="1")
        self.create_reading()
        self.create_reading(payload_fingerprint="second")
        export_request, record = ExportSecurityService.request_export(self.request_for(self.normal), {"orchard": self.orchard1, "plot": None, "device": None, "start_time": None, "end_time": None, "sensitivity_level": "SENSITIVE"})
        self.assertEqual(export_request.status, "PENDING")
        self.assertIsNone(record)
        self.assertTrue(RiskEvent.objects.filter(user=self.normal).exists())

    def test_other_user_cannot_download_export_id(self):
        self.create_reading()
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(MEDIA_ROOT=temp):
                _, record = ExportSecurityService.request_export(self.request_for(self.normal), {"orchard": self.orchard1, "plot": None, "device": None, "start_time": None, "end_time": None, "sensitivity_level": "SENSITIVE"})
                self.client.force_login(self.other)
                response = self.client.get(f"/dlp/exports/{record.export_id}/download/")
                self.assertEqual(response.status_code, 403)
                self.assertTrue(AuditLog.objects.filter(action="UNAUTHORIZED_EXPORT_DOWNLOAD").exists())

    def test_normal_user_security_management_url_is_forbidden(self):
        self.client.force_login(self.normal)
        self.assertEqual(self.client.get("/dlp/policies/").status_code, 403)

