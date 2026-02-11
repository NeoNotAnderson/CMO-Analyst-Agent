"""
Django admin configuration for CMO Analyst Agent models.
"""

from django.contrib import admin
from .models import Prospectus


@admin.register(Prospectus)
class ProspectusAdmin(admin.ModelAdmin):
    """Admin interface for Prospectus model."""

    list_display = ('prospectus_name', 'created_by', 'upload_date', 'parse_status')
    list_filter = ('upload_date', 'created_by', 'parse_status')
    search_fields = ('prospectus_name',)
    readonly_fields = ('prospectus_id', 'upload_date')

    fieldsets = (
        ('Basic Information', {
            'fields': ('prospectus_id', 'prospectus_name', 'prospectus_file', 'created_by')
        }),
        ('Parsing Status', {
            'fields': ('parse_status',)
        }),
        ('Dates', {
            'fields': ('upload_date',)
        }),
        ('Data', {
            'fields': ('metadata', 'parsed_pages', 'index_page_numbers', 'parsed_index', 'parsed_file'),
            'classes': ('collapse',)
        }),
    )
