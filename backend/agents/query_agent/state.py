"""
State definitions for the Query Agent.

This module defines the state schema that flows through the LangGraph nodes.
"""

from typing import List, Dict, Optional
from langgraph.graph import MessagesState


class QueryState(MessagesState):
    """
    State for the query agent workflow.

    Inherits from MessagesState to get 'messages' field for ReAct agent communication.

    Attributes:
        messages: List of messages (inherited from MessagesState) - agent reasoning/tool calls
                 Note: Retrieved section content is passed through messages (ToolMessage),
                 implementing a RAG pattern where the agent sees retrieved content in context
        session_id: Session identifier for tracking user sessions
        active_prospectus_id: UUID of the currently active prospectus for this session
        query_type: Type of query (general_cmo, deal_specific)
        prospectus_name: Name of the active prospectus (for display)
        errors: List of error messages if any
    """

    session_id: str
    active_prospectus_id: Optional[str]
    query_type: Optional[str]
    prospectus_name: Optional[str]
    errors: List[str]
