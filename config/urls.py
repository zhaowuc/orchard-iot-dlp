from django.urls import include, path
from apps.iot.views import ingest_api


urlpatterns = [
    path("api/iot/data/", ingest_api, name="iot_ingest_api"),
    path("", include("apps.dashboard.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("assets/", include("apps.orchards.urls")),
    path("data/", include("apps.iot.urls")),
    path("sensitive/", include("apps.sensitive.urls")),
    path("masking/", include("apps.masking.urls")),
    path("dlp/", include("apps.dlp.urls")),
    path("security/", include("apps.audit.urls")),
]

handler400 = "config.error_views.bad_request"
handler403 = "config.error_views.permission_denied"
handler404 = "config.error_views.page_not_found"
handler500 = "config.error_views.server_error"

# MEDIA_ROOT contains private security exports. It must never be mounted as a
# public URL, even in DEBUG mode; downloads go through the authorized view.
