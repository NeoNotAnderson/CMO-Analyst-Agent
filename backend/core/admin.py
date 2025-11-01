"""
Django admin configuration for CMO Analyst Agent models.
"""

from django.contrib import admin
from .models import (
    Prospectus,
    SectionMapping,
    Conversation,
    Message,
    TrancheScript
)


@admin.register(Prospectus)
class ProspectusAdmin(admin.ModelAdmin):
    """Admin interface for Prospectus model."""

    list_display = ('filename', 'deal_name', 'processing_status', 'upload_date', 'file_size')
    list_filter = ('processing_status', 'upload_date')
    search_fields = ('filename', 'deal_name')
    readonly_fields = ('id', 'upload_date', 'file_size')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'filename', 'deal_name', 'file')
        }),
        ('Status', {
            'fields': ('processing_status', 'upload_date', 'file_size')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )


@admin.register(SectionMapping)
class SectionMappingAdmin(admin.ModelAdmin):
    """Admin interface for SectionMapping model."""

    list_display = ('section_title', 'section_type', 'prospectus', 'confidence_score', 'created_at')
    list_filter = ('section_type', 'created_at')
    search_fields = ('section_title', 'content', 'prospectus__deal_name')
    readonly_fields = ('id', 'created_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'prospectus', 'section_type', 'section_title')
        }),
        ('Content', {
            'fields': ('content', 'page_numbers')
        }),
        ('Metadata', {
            'fields': ('confidence_score', 'metadata', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model."""

    list_display = ('title', 'prospectus', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('title', 'prospectus__deal_name')
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'prospectus', 'title', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""

    list_display = ('get_preview', 'role', 'message_type', 'conversation', 'created_at')
    list_filter = ('role', 'message_type', 'created_at')
    search_fields = ('content', 'conversation__title')
    readonly_fields = ('id', 'created_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'role', 'message_type')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def get_preview(self, obj):
        """Return preview of message content."""
        return obj.content[:75] + '...' if len(obj.content) > 75 else obj.content
    get_preview.short_description = 'Preview'


@admin.register(TrancheScript)
class TrancheScriptAdmin(admin.ModelAdmin):
    """Admin interface for TrancheScript model."""

    list_display = ('get_script_name', 'prospectus', 'version', 'generation_status', 'created_at')
    list_filter = ('generation_status', 'created_at')
    search_fields = ('script_content', 'prospectus__deal_name')
    readonly_fields = ('id', 'created_at', 'version')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'prospectus', 'version', 'generation_status')
        }),
        ('Script Content', {
            'fields': ('script_content',)
        }),
        ('Validation', {
            'fields': ('validation_errors',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'created_by_message'),
            'classes': ('collapse',)
        }),
    )

    def get_script_name(self, obj):
        """Return script name with version."""
        return f"Script v{obj.version}"
    get_script_name.short_description = 'Script'
