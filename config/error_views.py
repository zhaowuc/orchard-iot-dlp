from django.shortcuts import render


def bad_request(request, exception=None):
    return render(request, "errors/error.html", {"code": 400, "title": "请求参数有误", "message": "请检查输入内容后重试。"}, status=400)


def permission_denied(request, exception=None):
    return render(request, "errors/error.html", {"code": 403, "title": "访问被拒绝", "message": "当前账号没有执行此操作的权限。"}, status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/error.html", {"code": 404, "title": "页面不存在", "message": "链接可能已失效或资源已被移除。"}, status=404)


def server_error(request):
    return render(request, "errors/error.html", {"code": 500, "title": "系统暂时不可用", "message": "错误已记录，请稍后重试。"}, status=500)

