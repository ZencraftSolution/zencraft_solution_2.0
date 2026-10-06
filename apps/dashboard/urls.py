from django.urls import path

from . import api, crud, two_factor, views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.DashboardLoginView.as_view(), name="login"),
    path("logout/", views.dashboard_logout, name="logout"),
    path("verify/", two_factor.two_factor, name="two_factor"),
    path("security/", two_factor.security, name="security"),
    path("security/disable/", two_factor.disable_two_factor, name="two_factor_disable"),
    path("", views.overview, name="overview"),
    path("leads/", views.leads_board, name="leads"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:pk>/document/", views.lead_document, name="lead_document"),
    path("recruitment/", views.applications_board, name="applications"),
    path("recruitment/list/", views.applications_list, name="applications_list"),
    path("recruitment/export.csv", views.applications_export, name="applications_export"),
    path("recruitment/<int:pk>/", views.application_detail, name="application_detail"),
    path("recruitment/<int:pk>/cv/", views.application_cv, name="application_cv"),
    path("orders/", views.orders_list, name="orders"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("estimator/", views.estimator_config, name="estimator_config"),
    path("settings/", views.site_settings, name="settings"),
    path("analytics/", views.analytics, name="analytics"),
    path("audit/", views.audit_log, name="audit"),
    path("newsletter/export.csv", views.newsletter_export, name="newsletter_export"),
    path("api/leads/<int:pk>/status/", api.LeadStatusAPI.as_view(), name="api_lead_status"),
    path("api/applications/<int:pk>/status/", api.ApplicationStatusAPI.as_view(), name="api_application_status"),
    path("manage/<slug:slug>/", crud.crud_list, name="crud_list"),
    path("manage/<slug:slug>/new/", crud.crud_edit, name="crud_create"),
    path("manage/<slug:slug>/<int:pk>/", crud.crud_edit, name="crud_edit"),
    path("manage/<slug:slug>/<int:pk>/delete/", crud.crud_delete, name="crud_delete"),
]
