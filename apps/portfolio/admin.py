from django.contrib import admin

from .models import CaseStudy, CaseStudyImage, GalleryImage, TeamMember, Testimonial


class CaseStudyImageInline(admin.TabularInline):
    model = CaseStudyImage
    extra = 0


@admin.register(CaseStudy)
class CaseStudyAdmin(admin.ModelAdmin):
    list_display = ["title", "client_name", "industry", "year", "featured", "is_published"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [CaseStudyImageInline]


admin.site.register(Testimonial)
admin.site.register(TeamMember)
admin.site.register(GalleryImage)
