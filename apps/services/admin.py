from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import FAQ, Industry, ProcessStep, Service, ServiceCategory, Technology


class FAQInline(GenericTabularInline):
    model = FAQ
    extra = 0


class ProcessStepInline(admin.TabularInline):
    model = ProcessStep
    extra = 0


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "order", "featured", "is_published"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [ProcessStepInline, FAQInline]
    filter_horizontal = ["technologies", "industries", "engagement_models", "related"]


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ["name"]}
    inlines = [FAQInline]


admin.site.register(ServiceCategory)
admin.site.register(Technology)
