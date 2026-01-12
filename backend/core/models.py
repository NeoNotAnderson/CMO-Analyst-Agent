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


class SectionMap(models.Model):
    """
    Stores classified section mappings with standardized taxonomy.

    This model maps prospectus sections to a standardized taxonomy for
    efficient retrieval and script generation.

    Attributes:
        prospectus: Foreign key to Prospectus
        category: Primary section category from taxonomy
        subcategory: Optional subcategory for detailed classification
        title: Original section title from prospectus
        page_start: Starting page number
        page_end: Ending page number
        level: Hierarchy level from index
        parent_category: Parent section's category (for nested sections)
        confidence_score: Classification confidence (0.0-1.0)
        classification_method: How it was classified (rule/llm/manual)
        content_summary: Brief summary of section content
        keywords: Extracted keywords for search
        page_numbers: Full list of page numbers in section
    """

    class Category(models.TextChoices):
        """Standardized section categories."""
        DEAL_SUMMARY = 'deal_summary', 'Deal Summary'
        RISK_DESCRIPTION = 'risk_factors', 'Risk Factors'
        CERTIFICATE_DESCRIPTION = 'certificate_structure', 'Certificate Structure'
        COLLATERAL_DESCRIPTION = 'collateral_description', 'Collateral Description'
        UNCLASSIFIED = 'unclassified', 'Unclassified'

    class Subcategory(models.TextChoices):
        """Detailed subcategories."""
        # DEAL_SUMMARY subsections
        CERTIFICATE_SUMARY = 'offered_certificates', 'Offered Certificates'
        COUNTERPARTIES = 'counterparties', 'Counterparties'
        KEY_DATES = 'key_dates', 'Key Dates'
        PAYMENT_PRIORITY = 'payment_priority', 'Payment Priority'
        INTEREST_DISTRIBUTION = 'interest_distribution', 'Interest Distribution'
        PRINCIPAL_DISTRIBUTION = 'principal_distribution', 'Principal Distribution'
        CROSS_COLLATERALIZATION = 'cross_collateralization', 'Cross-Collateralization'
        CLEAN_UP_CALL = 'clean_up_call', 'Clean-Up Call'
        CREDIT_ENHANCEMENT = 'credit_enhancement', 'Credit Enhancement'
        MORTGAGE_SUMMARY = 'mortgage_summary', 'Mortgage Summary'
        TAX_INFORMATION = 'tax_information', 'Tax Information'
        CERTIFICATE_RATINGS = 'certificate_ratings', 'Certificate Ratings'

        # RISK_DESCRIPTION subsections
        PREPAYMENT_RISK = 'prepayment_risk', 'Prepayment Risk'
        INTEREST_RATE_RISK = 'interest_rate_risk', 'Interest Rate Risk'
        CREDIT_ENHANCEMENT_RISK = 'credit_enhancement_risk', 'Credit Enhancement Risk'

        # CERTIFICATE_DESCRIPTION subsections
        CERTIFICATE_CHARACTERISTICS = 'certificate_characteristics', 'Certificate Characteristics'
        LOSS_ALLOCATION = 'loss_allocation', 'Loss Allocation'
        SUBORDINATE_CERTIFICATES_PAYMENTS = 'subordinate_certificates_payments', 'Subordinate Certificates Payments'

        # COLLATERAL_DESCRIPTION subsections
        MORTGAGE_CHARACTERISTICS = 'loan_characteristics', 'Loan Characteristics'
        MORTGAGE_STATISTICS = 'loan_statistics', 'Loan Statistics'
        MORTGAGE_ASSIGNEMT = 'loan_assignment', 'Loan Assignment'

    class ClassificationMethod(models.TextChoices):
        """Methods used for classification."""
        RULE_EXACT = 'rule_exact', 'Rule-Based (Exact Match)'
        RULE_FUZZY = 'rule_fuzzy', 'Rule-Based (Fuzzy Match)'
        RULE_KEYWORD = 'rule_keyword', 'Rule-Based (Keyword Match)'
        LLM = 'llm', 'LLM Classification'
        MANUAL = 'manual', 'Manual Classification'

    prospectus = models.ForeignKey(
        Prospectus,
        on_delete=models.CASCADE,
        related_name='section_maps',
        db_column='prospectus_id'
    )
    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        db_index=True,
        help_text="Primary section category"
    )
    subcategory = models.CharField(
        max_length=50,
        choices=Subcategory.choices,
        null=True,
        blank=True,
        db_index=True,
        help_text="Detailed subcategory"
    )
    title = models.CharField(max_length=500, help_text="Original section title")
    page_start = models.IntegerField(help_text="Starting page number")
    page_end = models.IntegerField(help_text="Ending page number")
    level = models.IntegerField(default=1, help_text="Hierarchy level from index")
    parent_category = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Parent section's category"
    )
    confidence_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.0,
        help_text="Classification confidence (0.0-1.0)"
    )
    classification_method = models.CharField(
        max_length=20,
        choices=ClassificationMethod.choices,
        default=ClassificationMethod.LLM
    )
    content_summary = models.TextField(blank=True, help_text="Brief content summary")
    keywords = models.JSONField(default=list, blank=True, help_text="Extracted keywords")
    page_numbers = models.JSONField(default=list, help_text="All page numbers in section")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'section_map'
        ordering = ['prospectus', 'page_start']
        indexes = [
            models.Index(fields=['prospectus', 'category']),
            models.Index(fields=['prospectus', 'subcategory']),
            models.Index(fields=['prospectus', 'page_start', 'page_end']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['prospectus', 'title', 'page_start'],
                name='unique_section_per_prospectus'
            )
        ]

    def __str__(self):
        return f"{self.category} - {self.title[:50]} (Pages {self.page_start}-{self.page_end})"

    def get_page_range(self) -> range:
        """
        Get range object for all pages in section.

        Returns:
            range: Page range from start to end (inclusive)
        """
        # TODO: Implement page range helper
        pass

    def get_related_sections(self) -> 'models.QuerySet[SectionMap]':
        """
        Get related sections (same category, nearby pages).

        Returns:
            QuerySet: Related SectionMap objects
        """
        # TODO: Implement related sections query
        pass


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
