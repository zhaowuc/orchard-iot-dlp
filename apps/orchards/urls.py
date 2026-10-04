from django.urls import path
from . import views

app_name = "orchards"
urlpatterns = [
    path("<str:kind>/", views.asset_list, name="asset_list"),
    path("<str:kind>/new/", views.asset_edit, name="asset_create"),
    path("<str:kind>/<int:pk>/edit/", views.asset_edit, name="asset_edit"),
]
