from django.utils import timezone


def application_context(request):
    role_code = ""
    if getattr(request, "user", None) and request.user.is_authenticated and request.user.role_id:
        role_code = request.user.role.code
    return {
        "app_name": "果安哨兵",
        "current_time": timezone.localtime(),
        "current_role_code": role_code,
    }

