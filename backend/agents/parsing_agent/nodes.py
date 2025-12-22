"""
LangGraph nodes for the Parsing Agent.

ReAct pattern implementation with agent_node and conditional routing.
"""

from .state import ParsingState
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
import os
from .tools import (
    check_parsed_index_exists,
    save_parsed_index_to_db,
    parse_prospectus_with_parsed_index,
    classify_sections_with_llm,
    determin_doc_type,
    find_index_pages,
    convert_pages_to_images,
    parse_page_images_with_openai,
    build_prompt_for_index_parsing
)

load_dotenv()
api_key=os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(model='gpt-5-nano', api_key=api_key)
# Define the list of tools available to the agent
# Mix of granular tools and one complex orchestration tool (parse_prospectus_with_parsed_index)
TOOLS = [
    check_parsed_index_exists,
    save_parsed_index_to_db,
    parse_prospectus_with_parsed_index,
    classify_sections_with_llm,
    determin_doc_type,
    find_index_pages,
    convert_pages_to_images,
    parse_page_images_with_openai,
    build_prompt_for_index_parsing
]
llm_with_tools = llm.bind_tools(TOOLS)

def agent_node(state: ParsingState) -> ParsingState:
    """
    ReAct agent node that autonomously selects and calls tools.

    The agent will:
    1. Receive the current state (including message history)
    2. Reason about what needs to be done
    3. Decide which tool(s) to call (if any)
    4. Return updated state with agent response

    Args:
        state: Current parsing state with messages

    Returns:
        Updated state with agent's response and tool calls
    """
    messages = state['messages']
    response = llm_with_tools.invoke(messages)
    return {'messages': [response]}

def should_continue(state: ParsingState) -> str:
    """
    Conditional edge function to decide next step in ReAct loop.

    Decision logic:
    - If last agent response has tool calls -> route to "tools" (ToolNode)
    - If parsing is complete -> route to "END"
    - Otherwise -> route to "END" (agent finished reasoning)

    Args:
        state: Current parsing state

    Returns:
        "tools" to execute tool calls, "END" to finish
    """
    last_message = state['messages'][-1]
    if not getattr(last_message, "tool_calls", None):
        return "end"
    return "continue"
