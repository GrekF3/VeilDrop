from django.contrib import admin
from .models import File, AdsBanner

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('unique_key', 'file', 'created_at')
    search_fields = ('unique_key',)

@admin.register(AdsBanner)
class AdsBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('title',)