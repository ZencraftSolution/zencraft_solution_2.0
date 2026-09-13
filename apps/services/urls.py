from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    path("", views.service_list, name="list"),
    path("industries/", views.industry_list, name="industries"),
    path("industries/<slug:slug>/", views.industry_detail, name="industry_detail"),
    path("technologies/", views.technology_list, name="technologies"),
    path("<slug:slug>/", views.service_detail, name="detail"),
]
