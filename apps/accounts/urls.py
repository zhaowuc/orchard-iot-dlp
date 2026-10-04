from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("users/", views.user_list, name="user_list"),
    path("users/new/", views.user_edit, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("roles/", views.role_list, name="role_list"),
    path("roles/new/", views.role_edit, name="role_create"),
    path("roles/<int:pk>/edit/", views.role_edit, name="role_edit"),
]

