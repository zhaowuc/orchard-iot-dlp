from django.urls import path
from . import views

app_name = "audit"
urlpatterns = [
    path("logs/", views.audit_list, name="logs"),
    path("risks/", views.risk_list, name="risks"),
    path("alerts/", views.alert_list, name="alerts"),
    path("alerts/<int:pk>/", views.alert_handle, name="alert_handle"),
]
