from django.urls import path
from . import views

app_name = "sensitive"
urlpatterns = [
    path("fields/", views.field_list, name="fields"),
    path("fields/new/", views.field_edit, name="field_create"),
    path("fields/<int:pk>/edit/", views.field_edit, name="field_edit"),
    path("rules/", views.rule_list, name="rules"),
    path("rules/new/", views.rule_edit, name="rule_create"),
    path("rules/<int:pk>/edit/", views.rule_edit, name="rule_edit"),
    path("detections/", views.detection_list, name="detections"),
]

