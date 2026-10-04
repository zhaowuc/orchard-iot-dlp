from django.urls import path
from . import views

app_name = "dlp"
urlpatterns = [
    path("policies/", views.policy_list, name="policies"),
    path("policies/new/", views.policy_edit, name="policy_create"),
    path("policies/<int:pk>/edit/", views.policy_edit, name="policy_edit"),
    path("queries/", views.query_list, name="queries"),
    path("exports/", views.export_center, name="exports"),
    path("exports/<uuid:export_id>/decision/", views.export_decide, name="export_decide"),
    path("exports/<uuid:export_id>/download/", views.export_download, name="export_download"),
]

