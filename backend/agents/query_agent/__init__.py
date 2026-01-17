"""
Query Agent for CMO Analyst Agent.

Main entry point for query processing and user interaction.
"""

from .graph import (
    create_query_graph,
    run_agent,
    extract_response,
    get_session_info
)

from .tools import (
    # Agent tools
    classify_query,
    get_prospectus_status,
    trigger_parsing_agent,
    analyze_query_sections,
    retrieve_sections,
    ALL_TOOLS
)

from .state import QueryState

__all__ = [
    # Main functions
    'create_query_graph',
    'run_agent',
    'extract_response',
    'get_session_info',

    # Agent tools (called by LLM during ReAct loop)
    'classify_query',
    'get_prospectus_status',
    'trigger_parsing_agent',
    'analyze_query_sections',
    'retrieve_sections',

    # Tool list (only contains agent tools)
    'ALL_TOOLS',

    # State
    'QueryState',
]