from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class ZencraftUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Profile", {"fields": ("job_title", "phone")}),)
