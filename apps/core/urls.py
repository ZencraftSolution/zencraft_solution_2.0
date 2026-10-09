from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("book-consultation/", views.consultation, name="consultation"),
    path("newsletter/", views.newsletter_subscribe, name="newsletter"),
    path("feedback/", views.feedback, name="feedback"),
    path("search/", views.search, name="search"),
    path("pageview/", views.pageview, name="pageview"),
    path("legal/privacy/", views.legal, {"page": "privacy"}, name="privacy"),
    path("legal/terms/", views.legal, {"page": "terms"}, name="terms"),
    path("legal/cookies/", views.legal, {"page": "cookies"}, name="cookies"),
]
