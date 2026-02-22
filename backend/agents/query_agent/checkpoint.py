"""
LangGraph Checkpoint Configuration for Query Agent.

This module provides the PostgresSaver instance for persisting agent state
across conversation turns.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from django.conf import settings
import psycopg


def get_checkpointer():
    """
    Create and return a PostgresSaver instance for LangGraph checkpointing.

    Uses Django database settings to connect to PostgreSQL.

    Returns:
        PostgresSaver: Configured checkpointer for agent state persistence

    Example usage:
        checkpointer = get_checkpointer()
        agent = create_query_graph(checkpointer)
    """
    # Extract database settings from Django
    db_config = settings.DATABASES['default']

    # Build PostgreSQL connection string
    # Format: postgresql://user:password@host:port/dbname
    connection_string = (
        f"postgresql://{db_config['USER']}:{db_config['PASSWORD']}"
        f"@{db_config['HOST']}:{db_config['PORT']}/{db_config['NAME']}"
    )

    # Create connection with autocommit for setup
    # This is required because PostgresSaver.setup() uses CREATE INDEX CONCURRENTLY
    # which cannot run inside a transaction block
    conn = psycopg.connect(connection_string, autocommit=True)

    # Create and return PostgresSaver
    # This will automatically create the necessary checkpoint tables if they don't exist
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()  # Initialize checkpoint tables

    return checkpointer


# Singleton instance (created once, reused across requests)
_CHECKPOINTER = None


def get_or_create_checkpointer():
    """
    Get or create a singleton PostgresSaver instance.

    This ensures we reuse the same database connection across requests
    for better performance.

    Returns:
        PostgresSaver: Singleton checkpointer instance
    """
    global _CHECKPOINTER

    if _CHECKPOINTER is None:
        _CHECKPOINTER = get_checkpointer()

    return _CHECKPOINTER
