from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import User

@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ('email', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('email',)
    ordering = ('-date_joined',)
