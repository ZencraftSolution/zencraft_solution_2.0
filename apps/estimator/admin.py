from django.contrib import admin

from .models import EstimatorConfig, FeatureOption, LeadNote, ProjectInquiry, ProjectType


class LeadNoteInline(admin.TabularInline):
    model = LeadNote
    extra = 0


@admin.register(ProjectInquiry)
class ProjectInquiryAdmin(admin.ModelAdmin):
    list_display = ["reference", "name", "company", "project_type_label", "status", "created_at"]
    list_filter = ["status", "project_type"]
    inlines = [LeadNoteInline]


admin.site.register(EstimatorConfig)
admin.site.register(ProjectType)
admin.site.register(FeatureOption)
