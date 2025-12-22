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
        CLASSIFYING = 'classifying', 'Classifying'
        STORING = 'storing', 'Storing'
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

    def __str__(self):
        return f"{self.prospectus_name}"


class ProspectusSection(models.Model):
    """
    Stores parsed sections from prospectus with hierarchical structure.

    Self-referencing tree structure to handle sections and subsections
    at arbitrary nesting depths.

    Attributes:
        prospectus_id: Foreign key to Prospectus
        parent: Self-referencing foreign key for hierarchy (null for root sections)
        section_type: Type/classification of section
        title: Section heading/title
        content: Extracted text content at this level
        page_numbers: List of page numbers where this section appears
        level: Depth in hierarchy (0=root, 1=section, 2=subsection, etc.)
        order: Order within parent for sorting
        structured_data: Flexible JSON storage for parsed/structured data
        metadata: Additional parsing metadata (confidence scores, method, etc.)
    """

    class SectionType(models.TextChoices):
        """Standard CMO prospectus section types."""
        DEAL_SUMMARY = 'deal_summary', 'Deal Summary'
        DEAL_STRUCTURE = 'deal_structure', 'Deal Structure'
        TRANCHE_LIST = 'tranche_list', 'Tranche List'
        TRANCHE_DETAILS = 'tranche_details', 'Tranche Details'
        COLLATERAL_DETAIL = 'collateral_detail', 'Collateral Detail'
        PAYMENT_PRIORITY = 'payment_priority', 'Payment Priority'
        INTEREST_DISTRIBUTION = 'interest_distribution', 'Interest Distribution'
        PRINCIPAL_DISTRIBUTION = 'principal_distribution', 'Principal Distribution'
        DEFAULT_LOSS = 'default_loss', 'Default Loss Distribution'
        PREPAYMENT_PENALTY = 'prepayment_penalty', 'Prepayment Penalty'
        RISK_FACTORS = 'risk_factors', 'Risk Factors'
        OTHER = 'other', 'Other'

    prospectus_id = models.ForeignKey(
        Prospectus,
        on_delete=models.CASCADE,
        related_name='sections',
        db_column='prospectus_id'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subsections'
    )
    section_type = models.CharField(
        max_length=50,
        choices=SectionType.choices
    )
    title = models.CharField(max_length=500)
    content = models.TextField()
    page_numbers = models.JSONField(default=list)
    level = models.IntegerField(default=0)
    order = models.IntegerField(default=0)
    structured_data = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'prospectus_section'
        ordering = ['prospectus_id', 'order']
        indexes = [
            models.Index(fields=['prospectus_id', 'section_type']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return f"{self.section_type} - {self.title[:50]} (Level {self.level})"


class TranchesDefinition(models.Model):
    """
    Stores deal-level tranche definitions and parameters.

    Global parameters that apply to all tranches in the deal.

    Attributes:
        deal_id: Unique identifier for the deal
        dated_date: Deal dated date
        first_pay_date: First payment date
        delay: Payment delay in days
        pay_freq: Payment frequency (monthly, quarterly, etc.)
        interest_day_count: Day count convention for interest
        currency: Currency denomination
    """

    deal_id = models.CharField(max_length=100, primary_key=True)
    dated_date = models.DateField(null=True, blank=True)
    first_pay_date = models.DateField(null=True, blank=True)
    delay = models.IntegerField(null=True, blank=True, help_text="Payment delay in days")
    pay_freq = models.CharField(max_length=50, null=True, blank=True, help_text="Payment frequency")
    interest_day_count = models.CharField(max_length=50, null=True, blank=True)
    currency = models.CharField(max_length=10, default='USD')

    class Meta:
        db_table = 'tranches_definition'

    def __str__(self):
        return f"Tranches Definition - {self.deal_id}"


class TrancheDeclaration(models.Model):
    """
    Stores individual tranche declarations within a deal.

    Each tranche has specific parameters like balance, coupon, etc.

    Attributes:
        deal_id: Foreign key to TranchesDefinition
        percentage: Percentage of deal (if applicable)
        amount: Original balance/amount
        principal_type: Type of principal payment (sequential, pro-rata, etc.)
        coupon_type: Fixed, floating, step, etc.
        coupon_rate: Coupon rate (for fixed) or spread (for floating)
        delay: Tranche-specific delay (overrides deal-level if set)
        group_name: Collateral group assignment
        comment: Additional notes/comments
    """

    deal_id = models.ForeignKey(
        TranchesDefinition,
        on_delete=models.CASCADE,
        related_name='tranches',
        db_column='deal_id'
    )
    percentage = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    principal_type = models.CharField(max_length=50, null=True, blank=True)
    coupon_type = models.CharField(max_length=50, null=True, blank=True)
    coupon_rate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    delay = models.IntegerField(null=True, blank=True, help_text="Tranche-specific delay")
    group_name = models.CharField(max_length=100, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'tranche_declaration'

    def __str__(self):
        return f"Tranche - {self.deal_id} ({self.group_name})"


class DealScript(models.Model):
    """
    Stores generated TrancheSpeak scripts with deal structure.

    Attributes:
        deal_id: Foreign key to TranchesDefinition
        prospectus_id: Foreign key to Prospectus
        script_content: Generated TrancheSpeak script content
        generated_date: Timestamp of generation
        collateral_groups: JSON field storing groups (e.g., ["group1", "group2"])
        deal_tree: JSON field storing hierarchical deal structure
                   Example: {
                       "group1": {"HIDA": ["A1", "A2"]},
                       "group2": {"HIDB": ["B1", "B2"]}
                   }
    """

    deal_id = models.ForeignKey(
        TranchesDefinition,
        on_delete=models.CASCADE,
        related_name='scripts',
        db_column='deal_id'
    )
    prospectus_id = models.ForeignKey(
        Prospectus,
        on_delete=models.CASCADE,
        related_name='deal_scripts',
        db_column='prospectus_id'
    )
    script_content = models.TextField()
    generated_date = models.DateTimeField(auto_now_add=True)
    collateral_groups = models.JSONField(default=list, blank=True)  # ["group1", "group2"]
    deal_tree = models.JSONField(default=dict, blank=True)  # Hierarchical structure

    class Meta:
        db_table = 'deal_script'
        ordering = ['-generated_date']

    def __str__(self):
        return f"Script for {self.deal_id} - {self.generated_date}"
