from django.urls import path
from . import views

app_name = "iot"
urlpatterns = [
    path("readings/", views.reading_list, name="readings"),
    path("api/readings/", views.readings_api, name="readings_api"),
    path("api/iot/data/", views.ingest_api, name="ingest_api"),
]
