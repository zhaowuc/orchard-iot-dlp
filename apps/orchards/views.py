from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Role
from apps.audit.services import AuditService
from apps.dlp.models import AccessPolicy
from apps.dlp.services import AccessControlService
from apps.masking.models import MaskingRule
from apps.masking.services import MaskingService
from config.view_utils import render_table
from .forms import DataSourceForm, DeviceForm, GatewayForm, OrchardForm, PlotForm
from .models import DataSource, Device, Gateway, Orchard, Plot, StatusChoices


REGISTRY = {
    "orchards": {"model": Orchard, "form": OrchardForm, "title": "果园管理", "search": ("name", "code", "location"), "select": (), "columns": [("名称", "name"), ("编码", "code"), ("位置", "location"), ("联系人", "contact_name"), ("状态", "status", True)]},
    "plots": {"model": Plot, "form": PlotForm, "title": "地块管理", "search": ("name", "code", "orchard__name"), "select": ("orchard",), "columns": [("地块", "name"), ("编码", "code"), ("果园", lambda o: o.orchard.name), ("面积/亩", lambda o: o.area or "—"), ("状态", "status", True)]},
    "gateways": {"model": Gateway, "form": GatewayForm, "title": "网关管理", "search": ("name", "gateway_code", "orchard__name"), "select": ("orchard",), "columns": [("网关", "name"), ("编码", "gateway_code"), ("果园", lambda o: o.orchard.name), ("协议", "protocol", True), ("状态", "status", True)]},
    "devices": {"model": Device, "form": DeviceForm, "title": "设备管理", "search": ("device_name", "device_code", "orchard__name"), "select": ("orchard", "plot", "gateway"), "columns": [("设备", "device_name"), ("设备编号", "device_code"), ("类型", lambda o: o.get_device_type_display()), ("果园/地块", lambda o: f"{o.orchard.name} / {o.plot.name if o.plot else '未分配'}"), ("状态", "status", True)]},
    "sources": {"model": DataSource, "form": DataSourceForm, "title": "数据源管理", "search": ("name", "orchard__name", "endpoint"), "select": ("orchard",), "columns": [("名称", "name"), ("果园", lambda o: o.orchard.name), ("类型", "source_type", True), ("端点", lambda o: o.endpoint or "—"), ("状态", "status", True)]},
}


def _scoped_queryset(user, cfg):
    qs = cfg["model"].objects.all()
    if cfg["select"]:
        qs = qs.select_related(*cfg["select"])
    if cfg["model"] is Orchard:
        return AccessControlService.orchard_queryset(user, qs)
    if not (user.is_superuser or user.role_code in {Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN}):
        qs = qs.filter(orchard__authorized_users=user)
    return qs


