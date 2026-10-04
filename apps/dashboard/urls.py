from django.urls import path
from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.index, name="index"),
    path("api/dashboard/summary/", views.chart_api, name="chart_api"),
    path("settings/", views.config_list, name="configs"),
    path("settings/<int:pk>/edit/", views.config_edit, name="config_edit"),
]

