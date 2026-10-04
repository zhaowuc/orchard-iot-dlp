from django import template


register = template.Library()


@register.filter
def status_class(value):
    value = str(value or "").upper()
    if value in {"ACTIVE", "ONLINE", "SUCCESS", "APPROVED", "COMPLETED", "RESOLVED", "PUBLIC", "LOW", "ALLOW"}:
        return "success"
    if value in {"PENDING", "PROCESSING", "INTERNAL", "MEDIUM", "OFFLINE"}:
        return "warning"
    if value in {"HIGH", "SENSITIVE", "ABNORMAL", "FAILURE", "REJECTED"}:
        return "danger"
    if value in {"CRITICAL", "IMPORTANT", "BLOCKED", "DISABLED", "DENY"}:
        return "critical"
    return "neutral"


@register.filter
def get_item(mapping, key):
    return mapping.get(key, "") if mapping else ""

