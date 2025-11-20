"""
State definitions for the Query Agent.

This module defines the state schema that flows through the LangGraph nodes.
"""

from typing import TypedDict, List, Dict, Optional


class QueryState(TypedDict):
    """
    State for the query agent workflow.

    Attributes:
        prospectus_id: UUID of the prospectus being queried
        user_query: The user's question
        query_type: Type of query (generic_cmo, deal_specific, script_generation)
        retrieved_context: Relevant sections retrieved from database
        analysis: LLM analysis of the query
        response: Final response to the user
        should_generate_script: Whether to generate TrancheSpeak script
        script_content: Generated script if applicable
        errors: List of error messages if any
        metadata: Additional metadata (confidence scores, sources, etc.)
    """

    prospectus_id: Optional[str]
    user_query: str
    query_type: str
    retrieved_context: List[Dict]
    analysis: str
    response: str
    should_generate_script: bool
    script_content: Optional[str]
    errors: List[str]
    metadata: Dict
