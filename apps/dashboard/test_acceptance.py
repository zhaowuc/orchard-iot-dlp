import hashlib
import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import Resolver404, resolve
from django.utils import timezone

from apps.accounts.models import LoginAttempt, User
from apps.audit.models import AuditLog, RiskEvent, SecurityAlert
from apps.audit.services import RiskScoringService
from apps.dashboard.models import SystemConfig
from apps.dashboard.views import _dashboard_payload
from apps.dlp.export_services import ExportSecurityService
from apps.dlp.models import AccessPolicy, ExportRecord, ExportRequest, QueryMonitor
from apps.dlp.services import AccessControlService, QueryLimitService
from apps.iot.models import SensorReading
from apps.masking.models import MaskingRule
from apps.masking.services import MaskingService
from apps.orchards.models import Device, Orchard
from apps.sensitive.models import SensitiveDetectionRecord, SensitiveFieldDefinition, SensitiveRule
from tests.base import BaseDataTestCase, DEVICE_TOKEN, PASSWORD


class IndependentAcceptanceTests(BaseDataTestCase):
    def request_for(self, user, path="/dlp/exports/"):
        request = RequestFactory().post(path, REMOTE_ADDR="127.0.0.1")
        request.user = user
        return request

    def iot_payload(self, **updates):
        payload = {
            "device_code": self.device1.device_code,
            "temperature": 26.5,
            "humidity": 62.1,
            "soil_moisture": 45.8,
            "light": 35000,
            "pest_alarm": False,
            "device_status": "ONLINE",
            "collection_time": timezone.now().isoformat(),
        }
        payload.update(updates)
        return payload

    def post_iot(self, payload, token=DEVICE_TOKEN):
        self.client.raise_request_exception = False
        return self.client.post(
            "/api/iot/data/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_TOKEN=token,
        )

    def test_debug_urlconf_never_exposes_private_media(self):
        with self.assertRaises(Resolver404):
            resolve("/media/exports/secret.csv")

    def test_login_next_rejects_external_redirect(self):
        response = self.client.post(
            "/accounts/login/?next=https://evil.example/steal",
            {"username": self.normal.username, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_anonymous_business_urls_require_login(self):
        urls = [
            "/", "/assets/orchards/", "/data/readings/", "/data/api/readings/",
            "/sensitive/fields/", "/masking/rules/", "/dlp/exports/",
            "/security/risks/", "/security/logs/", "/api/dashboard/summary/",
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, {302, 403})
                self.assertNotContains(response, "13812345678", status_code=response.status_code)

    def test_logout_invalidates_session(self):
        self.client.force_login(self.normal)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.post("/accounts/logout/").status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_normal_user_direct_get_and_post_to_security_urls_are_forbidden(self):
        self.client.force_login(self.normal)
        urls = [
            "/accounts/users/", "/accounts/roles/", "/sensitive/fields/",
            "/sensitive/rules/", "/masking/rules/", "/masking/preview/",
            "/dlp/policies/", "/dlp/queries/", "/security/logs/",
            "/security/risks/", "/security/alerts/", "/settings/",
        ]
        for url in urls:
            with self.subTest(method="GET", url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
            with self.subTest(method="POST", url=url):
                self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_csrf_is_enforced_on_security_post(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.security)
        response = csrf_client.post("/masking/rules/new/", {})
        self.assertEqual(response.status_code, 403)

    def test_xss_payload_is_escaped_in_asset_list(self):
        self.orchard1.name = "<script>alert(1)</script>"
        self.orchard1.save(update_fields=["name", "updated_at"])
        self.client.force_login(self.admin)
        content = self.client.get("/assets/orchards/").content.decode()
        self.assertNotIn("<script>alert(1)</script>", content)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", content)

    def test_sql_injection_search_does_not_bypass_scope(self):
        self.client.force_login(self.normal)
        response = self.client.get("/assets/orchards/", {"q": "' OR '1'='1"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.orchard2.name)

    def test_orchard_admin_cannot_link_device_to_foreign_plot(self):
        self.client.force_login(self.orchard_admin)
        response = self.client.post(
            f"/assets/devices/{self.device1.pk}/edit/",
            {
                "device_code": self.device1.device_code,
                "device_name": self.device1.device_name,
                "device_type": self.device1.device_type,
                "orchard": self.orchard1.pk,
                "plot": self.plot2.pk,
                "gateway": "",
                "status": "ONLINE",
                "manufacturer": "test",
                "description": "test",
                "demo_token": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.device1.refresh_from_db()
        self.assertEqual(self.device1.plot_id, self.plot1.pk)

    def test_iot_rejects_non_object_json_without_500(self):
        for payload in ([], None, "text", 123):
            with self.subTest(payload=payload):
                response = self.post_iot(payload)
                self.assertEqual(response.status_code, 400)

    def test_iot_rejects_non_finite_number_without_500(self):
        response = self.post_iot(self.iot_payload(humidity=float("nan")))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_iot_string_false_is_not_saved_as_true(self):
        response = self.post_iot(self.iot_payload(pest_alarm="false"))
        self.assertEqual(response.status_code, 201)
        self.assertFalse(SensorReading.objects.get().pest_alarm)

    def test_iot_time_and_range_errors_are_persisted(self):
        response = self.post_iot(
            self.iot_payload(
                humidity=150,
                soil_moisture=-10,
                light=999999999,
                collection_time=(timezone.now() + timedelta(days=1)).isoformat(),
            )
        )
        self.assertEqual(response.status_code, 201)
        reading = SensorReading.objects.get()
        self.assertTrue(reading.is_abnormal)
        for marker in ("humidity", "soil_moisture", "light", "采集时间"):
            self.assertIn(marker, reading.abnormal_reason)

    def test_iot_ingest_creates_real_detection_records(self):
        SensitiveFieldDefinition.objects.create(
            name="采集时间", field_name="collection_time", field_type="collection_time",
            sensitivity_level="SENSITIVE", enabled=True,
        )
        SensitiveRule.objects.create(
            name="采集时间字段", match_type="FIELD_NAME", pattern="collection_time",
            field_type="collection_time", sensitivity_level="SENSITIVE", priority=2,
        )
        response = self.post_iot(self.iot_payload())
        self.assertEqual(response.status_code, 201)
        reading_id = response.json()["id"]
        records = SensitiveDetectionRecord.objects.filter(source_type="SensorReading", source_object_id=str(reading_id))
        self.assertTrue(records.filter(field_name="device_code", matched_rule__isnull=False).exists())
        self.assertTrue(records.filter(field_name="collection_time").exists())

    def test_masking_all_algorithms_and_special_inputs_do_not_raise(self):
        for algorithm in MaskingRule.MaskingTypes.values:
            for value in (None, "", "短", "🙂Unicode", "x" * 500):
                with self.subTest(algorithm=algorithm, value=value):
                    result = MaskingService.transform(value or "", "generic", algorithm)
                    self.assertIsInstance(result, str)

    def test_generalize_honors_configured_replacement(self):
        result = MaskingService.transform(
            "45.781328,126.621378",
            "coordinate",
            MaskingRule.MaskingTypes.GENERALIZE,
            {"replacement": "黑龙江省"},
        )
        self.assertEqual(result, "黑龙江省")

    def test_global_masking_rule_is_applied(self):
        MaskingRule.objects.create(
            name="global-email-hash", field_type="email", masking_type="HASH",
            sensitivity_level="SENSITIVE", role=None, scene="ALL", priority=1,
        )
        result = MaskingService.apply(
            "person@example.com", "email", user=self.normal,
            sensitivity_level="SENSITIVE", orchard=self.orchard1, record=False,
        )
        self.assertTrue(result.startswith("HASH_"))

    def test_database_keeps_raw_phone_but_normal_html_masks_it(self):
        self.assertEqual(Orchard.objects.get(pk=self.orchard1.pk).contact_phone, "13812345678")
        self.client.force_login(self.normal)
        content = self.client.get("/assets/orchards/").content.decode()
        self.assertNotIn("13812345678", content)
        self.assertIn("138****5678", content)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/assets/orchards/"), "13812345678")

    def test_raw_view_policy_honors_time_window(self):
        AccessPolicy.objects.filter(role=self.normal.role, operation="RAW_VIEW").delete()
        outside = (timezone.localtime() + timedelta(hours=2)).time().replace(microsecond=0)
        AccessPolicy.objects.create(
            name="future-window", role=self.normal.role, orchard=self.orchard1,
            operation="RAW_VIEW", effect="ALLOW", start_time=outside, end_time=outside,
            priority=1,
        )
        self.assertFalse(AccessControlService.can_view_raw(self.normal, orchard=self.orchard1))

    def test_query_limit_boundary_uses_runtime_config(self):
        SystemConfig.objects.filter(key="query_rate_limit").update(value="2")
        request = self.request_for(self.normal, "/data/readings/")
        QueryLimitService.record_and_check(request)
        QueryLimitService.record_and_check(request)
        self.assertEqual(QueryMonitor.objects.filter(blocked=False).count(), 2)
        with self.assertRaises(PermissionDenied):
            QueryLimitService.record_and_check(request)
        self.assertEqual(QueryMonitor.objects.filter(blocked=True).count(), 1)

    def test_system_config_form_rejects_invalid_typed_value(self):
        config = SystemConfig.objects.get(key="query_rate_limit")
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/settings/{config.pk}/edit/",
            {"name": config.name, "value": "not-an-integer", "value_type": "INTEGER", "description": "x", "editable": "on"},
        )
        self.assertEqual(response.status_code, 200)
        config.refresh_from_db()
        self.assertNotEqual(config.value, "not-an-integer")

    def test_risk_score_boundaries_and_clamp(self):
        expected = {0: "LOW", 29: "LOW", 30: "MEDIUM", 59: "MEDIUM", 60: "HIGH", 79: "HIGH", 80: "CRITICAL", 100: "CRITICAL"}
        for score, level in expected.items():
            self.assertEqual(RiskScoringService.level_for(score), level)
        score, _ = RiskScoringService.calculate([{"key": "custom", "score": 999}])
        self.assertEqual(score, 100)

    def test_risk_score_does_not_double_count_same_factor(self):
        score, breakdown = RiskScoringService.calculate(["large_export", "sensitive_access", "large_export"])
        self.assertEqual(score, 50)
        self.assertEqual([item["key"] for item in breakdown], ["large_export", "sensitive_access"])

    def test_repeated_same_risk_does_not_create_alert_storm(self):
        for _ in range(3):
            RiskScoringService.create_event(
                "重复高风险查询", ["large_export", "important_data", "sensitive_access"], user=self.normal,
            )
        self.assertEqual(SecurityAlert.objects.filter(user=self.normal, title__contains="重复高风险查询").count(), 1)
        self.assertEqual(RiskEvent.objects.filter(user=self.normal, event_type="重复高风险查询").count(), 3)

    def test_repeated_login_failures_can_reach_alert_threshold(self):
        SystemConfig.objects.filter(key="failed_login_threshold").update(value="3")
        for _ in range(8):
            self.client.post("/accounts/login/", {"username": self.normal.username, "password": "wrong"})
        self.assertEqual(LoginAttempt.objects.filter(username=self.normal.username, success=False).count(), 8)
        self.assertTrue(RiskEvent.objects.filter(event_type="连续登录失败").exists())
        self.assertTrue(SecurityAlert.objects.filter(user=self.normal).exists())
        self.assertFalse(AuditLog.objects.filter(details__has_key="password").exists())

    def test_export_csv_escapes_formula_cells_and_hash_matches(self):
        self.orchard1.name = "=1+1"
        self.orchard1.save(update_fields=["name", "updated_at"])
        self.create_reading(abnormal_reason="@TEST", is_abnormal=True)
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(MEDIA_ROOT=temp):
                _, record = ExportSecurityService.request_export(
                    self.request_for(self.normal),
                    {"orchard": self.orchard1, "plot": None, "device": None, "start_time": None, "end_time": None, "sensitivity_level": "SENSITIVE"},
                )
                path = Path(temp) / record.file_path
                content = path.read_text(encoding="utf-8-sig")
                self.assertIn("'=1+1", content)
                self.assertIn("'@TEST", content)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record.file_hash)

    def test_export_form_rejects_reversed_dates_and_cross_orchard_device(self):
        self.client.force_login(self.normal)
        response = self.client.post(
            "/dlp/exports/",
            {
                "orchard": self.orchard1.pk,
                "device": self.device2.pk,
                "start_time": "2026-08-12T10:00",
                "end_time": "2026-08-11T10:00",
                "sensitivity_level": "SENSITIVE",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ExportRequest.objects.count(), 0)

    def test_rejected_request_cannot_be_generated(self):
        export_request = ExportRequest.objects.create(user=self.normal, orchard=self.orchard1, status="REJECTED")
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(MEDIA_ROOT=temp):
                with self.assertRaises(PermissionDenied):
                    ExportSecurityService.generate(export_request)

    def test_expired_export_record_cannot_be_downloaded(self):
        self.create_reading()
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(MEDIA_ROOT=temp):
                export_request, record = ExportSecurityService.request_export(
                    self.request_for(self.normal),
                    {"orchard": self.orchard1, "plot": None, "device": None, "start_time": None, "end_time": None, "sensitivity_level": "SENSITIVE"},
                )
                export_request.expires_at = timezone.now() - timedelta(seconds=1)
                export_request.save(update_fields=["expires_at", "updated_at"])
                self.client.force_login(self.normal)
                response = self.client.get(f"/dlp/exports/{record.export_id}/download/")
                self.assertEqual(response.status_code, 403)

    def test_dashboard_does_not_leak_other_users_security_event(self):
        RiskScoringService.create_event(
            "OTHER-USER-SECRET-EVENT", ["large_export", "important_data", "sensitive_access"], user=self.other,
        )
        self.client.force_login(self.normal)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "OTHER-USER-SECRET-EVENT")

    def test_dashboard_changes_after_real_risk_and_offline_timeout(self):
        self.device1.last_seen_at = timezone.now()
        self.device1.status = Device.DeviceStatus.ONLINE
        self.device1.save(update_fields=["last_seen_at", "status", "updated_at"])
        before, _ = _dashboard_payload(self.normal, 7)
        RiskScoringService.create_event("动态测试", ["sensitive_access"], user=self.normal)
        after, _ = _dashboard_payload(self.normal, 7)
        self.assertEqual(after["today_risks"], before["today_risks"] + 1)
        SystemConfig.objects.filter(key="device_offline_timeout").update(value="0")
        offline, _ = _dashboard_payload(self.normal, 7)
        self.assertGreaterEqual(offline["device_offline"], 1)

    def test_all_four_demo_roles_can_authenticate(self):
        for user in (self.admin, self.security, self.orchard_admin, self.normal):
            self.client.logout()
            with self.subTest(user=user.username):
                response = self.client.post("/accounts/login/", {"username": user.username, "password": PASSWORD})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_security_admin_cannot_modify_business_assets(self):
        self.client.force_login(self.security)
        self.assertEqual(self.client.get(f"/assets/devices/{self.device1.pk}/edit/").status_code, 403)
        self.assertEqual(self.client.post(f"/assets/devices/{self.device1.pk}/edit/", {}).status_code, 403)

    def test_admin_menu_targets_are_live(self):
        self.client.force_login(self.admin)
        urls = [
            "/", "/assets/orchards/", "/assets/plots/", "/assets/gateways/",
            "/assets/devices/", "/assets/sources/", "/data/readings/",
            "/sensitive/fields/", "/sensitive/rules/", "/sensitive/detections/",
            "/masking/rules/", "/masking/preview/", "/masking/records/",
            "/dlp/policies/", "/dlp/queries/", "/dlp/exports/",
            "/security/risks/", "/security/alerts/", "/security/logs/",
            "/accounts/users/", "/accounts/roles/", "/settings/",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_http_methods_do_not_mutate_on_get(self):
        self.assertEqual(self.client.get("/api/iot/data/").status_code, 405)
        self.client.force_login(self.normal)
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_iot_auth_content_type_body_size_and_invalid_status(self):
        payload = self.iot_payload()
        self.assertEqual(self.post_iot(payload, token="").status_code, 403)
        self.assertEqual(self.post_iot(payload, token="wrong").status_code, 403)
        self.assertEqual(self.client.post("/api/iot/data/", data="{}", content_type="text/plain").status_code, 415)
        oversized = {"device_code": self.device1.device_code, "collection_time": timezone.now().isoformat(), "padding": "x" * 70000}
        self.assertEqual(self.post_iot(oversized).status_code, 413)
        response = self.post_iot(self.iot_payload(device_status="HACKED"))
        self.assertEqual(response.status_code, 201)
        reading = SensorReading.objects.get()
        self.assertTrue(reading.is_abnormal)
        self.assertEqual(reading.device_status, Device.DeviceStatus.ABNORMAL)

    def test_sensitive_level_change_affects_dynamic_view(self):
        definition = SensitiveFieldDefinition.objects.get(field_name="contact_phone")
        definition.sensitivity_level = "PUBLIC"
        definition.save(update_fields=["sensitivity_level", "updated_at"])
        self.client.force_login(self.normal)
        self.assertContains(self.client.get("/assets/orchards/"), "13812345678")

    def test_redetection_updates_existing_record_after_rule_change(self):
        from apps.sensitive.services import SensitiveDetectionService

        result = SensitiveDetectionService.detect("device_code", self.device1.device_code, source_type="acceptance", source_object_id="1")
        record = result["record"]
        rule = SensitiveRule.objects.get(name="设备编号字段")
        rule.sensitivity_level = "IMPORTANT"
        rule.save(update_fields=["sensitivity_level", "updated_at"])
        SensitiveDetectionService.detect("device_code", self.device1.device_code, source_type="acceptance", source_object_id="1")
        record.refresh_from_db()
        self.assertEqual(record.sensitivity_level, "IMPORTANT")
        self.assertEqual(SensitiveDetectionRecord.objects.filter(source_type="acceptance", source_object_id="1").count(), 1)

    def test_repeated_export_submission_is_idempotent(self):
        self.create_reading()
        filters = {"orchard": self.orchard1, "plot": None, "device": None, "start_time": None, "end_time": None, "sensitivity_level": "SENSITIVE"}
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(MEDIA_ROOT=temp):
                first, first_record = ExportSecurityService.request_export(self.request_for(self.normal), filters)
                second, second_record = ExportSecurityService.request_export(self.request_for(self.normal), filters)
                self.assertEqual(first.export_id, second.export_id)
                self.assertEqual(first_record.export_id, second_record.export_id)
                self.assertEqual(ExportRequest.objects.count(), 1)
                self.assertEqual(ExportRecord.objects.count(), 1)

    def test_tampered_export_fails_integrity_check(self):
        self.create_reading()
        filters = {"orchard": self.orchard1, "plot": None, "device": None, "start_time": None, "end_time": None, "sensitivity_level": "SENSITIVE"}
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(MEDIA_ROOT=temp):
                _, record = ExportSecurityService.request_export(self.request_for(self.normal), filters)
                path = Path(temp) / record.file_path
                path.write_text("tampered", encoding="utf-8")
                self.client.force_login(self.normal)
                response = self.client.get(f"/dlp/exports/{record.export_id}/download/")
                self.assertEqual(response.status_code, 403)
                self.assertTrue(AuditLog.objects.filter(action="EXPORT_INTEGRITY_FAILURE", result="BLOCKED").exists())

    def test_alert_duplicate_submission_is_idempotent(self):
        event = RiskScoringService.create_event("告警重复提交", ["large_export", "important_data", "sensitive_access"], user=self.normal)
        alert = SecurityAlert.objects.get(event=event)
        self.client.force_login(self.security)
        payload = {"status": "RESOLVED", "handling_comment": "已处置"}
        self.assertEqual(self.client.post(f"/security/alerts/{alert.pk}/", payload).status_code, 302)
        self.assertEqual(self.client.post(f"/security/alerts/{alert.pk}/", payload).status_code, 302)
        self.assertEqual(AuditLog.objects.filter(action="ALERT_HANDLE", object_id=str(alert.pk)).count(), 1)

    def test_export_approval_rolls_back_if_generation_fails(self):
        request_obj = ExportRequest.objects.create(user=self.normal, orchard=self.orchard1, status="PENDING")
        self.client.force_login(self.security)
        with patch("apps.dlp.views.ExportSecurityService.generate", side_effect=RuntimeError("disk failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    f"/dlp/exports/{request_obj.export_id}/decision/",
                    {"decision": "APPROVE", "comment": "批准"},
                )
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, "PENDING")
        self.assertFalse(AuditLog.objects.filter(action="EXPORT_APPROVAL", object_id=str(request_obj.export_id)).exists())

    def test_path_traversal_and_malformed_export_id_are_not_resolved(self):
        self.client.force_login(self.normal)
        for url in ("/dlp/exports/../db.sqlite3/download/", "/dlp/exports/not-a-uuid/download/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)


class EmptyStateAcceptanceTests(TestCase):
    def test_empty_dashboard_and_invalid_pagination_do_not_500(self):
        from apps.accounts.models import Role

        role = Role.objects.create(name="普通用户", code="NORMAL_USER")
        user = User.objects.create_user("empty_user", password=PASSWORD, role=role)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/data/readings/?page=abc").status_code, 200)
        payload = self.client.get("/api/dashboard/summary/?days=invalid").json()
        self.assertEqual(payload["cards"]["device_total"], 0)
        self.assertEqual(payload["charts"]["temperature"], [])
