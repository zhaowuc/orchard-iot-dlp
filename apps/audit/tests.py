from django.test import RequestFactory

from .models import AuditLog, RiskEvent, SecurityAlert
from .services import AuditService, RiskScoringService
from tests.base import BaseDataTestCase


class AuditRiskTests(BaseDataTestCase):
    def test_audit_service_records_request_context(self):
        request = RequestFactory().post("/masking/preview/", HTTP_USER_AGENT="test-agent")
        request.user = self.security
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        log = AuditService.log("MASKING_PREVIEW", user=self.security, request=request, message="测试")
        self.assertEqual(log.request_path, "/masking/preview/")
        self.assertEqual(log.ip_address, "127.0.0.1")

    def test_explainable_risk_score_and_level(self):
        score, breakdown = RiskScoringService.calculate(["large_export", "important_data", "sensitive_access", "repeated_anomaly"])
        self.assertEqual(score, 82)
        self.assertEqual(sum(item["score"] for item in breakdown), 82)
        self.assertEqual(RiskScoringService.level_for(score), "CRITICAL")

    def test_threshold_automatically_creates_alert(self):
        event = RiskScoringService.create_event("批量导出", ["large_export", "important_data", "sensitive_access"], user=self.normal)
        self.assertEqual(event.score, 70)
        self.assertTrue(SecurityAlert.objects.filter(event=event).exists())

    def test_security_admin_can_handle_alert_and_is_audited(self):
        event = RiskScoringService.create_event("严重异常", ["large_export", "important_data", "sensitive_access"], user=self.normal)
        alert = SecurityAlert.objects.get(event=event)
        self.client.force_login(self.security)
        response = self.client.post(f"/security/alerts/{alert.pk}/", {"status": "RESOLVED", "handling_comment": "已确认异常批量导出，限制用户操作。"})
        self.assertEqual(response.status_code, 302)
        alert.refresh_from_db()
        self.assertEqual(alert.handler, self.security)
        self.assertTrue(AuditLog.objects.filter(action="ALERT_HANDLE", user=self.security).exists())

    def test_normal_user_cannot_handle_alert(self):
        event = RiskScoringService.create_event("严重异常", ["large_export", "important_data", "sensitive_access"], user=self.normal)
        alert = SecurityAlert.objects.get(event=event)
        self.client.force_login(self.normal)
        self.assertEqual(self.client.get(f"/security/alerts/{alert.pk}/").status_code, 403)

