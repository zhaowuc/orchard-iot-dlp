from apps.audit.models import AuditLog, RiskEvent
from tests.base import BaseDataTestCase


class OrchardPermissionTests(BaseDataTestCase):
    def test_orchard_admin_only_sees_assigned_orchard(self):
        self.client.force_login(self.orchard_admin)
        content = self.client.get("/assets/orchards/").content.decode()
        self.assertIn(self.orchard1.name, content)
        self.assertNotIn(self.orchard2.name, content)

    def test_normal_user_cannot_edit_asset(self):
        self.client.force_login(self.normal)
        self.assertEqual(self.client.get(f"/assets/devices/{self.device1.pk}/edit/").status_code, 403)

    def test_orchard_admin_idor_is_blocked_and_audited(self):
        self.client.force_login(self.orchard_admin)
        response = self.client.get(f"/assets/devices/{self.device2.pk}/edit/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action="UNAUTHORIZED_ORCHARD_ACCESS", user=self.orchard_admin).exists())
        self.assertTrue(RiskEvent.objects.filter(user=self.orchard_admin).exists())

    def test_normal_asset_list_masks_sensitive_values(self):
        self.client.force_login(self.normal)
        content = self.client.get("/assets/orchards/").content.decode()
        self.assertNotIn("13812345678", content)
        self.assertIn("138****5678", content)

