from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("", views.case_study_list, name="list"),
    path("<slug:slug>/", views.case_study_detail, name="detail"),
]
