from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="list"),
    path("topic/<slug:category>/", views.post_list, name="category"),
    path("<slug:slug>/", views.post_detail, name="detail"),
]
