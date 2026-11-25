from django.contrib import admin

from .models import Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "uploaded_at")
    list_filter = ("owner", "uploaded_at")
    search_fields = ("title", "caption", "owner__username")
