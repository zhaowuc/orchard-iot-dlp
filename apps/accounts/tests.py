from apps.audit.models import AuditLog, RiskEvent
from .models import LoginAttempt
from tests.base import BaseDataTestCase, PASSWORD


class AccountTests(BaseDataTestCase):
    def test_login_success_is_audited(self):
        response = self.client.post("/accounts/login/", {"username": self.normal.username, "password": PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LoginAttempt.objects.filter(username=self.normal.username, success=True).exists())
        self.assertTrue(AuditLog.objects.filter(action="LOGIN_SUCCESS", user=self.normal).exists())

    def test_login_failure_is_audited(self):
        response = self.client.post("/accounts/login/", {"username": self.normal.username, "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(LoginAttempt.objects.filter(username=self.normal.username, success=False).exists())
        self.assertTrue(AuditLog.objects.filter(action="LOGIN_FAILURE").exists())

    def test_repeated_failures_create_risk_event(self):
        for _ in range(3):
            self.client.post("/accounts/login/", {"username": self.normal.username, "password": "wrong"})
        self.assertTrue(RiskEvent.objects.filter(event_type="连续登录失败").exists())

    def test_disabled_user_cannot_login(self):
        self.normal.is_active = False
        self.normal.save(update_fields=["is_active"])
        response = self.client.post("/accounts/login/", {"username": self.normal.username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_normal_user_cannot_manage_users(self):
        self.client.force_login(self.normal)
        self.assertEqual(self.client.get("/accounts/users/").status_code, 403)

