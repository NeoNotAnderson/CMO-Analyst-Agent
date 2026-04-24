# Generated migration for ProspectusChunk model with pgvector support

from django.db import migrations, models
import django.db.models.deletion
import uuid
from pgvector.django import VectorExtension, VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_conversationthread_chatmessage_agentcheckpoint_and_more'),
    ]

    operations = [
        # Enable pgvector extension (idempotent - safe to run multiple times)
        VectorExtension(),

        # Create ProspectusChunk model
        migrations.CreateModel(
            name='ProspectusChunk',
            fields=[
                ('chunk_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('chunk_text', models.TextField(help_text='The actual text content of this chunk')),
                ('chunk_index', models.IntegerField(db_index=True, help_text='Sequential position in document (0-indexed)')),
                ('embedding', VectorField(dimensions=1536, help_text='1536-dim embedding vector for semantic search')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Section path, page number, token count, table flags, etc.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('prospectus', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='core.prospectus')),
            ],
            options={
                'db_table': 'prospectus_chunk',
                'ordering': ['prospectus', 'chunk_index'],
            },
        ),

        # Add indexes
        migrations.AddIndex(
            model_name='prospectuschunk',
            index=models.Index(fields=['prospectus', 'chunk_index'], name='prospectus_chunk_prosp_idx'),
        ),
        migrations.AddIndex(
            model_name='prospectuschunk',
            index=models.Index(fields=['prospectus', 'created_at'], name='prospectus_chunk_created_idx'),
        ),

        # Add unique constraint
        migrations.AddConstraint(
            model_name='prospectuschunk',
            constraint=models.UniqueConstraint(fields=['prospectus', 'chunk_index'], name='unique_chunk_index_per_prospectus'),
        ),
    ]
