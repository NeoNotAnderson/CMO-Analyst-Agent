"""
State definitions for the Parsing Agent.

This module defines the state schema that flows through the LangGraph nodes.
"""

from typing import List, Dict
from langgraph.graph import MessagesState
from core.models import Prospectus


class ParsingState(MessagesState):
    """
    State for the ReAct parsing agent.

    Inherits from MessagesState to get the 'messages' field for ReAct agent communication.

    Attributes:
        messages: List of messages (inherited from MessagesState) - used for agent reasoning and tool calls
        prospectus: The Prospectus object being parsed (contains all prospectus data)
        errors: List of error messages if any
    """

    prospectus: Prospectus
    #after implementig the classify logic, we can add this one:
    #section_map: Dict[str, List[Dict]]
    errors: List[str]
