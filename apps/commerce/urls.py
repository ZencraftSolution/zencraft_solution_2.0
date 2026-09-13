from django.urls import path

from . import views

app_name = "commerce"

urlpatterns = [
    path("", views.pricing, name="pricing"),
    path("store/", views.store, name="store"),
    path("store/cart/", views.cart_detail, name="cart"),
    path("store/cart/add/<int:pk>/", views.cart_add, name="cart_add"),
    path("store/cart/update/", views.cart_update, name="cart_update"),
    path("store/checkout/", views.checkout, name="checkout"),
    path("store/order/<str:reference>/pay/", views.payment_select, name="payment"),
    path("store/order/<str:reference>/pay/<str:gateway>/", views.payment_start, name="payment_start"),
    path("store/payments/<str:gateway>/<str:reference>/callback/<str:outcome>/", views.payment_callback, name="payment_callback"),
    path("store/payments/<str:gateway>/<str:reference>/sandbox/", views.simulate, name="simulate"),
    path("store/order/<str:reference>/", views.order_done, name="order_done"),
    path("store/<slug:slug>/", views.product_detail, name="product_detail"),
]
