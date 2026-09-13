from django.urls import path

from . import views

app_name = "careers"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("jobs/", views.job_list, name="jobs"),
    path("jobs/<slug:slug>/", views.job_detail, name="job_detail"),
    path("jobs/<slug:slug>/apply/", views.apply, name="apply"),
    path("application-received/", views.applied, name="applied"),
]
