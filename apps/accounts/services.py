from datetime import timedelta

from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import AuditService, RiskScoringService, client_ip
from .models import LoginAttempt


class LoginAuditService:
    @classmethod
    def record(cls, request, username, success, user=None, reason=""):
        attempt = LoginAttempt.objects.create(
            username=username[:150],
            user=user,
            ip_address=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            success=success,
            reason=reason[:200],
        )
        audit = AuditService.log(
            "LOGIN_SUCCESS" if success else "LOGIN_FAILURE",
            user=user,
            request=request,
            username_snapshot=username[:150],
            result=AuditLog.Results.SUCCESS if success else AuditLog.Results.FAILURE,
            message="登录成功" if success else (reason or "用户名或密码错误"),
        )
        if not success:
            from apps.dashboard.models import SystemConfig

            threshold = SystemConfig.get_value("failed_login_threshold", 5)
            count = LoginAttempt.objects.filter(username=username, success=False, created_at__gte=timezone.now() - timedelta(minutes=10)).count()
            if count >= threshold:
                RiskScoringService.create_event(
                    "连续登录失败",
                    [{"key": "failed_login", "score": min(15 + count * 5, 60)}, "repeated_anomaly"],
                    user=user,
                    audit_log=audit,
                    details={"username": username, "failures_in_10m": count},
                )
        return attempt