def asset_list(request, kind):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect("accounts:login")
    cfg = REGISTRY.get(kind)
    if not cfg:
        raise PermissionDenied
    if kind == "orchards":
        location_level = MaskingService.level_for_field("plot_location", "location", "SENSITIVE")
        contact_level = MaskingService.level_for_field("contact_name", "contact", "SENSITIVE")
        phone_level = MaskingService.level_for_field("contact_phone", "phone", "IMPORTANT")
        columns = [
            {"label": "名称", "value": "name"},
            {"label": "编码", "value": "code"},
            {"label": "位置", "value": lambda o: MaskingService.apply(o.location, "location", user=request.user, scene=MaskingRule.Scenes.WEB_VIEW, sensitivity_level=location_level, orchard=o, source_type="Orchard", source_object_id=o.pk)},
            {"label": "联系人", "value": lambda o: MaskingService.apply(o.contact_name, "username", user=request.user, scene=MaskingRule.Scenes.WEB_VIEW, sensitivity_level=contact_level, orchard=o, source_type="Orchard", source_object_id=o.pk)},
            {"label": "联系电话", "value": lambda o: MaskingService.apply(o.contact_phone, "phone", user=request.user, scene=MaskingRule.Scenes.WEB_VIEW, sensitivity_level=phone_level, orchard=o, source_type="Orchard", source_object_id=o.pk)},
            {"label": "状态", "value": "status", "badge": True},
        ]
    elif kind == "devices":
        device_level = MaskingService.level_for_field("device_code", "device_code", "SENSITIVE")
        columns = [
            {"label": "设备", "value": "device_name"},
            {"label": "设备编号", "value": lambda o: MaskingService.apply(o.device_code, "device_code", user=request.user, scene=MaskingRule.Scenes.WEB_VIEW, sensitivity_level=device_level, orchard=o.orchard, source_type="Device", source_object_id=o.pk)},
            {"label": "类型", "value": lambda o: o.get_device_type_display()},
            {"label": "果园/地块", "value": lambda o: f"{o.orchard.name} / {o.plot.name if o.plot else '未分配'}"},
            {"label": "状态", "value": "status", "badge": True},
        ]
    else:
        columns = [{"label": item[0], "value": item[1], "badge": len(item) > 2 and item[2]} for item in cfg["columns"]]
    can_edit = request.user.has_role(Role.Codes.SUPER_ADMIN) or (request.user.role_code == Role.Codes.ORCHARD_ADMIN and kind != "orchards")
    return render_table(
        request,
        title=cfg["title"],
        subtitle="按授权果园范围展示，所有对象权限均由后端校验",
        queryset=_scoped_queryset(request.user, cfg),
        columns=columns,
        search_fields=cfg["search"],
        filters=[{"param": "status", "label": "状态", "choices": StatusChoices.choices}],
        create_url="orchards:asset_create" if can_edit else None,
        extra={"edit_url_name": "orchards:asset_edit" if can_edit else None, "kind": kind},
    )


def asset_edit(request, kind, pk=None):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not request.user.has_role(Role.Codes.SUPER_ADMIN, Role.Codes.ORCHARD_ADMIN):
        raise PermissionDenied
    cfg = REGISTRY.get(kind)
    if not cfg:
        raise PermissionDenied
    if kind == "orchards" and not request.user.has_role(Role.Codes.SUPER_ADMIN):
        raise PermissionDenied("只有超级管理员可以新增或修改果园")
    obj = get_object_or_404(cfg["model"].objects.all(), pk=pk) if pk else None
    if obj and not isinstance(obj, Orchard):
        AccessControlService.require_orchard(request.user, obj.orchard, AccessPolicy.Operations.UPDATE, request=request)
    form = cfg["form"](request.POST or None, instance=obj)
    if request.user.role_code == Role.Codes.ORCHARD_ADMIN:
        authorized = request.user.assigned_orchards.all()
        if "orchard" in form.fields:
            form.fields["orchard"].queryset = authorized
        if "plot" in form.fields:
            form.fields["plot"].queryset = Plot.objects.filter(orchard__in=authorized)
        if "gateway" in form.fields:
            form.fields["gateway"].queryset = Gateway.objects.filter(orchard__in=authorized)
    if request.method == "POST" and form.is_valid():
        orchard = form.cleaned_data.get("orchard") or (obj if isinstance(obj, Orchard) else None)
        if orchard and not AccessControlService.can_access_orchard(request.user, orchard, AccessPolicy.Operations.UPDATE):
            AccessControlService.require_orchard(request.user, orchard, AccessPolicy.Operations.UPDATE, request=request)
        saved = form.save()
        AuditService.log("ASSET_MODIFY", user=request.user, request=request, object_type=saved.__class__.__name__, object_id=str(saved.pk), orchard=saved if isinstance(saved, Orchard) else getattr(saved, "orchard", None), message=f"维护{cfg['title']}记录")
        messages.success(request, "资产信息已保存。")
        return redirect("orchards:asset_list", kind=kind)
    return render(request, "shared/form.html", {"title": f"{'编辑' if obj else '新增'}{cfg['title'].replace('管理', '')}", "form": form, "back_url": "orchards:asset_list", "back_kwargs": {"kind": kind}})
