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


class ConversationThread(models.Model):
    """
    Represents a conversation thread between a user and a specific prospectus.
    One thread per (user, prospectus) combination.

    Attributes:
        thread_id: UUID primary key
        user: Foreign key to User who owns this conversation
        prospectus: Foreign key to the prospectus being discussed
        created_at: Timestamp when thread was created
        updated_at: Timestamp of last activity
    """
    thread_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_threads')
    prospectus = models.ForeignKey(Prospectus, on_delete=models.CASCADE, related_name='conversation_threads')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversation_thread'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'prospectus'],
                name='unique_thread_per_user_prospectus'
            )
        ]

    def __str__(self):
        return f"Thread {self.thread_id} - {self.user.username} + {self.prospectus.prospectus_name}"


class ChatMessage(models.Model):
    """
    Stores individual chat messages within a conversation thread.

    Attributes:
        message_id: UUID primary key
        thread: Foreign key to ConversationThread
        role: Message role (user, assistant, system, tool)
        content: Message content text
        tool_calls: JSON field for tool call data (if role is assistant)
        tool_call_id: ID for tool response messages (if role is tool)
        created_at: Timestamp when message was created
        metadata: Additional metadata as JSON
    """

    class MessageRole(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'
        SYSTEM = 'system', 'System'
        TOOL = 'tool', 'Tool'

    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(ConversationThread, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=MessageRole.choices)
    content = models.TextField()
    tool_calls = models.JSONField(default=list, blank=True, null=True)
    tool_call_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'chat_message'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'created_at']),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class AgentCheckpoint(models.Model):
    """
    Stores LangGraph checkpoints for agent state persistence.
    Used by LangGraph's PostgresSaver.

    Attributes:
        checkpoint_id: UUID primary key
        thread: Foreign key to ConversationThread
        checkpoint_ns: Checkpoint namespace (default: '')
        checkpoint: Serialized checkpoint data (JSON)
        metadata: Checkpoint metadata (JSON)
        parent_checkpoint_id: Foreign key to parent checkpoint (for branching)
        created_at: Timestamp when checkpoint was created
    """
    checkpoint_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(ConversationThread, on_delete=models.CASCADE, related_name='checkpoints')
    checkpoint_ns = models.CharField(max_length=255, default='', blank=True)
    checkpoint = models.JSONField()
    metadata = models.JSONField(default=dict, blank=True)
    parent_checkpoint_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agent_checkpoint'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['thread', 'checkpoint_ns', 'created_at']),
        ]

    def __str__(self):
        return f"Checkpoint {self.checkpoint_id} for thread {self.thread_id}"

