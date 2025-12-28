from django.contrib import admin
from .models import AuditLog
from memorials.admin import MemorialRelatedAdminMixin


@admin.register(AuditLog)
class AuditLogAdmin(MemorialRelatedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'action', 'actor_type', 'target_type', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('actor_id', 'target_id', 'metadata')