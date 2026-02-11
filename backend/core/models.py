"""
Database models for CMO Analyst Agent.

This module defines the core data structures for storing:
- Prospectus documents with parsed pages
- Hierarchical section mappings (self-referencing tree)
- Tranche definitions and declarations
- Generated TrancheSpeak scripts with deal structure
"""

from django.db import models
from django.contrib.auth.models import User
import uuid


class Prospectus(models.Model):
    """
    Stores uploaded CMO prospectus documents.

    Attributes:
        prospectus_id: UUID primary key
        prospectus_name: Name/identifier of the prospectus
        prospectus_file: Uploaded PDF file
        upload_date: Timestamp of upload
        created_by: User who uploaded the prospectus
        parse_status: Current parsing status
        metadata: Additional metadata as JSON
        parsed_pages: List of parsed pages from the current prospectus
        index_page_numbers: List of index page numbers
    """

    class ParseStatus(models.TextChoices):
        """Parsing status choices for prospectus."""
        PENDING = 'pending', 'Pending'
        PARSING_INDEX = 'parsing_index', 'Parsing Index'
        PARSING_SECTIONS = 'parsing_sections', 'Parsing Sections'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    prospectus_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prospectus_name = models.CharField(max_length=255)
    prospectus_file = models.FileField(upload_to='prospectus/')
    upload_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prospectuses')
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.PENDING,
        db_index=True,
        help_text="Current parsing status of the prospectus"
    )
    metadata = models.JSONField(default=dict, blank=True)
    parsed_pages = models.JSONField(default=list, blank=True)  # List of parsed page objects
    index_page_numbers = models.JSONField(default=list, blank=True, null=True)  # List of index page numbers
    parsed_index = models.JSONField(default=dict, blank=True, null=True)  # parsed index pages in json format
    parsed_file = models.JSONField(default=dict, blank=True, null=True)  # parsed prospectus in json format
    class Meta:
        db_table = 'prospectus'
        ordering = ['-upload_date']
        constraints = [
            models.UniqueConstraint(
                fields=['prospectus_name', 'created_by'],
                name='unique_prospectus_per_user'
            )
        ]

    def __str__(self):
        return f"{self.prospectus_name}"

