"""
Django admin configuration for CMO Analyst Agent models.
"""

from django.contrib import admin
from .models import (
    Prospectus,
    ProspectusSection,
    TranchesDefinition,
    TrancheDeclaration,
    DealScript
)


@admin.register(Prospectus)
class ProspectusAdmin(admin.ModelAdmin):
    """Admin interface for Prospectus model."""

    list_display = ('prospectus_name', 'created_by', 'upload_date')
    list_filter = ('upload_date', 'created_by')
    search_fields = ('prospectus_name',)
    readonly_fields = ('prospectus_id', 'upload_date')

    fieldsets = (
        ('Basic Information', {
            'fields': ('prospectus_id', 'prospectus_name', 'prospectus_file', 'created_by')
        }),
        ('Dates', {
            'fields': ('upload_date',)
        }),
        ('Data', {
            'fields': ('metadata', 'parsed_pages'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProspectusSection)
class ProspectusSectionAdmin(admin.ModelAdmin):
    """Admin interface for ProspectusSection model."""

    list_display = ('title', 'section_type', 'prospectus_id', 'level', 'order')
    list_filter = ('section_type', 'level')
    search_fields = ('title', 'content')
    readonly_fields = ('prospectus_id',)

    fieldsets = (
        ('Basic Information', {
            'fields': ('prospectus_id', 'parent', 'section_type', 'title')
        }),
        ('Hierarchy', {
            'fields': ('level', 'order')
        }),
        ('Content', {
            'fields': ('content', 'page_numbers')
        }),
        ('Data', {
            'fields': ('structured_data', 'metadata'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TranchesDefinition)
class TranchesDefinitionAdmin(admin.ModelAdmin):
    """Admin interface for TranchesDefinition model."""

    list_display = ('deal_id', 'dated_date', 'first_pay_date', 'pay_freq', 'currency')
    search_fields = ('deal_id',)
    readonly_fields = ('deal_id',)

    fieldsets = (
        ('Deal Information', {
            'fields': ('deal_id', 'currency')
        }),
        ('Dates and Frequency', {
            'fields': ('dated_date', 'first_pay_date', 'delay', 'pay_freq')
        }),
        ('Interest Settings', {
            'fields': ('interest_day_count',)
        }),
    )


@admin.register(TrancheDeclaration)
class TrancheDeclarationAdmin(admin.ModelAdmin):
    """Admin interface for TrancheDeclaration model."""

    list_display = ('deal_id', 'group_name', 'amount', 'coupon_type', 'coupon_rate')
    list_filter = ('coupon_type', 'principal_type')
    search_fields = ('group_name', 'comment')

    fieldsets = (
        ('Basic Information', {
            'fields': ('deal_id', 'group_name')
        }),
        ('Amounts', {
            'fields': ('percentage', 'amount')
        }),
        ('Payment Details', {
            'fields': ('principal_type', 'coupon_type', 'coupon_rate', 'delay')
        }),
        ('Notes', {
            'fields': ('comment',),
            'classes': ('collapse',)
        }),
    )


@admin.register(DealScript)
class DealScriptAdmin(admin.ModelAdmin):
    """Admin interface for DealScript model."""

    list_display = ('deal_id', 'prospectus_id', 'generated_date')
    list_filter = ('generated_date',)
    search_fields = ('script_content',)
    readonly_fields = ('generated_date',)

    fieldsets = (
        ('Basic Information', {
            'fields': ('deal_id', 'prospectus_id', 'generated_date')
        }),
        ('Script Content', {
            'fields': ('script_content',)
        }),
        ('Structure', {
            'fields': ('collateral_groups', 'deal_tree'),
            'classes': ('collapse',)
        }),
    )
