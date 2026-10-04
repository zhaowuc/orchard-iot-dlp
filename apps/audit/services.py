import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .middleware import current_request
from .models import AuditLog, RiskEvent, SecurityAlert


logger = logging.getLogger(__name__)


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


class AuditService:
    @classmethod
    def log(cls, action, *, user=None, request=None, result=AuditLog.Results.SUCCESS, message="", **kwargs):
        request = request or current_request.get()
        if user is None and request is not None and getattr(request, "user", None) and request.user.is_authenticated:
            user = request.user
        username_snapshot = kwargs.pop("username_snapshot", "")
        try:
            return AuditLog.objects.create(
                user=user,
                username_snapshot=getattr(user, "username", "") or username_snapshot,
                ip_address=client_ip(request),
                user_agent=(request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""),
                request_path=(request.path[:500] if request else ""),
                http_method=(request.method[:12] if request else ""),
                action=action,
                result=result,
                message=message,
                **kwargs,
            )
        except Exception:
            logger.exception("Business audit write failed for action=%s", action)
            return None


class RiskScoringService:
    LEVELS = ((80, RiskEvent.Levels.CRITICAL), (60, RiskEvent.Levels.HIGH), (30, RiskEvent.Levels.MEDIUM), (0, RiskEvent.Levels.LOW))
    FACTOR_WEIGHTS = {
        "high_frequency_query": 25,
        "sensitive_access": 20,
        "large_export": 30,
        "unauthorized_orchard": 30,
        "failed_login": 15,
        "off_hours": 10,
        "repeated_anomaly": 12,
        "important_data": 20,
    }
    FACTOR_LABELS = {
        "high_frequency_query": "敏感数据高频查询",
        "sensitive_access": "敏感数据访问",
        "large_export": "大规模导出",
        "unauthorized_orchard": "跨果园越权尝试",
        "failed_login": "连续登录失败",
        "off_hours": "异常操作时段",
        "repeated_anomaly": "重复触发异常",
        "important_data": "重要数据访问",
    }

    @classmethod
    def calculate(cls, factors):
        breakdown = []
        total = 0
        seen = set()
        for item in factors:
            if isinstance(item, str):
                key, custom_score = item, None
            else:
                key, custom_score = item.get("key"), item.get("score")
            if not key or key in seen:
                continue
            seen.add(key)
            score = int(custom_score if custom_score is not None else cls.FACTOR_WEIGHTS.get(key, 0))
            if score <= 0:
                continue
            breakdown.append({"key": key, "label": cls.FACTOR_LABELS.get(key, key), "score": score})
            total += score
        return min(total, 100), breakdown

    @classmethod
    def level_for(cls, score):
        for threshold, level in cls.LEVELS:
            if score >= threshold:
                return level
        return RiskEvent.Levels.LOW

    @classmethod
    @transaction.atomic
    def create_event(cls, event_type, factors, *, user=None, audit_log=None, details=None):
        from apps.dashboard.models import SystemConfig

        score, breakdown = cls.calculate(factors)
        reason = "；".join(f"{item['label']} +{item['score']}" for item in breakdown) or "规则检测事件"
        event = RiskEvent.objects.create(
            user=user,
            event_type=event_type,
            score=score,
            risk_level=cls.level_for(score),
            reason=reason,
            details={"breakdown": breakdown, **(details or {})},
            related_audit_log=audit_log,
        )
        if audit_log is not None and audit_log.risk_score != score:
            audit_log.risk_score = score
            audit_log.save(update_fields=["risk_score", "updated_at"])
        threshold = SystemConfig.get_value("risk_alert_threshold", 60)
        if score >= threshold:
            cooldown_start = timezone.now() - timedelta(minutes=5)
            duplicate = SecurityAlert.objects.filter(
                user=user,
                event__event_type=event_type,
                status__in=[SecurityAlert.Status.PENDING, SecurityAlert.Status.PROCESSING],
                created_at__gte=cooldown_start,
            ).first()
            if duplicate:
                duplicate.score = max(duplicate.score, score)
                duplicate.risk_level = cls.level_for(duplicate.score)
                duplicate.description = f"5 分钟内重复触发，最近风险总分 {score}。{reason}"
                duplicate.save(update_fields=["score", "risk_level", "description", "updated_at"])
            else:
                SecurityAlert.objects.create(
                    event=event,
                    user=user,
                    risk_level=event.risk_level,
                    score=score,
                    title=f"{event.get_risk_level_display()}：{event_type}",
                    description=f"风险总分 {score}。{reason}",
                )
        return event


class BehaviorBaselineService:
    @classmethod
    def extra_factors(cls, user, *, orchard=None, export_size=0):
        factors = []
        now = timezone.localtime()
        if now.hour < 5 or now.hour >= 23:
            factors.append("off_hours")
        if user and orchard and user.is_authenticated:
            usual = user.audit_logs.filter(orchard=orchard, created_at__gte=timezone.now() - timedelta(days=30)).exists()
            if not usual and user.audit_logs.filter(created_at__gte=timezone.now() - timedelta(days=30)).exists():
                factors.append({"key": "repeated_anomaly", "score": 8})
        if export_size > 500:
            factors.append("large_export")
        return factors
