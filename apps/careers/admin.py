from django.contrib import admin

from .models import ApplicationNote, Department, EducationEntry, ExperienceEntry, JobApplication, JobOpening, ProjectEntry


class EducationInline(admin.TabularInline):
    model = EducationEntry
    extra = 0


class ExperienceInline(admin.TabularInline):
    model = ExperienceEntry
    extra = 0


class ProjectInline(admin.TabularInline):
    model = ProjectEntry
    extra = 0


class NoteInline(admin.TabularInline):
    model = ApplicationNote
    extra = 0


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ["reference", "full_name", "job", "application_mode", "status", "created_at"]
    list_filter = ["status", "job", "application_mode"]
    exclude = ["cv"]
    inlines = [EducationInline, ExperienceInline, ProjectInline, NoteInline]


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ["title", "department", "experience_level", "is_active", "posted_at"]
    prepopulated_fields = {"slug": ["title"]}


admin.site.register(Department)
