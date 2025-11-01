"""
Database models for CMO Analyst Agent.

This module defines the core data structures for storing:
- Prospectus documents
- Section mappings and extracted information
- Conversations and messages
- Generated TrancheSpeak scripts
"""

from django.db import models
import uuid


class Prospectus(models.Model):
    """
    Stores uploaded CMO prospectus documents.

    Attributes:
        id: UUID primary key
        file: Uploaded PDF file
        filename: Original filename
        deal_name: Name of the CMO deal (extracted from prospectus)
        upload_date: Timestamp of upload
        file_size: Size of the file in bytes
        processing_status: Current processing state
        metadata: Additional metadata as JSON
    """

    class ProcessingStatus(models.TextChoices):
        """Processing status choices."""
        UPLOADED = 'uploaded', 'Uploaded'
        PARSING = 'parsing', 'Parsing'
        PARSED = 'parsed', 'Parsed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='prospectus/')
    filename = models.CharField(max_length=255)
    deal_name = models.CharField(max_length=255, null=True, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    file_size = models.BigIntegerField()
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.UPLOADED
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'prospectus'
        ordering = ['-upload_date']

    def __str__(self):
        return f"{self.deal_name or self.filename} - {self.processing_status}"


class SectionMapping(models.Model):
    """
    Stores parsed sections from prospectus with their content and classification.

    Each section represents a distinct part of the prospectus (e.g., Deal Summary,
    Tranche Details, Payment Priority, etc.) with the extracted text content.

    Attributes:
        id: UUID primary key
        prospectus: Foreign key to Prospectus
        section_type: Type of section (deal_summary, tranche_list, etc.)
        section_title: Title/heading of the section
        content: Extracted text content
        page_numbers: List of page numbers where this section appears
        confidence_score: LLM confidence in classification (0-1)
        metadata: Additional metadata as JSON
        created_at: Timestamp of creation
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prospectus = models.ForeignKey(
        Prospectus,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    section_type = models.CharField(
        max_length=50,
        choices=SectionType.choices
    )
    section_title = models.CharField(max_length=500)
    content = models.TextField()
    page_numbers = models.JSONField(default=list)
    confidence_score = models.FloatField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'section_mapping'
        ordering = ['prospectus', 'section_type']
        indexes = [
            models.Index(fields=['prospectus', 'section_type']),
        ]

    def __str__(self):
        return f"{self.section_type} - {self.section_title[:50]}"


class Conversation(models.Model):
    """
    Stores conversation sessions between user and agent.

    Each conversation is tied to a specific prospectus and maintains
    the chat history and context.

    Attributes:
        id: UUID primary key
        prospectus: Foreign key to Prospectus
        title: Conversation title (auto-generated or user-provided)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
        is_active: Whether conversation is still active
        metadata: Additional metadata (e.g., user preferences)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prospectus = models.ForeignKey(
        Prospectus,
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    title = models.CharField(max_length=255, default='New Conversation')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'conversation'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} - {self.prospectus.deal_name}"


class Message(models.Model):
    """
    Stores individual messages within a conversation.

    Attributes:
        id: UUID primary key
        conversation: Foreign key to Conversation
        role: Message sender (user, assistant, system)
        content: Message content
        message_type: Type of message (text, script_generation, etc.)
        metadata: Additional data (tool calls, retrieved context, etc.)
        created_at: Timestamp of creation
    """

    class Role(models.TextChoices):
        """Message sender roles."""
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'
        SYSTEM = 'system', 'System'

    class MessageType(models.TextChoices):
        """Types of messages."""
        TEXT = 'text', 'Text'
        SCRIPT_GENERATION = 'script_generation', 'Script Generation'
        QUERY_ANALYSIS = 'query_analysis', 'Query Analysis'
        ERROR = 'error', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    message_type = models.CharField(
        max_length=30,
        choices=MessageType.choices,
        default=MessageType.TEXT
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'message'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class TrancheScript(models.Model):
    """
    Stores generated TrancheSpeak scripts.

    Attributes:
        id: UUID primary key
        prospectus: Foreign key to Prospectus
        script_content: Generated TrancheSpeak script
        version: Version number for tracking iterations
        generation_status: Status of script generation
        validation_errors: Any validation errors in JSON format
        created_at: Timestamp of creation
        created_by_message: Optional link to message that triggered generation
    """

    class GenerationStatus(models.TextChoices):
        """Script generation status."""
        GENERATING = 'generating', 'Generating'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        VALIDATING = 'validating', 'Validating'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prospectus = models.ForeignKey(
        Prospectus,
        on_delete=models.CASCADE,
        related_name='scripts'
    )
    script_content = models.TextField()
    version = models.IntegerField(default=1)
    generation_status = models.CharField(
        max_length=20,
        choices=GenerationStatus.choices,
        default=GenerationStatus.GENERATING
    )
    validation_errors = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_scripts'
    )

    class Meta:
        db_table = 'tranche_script'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['prospectus', '-version']),
        ]

    def __str__(self):
        return f"Script v{self.version} for {self.prospectus.deal_name}"
