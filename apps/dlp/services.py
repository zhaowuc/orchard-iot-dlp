from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.audit.services import AuditService, BehaviorBaselineService, RiskScoringService, client_ip
from apps.dashboard.models import SystemConfig
from .models import AccessPolicy, QueryMonitor


class AccessControlService:
    SECURITY_ROLES = {Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN}
    ASSET_MANAGER_ROLES = {Role.Codes.SUPER_ADMIN, Role.Codes.ORCHARD_ADMIN}

    @staticmethod
    def _within_time_window(policy):
        if not policy.start_time or not policy.end_time:
            return True
        local_time = timezone.localtime().time()
        if policy.start_time <= policy.end_time:
            return policy.start_time <= local_time <= policy.end_time
        return local_time >= policy.start_time or local_time <= policy.end_time

    @classmethod
    def orchard_queryset(cls, user, queryset=None):
        from apps.orchards.models import Orchard

        queryset = queryset if queryset is not None else Orchard.objects.all()
        if user.is_superuser or user.role_code in cls.SECURITY_ROLES:
            return queryset
        assigned = queryset.filter(authorized_users=user)
        allowed_ids = [
            orchard.pk
            for orchard in assigned
            if cls.can_access_orchard(user, orchard, AccessPolicy.Operations.VIEW)
        ]
        return queryset.filter(pk__in=allowed_ids)

    @classmethod
    def can_access_orchard(cls, user, orchard, operation=AccessPolicy.Operations.VIEW):
        if not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser or user.role_code in cls.SECURITY_ROLES:
            return True
        if not user.assigned_orchards.filter(pk=orchard.pk).exists():
            return False
        policies = AccessPolicy.objects.filter(enabled=True, role=user.role, operation=operation).filter(Q(orchard__isnull=True) | Q(orchard=orchard)).order_by("priority")
        first = policies.first()
        if first:
            if not cls._within_time_window(first):
                return False
            return first.effect == AccessPolicy.Effects.ALLOW
        if operation in {AccessPolicy.Operations.VIEW, AccessPolicy.Operations.EXPORT}:
            return True
        return user.role_code == Role.Codes.ORCHARD_ADMIN

    @classmethod
    def require_orchard(cls, user, orchard, operation=AccessPolicy.Operations.VIEW, request=None):
        if cls.can_access_orchard(user, orchard, operation):
            return True
        audit = AuditService.log(
            "UNAUTHORIZED_ORCHARD_ACCESS",
            user=user,
            request=request,
            result=AuditLog.Results.BLOCKED,
            orchard=orchard,
            message=f"拒绝访问未授权果园：{orchard.code}",
        )
        RiskScoringService.create_event("跨果园越权访问", ["unauthorized_orchard", "sensitive_access"], user=user, audit_log=audit, details={"orchard_id": orchard.pk})
        raise PermissionDenied("无权访问该果园")

    @classmethod
    def require_roles(cls, user, *roles):
        if not user.is_authenticated or not user.is_active or not user.has_role(*roles):
            raise PermissionDenied("当前角色无权执行此操作")

    @classmethod
    def can_view_raw(cls, user, *, orchard=None, sensitivity_level="SENSITIVE"):
        if user.is_superuser or user.role_code in cls.SECURITY_ROLES:
            return True
        if not user.role_id:
            return False
        policies = AccessPolicy.objects.filter(
            enabled=True,
            role=user.role,
            operation=AccessPolicy.Operations.RAW_VIEW,
        ).filter(Q(orchard__isnull=True) | Q(orchard=orchard)).filter(Q(sensitivity_level="") | Q(sensitivity_level=sensitivity_level)).order_by("priority")
        policy = policies.first()
        return bool(
            policy
            and cls._within_time_window(policy)
            and policy.effect == AccessPolicy.Effects.ALLOW
        )


class QueryLimitService:
    @classmethod
    def record_and_check(cls, request, *, orchard=None, plot=None, record_count=0, sensitive_count=0):
        user = request.user if request.user.is_authenticated else None
        now = timezone.now()
        period_start = now - timedelta(seconds=60)
        query_limit = SystemConfig.get_value("query_rate_limit", 30)
        sensitive_limit = SystemConfig.get_value("sensitive_query_rate_limit", 10)
        recent = QueryMonitor.objects.filter(user=user, created_at__gte=period_start)
        blocked = recent.count() >= query_limit or (sensitive_count and recent.filter(sensitive_count__gt=0).count() >= sensitive_limit)
        monitor = QueryMonitor.objects.create(
            user=user,
            ip_address=client_ip(request),
            path=request.path,
            orchard=orchard,
            plot=plot,
            record_count=record_count,
            sensitive_count=sensitive_count,
            blocked=blocked,
        )
        AuditService.log(
            "DATA_QUERY",
            user=user,
            request=request,
            result=AuditLog.Results.BLOCKED if blocked else AuditLog.Results.SUCCESS,
            orchard=orchard,
            record_count=record_count,
            sensitivity_level="SENSITIVE" if sensitive_count else "",
            message="查询频率超限" if blocked else "数据查询",
        )
        if blocked:
            factors = ["high_frequency_query"]
            if sensitive_count:
                factors.extend(["sensitive_access", "repeated_anomaly"])
            factors.extend(BehaviorBaselineService.extra_factors(user, orchard=orchard))
            RiskScoringService.create_event("查询频率异常", factors, user=user, details={"monitor_id": monitor.pk, "path": request.path})
            raise PermissionDenied("查询频率超过安全阈值，请稍后重试")
        return monitor
