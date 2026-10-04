from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render


def role_required(*codes):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_active or not request.user.has_role(*codes):
                raise PermissionDenied("当前角色无权访问此页面")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def paginate(request, queryset, per_page=20):
    if not queryset.ordered:
        queryset = queryset.order_by("-pk")
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def search_queryset(queryset, term, fields):
    if not term:
        return queryset
    query = Q()
    for field in fields:
        query |= Q(**{f"{field}__icontains": term})
    return queryset.filter(query)


def render_table(request, *, title, subtitle, queryset, columns, search_fields=(), filters=None, create_url=None, template="shared/table.html", extra=None):
    term = request.GET.get("q", "").strip()
    queryset = search_queryset(queryset, term, search_fields)
    filters = filters or []
    active_filters = {}
    for item in filters:
        value = request.GET.get(item["param"], "").strip()
        if value:
            queryset = queryset.filter(**{item.get("lookup", item["param"]): value})
            active_filters[item["param"]] = value
    page_obj = paginate(request, queryset)
    rows = []
    for obj in page_obj.object_list:
        cells = []
        for col in columns:
            value = col["value"](obj) if callable(col["value"]) else getattr(obj, col["value"], "")
            cells.append({"value": value, "badge": col.get("badge", False), "class": col.get("class", "")})
        rows.append({"object": obj, "cells": cells})
    context = {
        "title": title,
        "subtitle": subtitle,
        "columns": columns,
        "rows": rows,
        "page_obj": page_obj,
        "search_term": term,
        "filters": filters,
        "active_filters": active_filters,
        "create_url": create_url,
    }
    if extra:
        context.update(extra)
    return render(request, template, context)
