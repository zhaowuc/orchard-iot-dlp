from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from apps.audit.services import AuditService
from config.view_utils import render_table, role_required
from .forms import RoleForm, UserForm
from .models import Role, User
from .services import LoginAuditService


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        user = authenticate(request, username=username, password=request.POST.get("password", ""))
        if user and user.is_active:
            login(request, user)
            LoginAuditService.record(request, username, True, user=user)
            next_url = request.GET.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("dashboard:index")
        attempt_user = User.objects.filter(username=username).first()
        LoginAuditService.record(request, username, False, user=attempt_user, reason="用户名、密码错误或账号已禁用")
        messages.error(request, "用户名、密码错误或账号已禁用。")
    return render(request, "accounts/login.html")


@require_POST
@login_required
def logout_view(request):
    AuditService.log("LOGOUT", user=request.user, request=request, message="用户退出系统")
    logout(request)
    return redirect("accounts:login")


@role_required(Role.Codes.SUPER_ADMIN)
def user_list(request):
    return render_table(
        request,
        title="用户管理",
        subtitle="管理业务账号、角色及果园数据范围",
        queryset=User.objects.select_related("role").prefetch_related("assigned_orchards").order_by("username"),
        columns=[
            {"label": "账号", "value": "username"},
            {"label": "姓名", "value": lambda o: o.display_name or "—"},
            {"label": "角色", "value": lambda o: o.role.name if o.role else "未分配", "badge": True},
            {"label": "授权果园", "value": lambda o: "、".join(x.name for x in o.assigned_orchards.all()) or "全局/未授权"},
            {"label": "状态", "value": lambda o: "ACTIVE" if o.is_active else "INACTIVE", "badge": True},
        ],
        search_fields=("username", "display_name", "email"),
        create_url="accounts:user_create",
        extra={"edit_url_name": "accounts:user_edit"},
    )


@role_required(Role.Codes.SUPER_ADMIN)
def user_edit(request, pk=None):
    user_obj = get_object_or_404(User, pk=pk) if pk else None
    form = UserForm(request.POST or None, instance=user_obj)
    if request.method == "POST" and form.is_valid():
        if not user_obj and not form.cleaned_data.get("password"):
            form.add_error("password", "新建用户必须设置密码")
        else:
            saved = form.save()
            AuditService.log("USER_MODIFY", user=request.user, request=request, object_type="User", object_id=str(saved.pk), message=f"维护用户 {saved.username}")
            messages.success(request, "用户信息已保存。")
            return redirect("accounts:user_list")
    return render(request, "shared/form.html", {"title": "编辑用户" if user_obj else "新增用户", "form": form, "back_url": "accounts:user_list"})


@role_required(Role.Codes.SUPER_ADMIN)
def role_list(request):
    return render_table(
        request,
        title="角色管理",
        subtitle="四类业务角色及其职责边界",
        queryset=Role.objects.all(),
        columns=[{"label": "名称", "value": "name"}, {"label": "编码", "value": "code", "badge": True}, {"label": "说明", "value": "description"}],
        search_fields=("name", "code"),
        create_url="accounts:role_create",
        extra={"edit_url_name": "accounts:role_edit"},
    )


@role_required(Role.Codes.SUPER_ADMIN)
def role_edit(request, pk=None):
    obj = get_object_or_404(Role, pk=pk) if pk else None
    form = RoleForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        AuditService.log("PERMISSION_MODIFY", user=request.user, request=request, object_type="Role", object_id=str(saved.pk), message=f"维护角色 {saved.code}")
        messages.success(request, "角色已保存。")
        return redirect("accounts:role_list")
    return render(request, "shared/form.html", {"title": "编辑角色" if obj else "新增角色", "form": form, "back_url": "accounts:role_list"})
