from django.contrib import admin

from .models import EngagementModel, FixedPriceRange, Order, OrderItem, Payment, ProductizedService, RoleRate


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "customer_name", "total_npr", "payment_status", "fulfilment_status", "created_at"]
    inlines = [OrderItemInline, PaymentInline]


admin.site.register(EngagementModel)
admin.site.register(RoleRate)
admin.site.register(FixedPriceRange)
admin.site.register(ProductizedService)
