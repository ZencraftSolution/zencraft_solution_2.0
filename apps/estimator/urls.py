from django.urls import path

from . import views

app_name = "estimator"

urlpatterns = [
    path("", views.start, name="start"),
    path("api/config/", views.config_api, name="config_api"),
    path("api/preview/", views.preview_api, name="preview_api"),
    path("api/submit/", views.submit_api, name="submit_api"),
    path("api/event/", views.event_api, name="event_api"),
]
