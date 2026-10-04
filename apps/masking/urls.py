from django.urls import path
from . import views

app_name = "masking"
urlpatterns = [
    path("rules/", views.rule_list, name="rules"),
    path("rules/new/", views.rule_edit, name="rule_create"),
    path("rules/<int:pk>/edit/", views.rule_edit, name="rule_edit"),
    path("preview/", views.preview, name="preview"),
    path("records/", views.record_list, name="records"),
]
