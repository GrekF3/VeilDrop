from django.contrib import admin
from .models import BotUser

@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'user_id', 'generated_links')
    search_fields = ('username', 'user_id')