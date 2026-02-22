"""
LangGraph nodes for the Query Agent.

ReAct pattern implementation with agent_node and conditional routing.
"""

from .state import QueryState
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from .prompts import QUERY_AGENT_SYSTEM_PROMPT
from .tools import ALL_TOOLS
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Initialize LLM with tools
# Note: LangChain automatically traces LLM calls when LANGCHAIN_TRACING_V2=true
# This is configured in settings.py and will capture all LLM invocations
llm = ChatOpenAI(
    model='gpt-5-nano',
    api_key=api_key,
    temperature=0,
    # Tracing is automatic via environment variables set in settings.py
)

# Define the list of tools available to the agent
TOOLS = ALL_TOOLS

# Bind tools to LLM
llm_with_tools = llm.bind_tools(TOOLS, seed=None)


def agent_node(state: QueryState) -> QueryState:
    """
    ReAct agent node that autonomously handles user queries.

    The agent will:
    1. Receive the current state (including message history)
    2. Reason about the query type and what information is needed
    3. Decide which tool(s) to call (if any)
    4. Return updated state with agent response

    For general_cmo queries: Agent responds directly using CMO knowledge
    For deal_specific queries: Agent uses tools to retrieve prospectus data

    Args:
        state: Current query state with messages and session info

    Returns:
        Updated state with agent's response and tool calls
    """
    messages = state['messages']

    # Build session context string to inject into system message
    session_context = f"""
CURRENT SESSION CONTEXT:
- Session ID: {state.get('session_id', 'N/A')}
- Active Prospectus ID: {state.get('active_prospectus_id', 'None')}
- Active Prospectus Name: {state.get('prospectus_name', 'None')}
"""

    # Add system prompt with session context as first message if not already present
    if not messages or not isinstance(messages[0], SystemMessage):
        full_prompt = QUERY_AGENT_SYSTEM_PROMPT + "\n\n" + session_context
        messages = [SystemMessage(content=full_prompt)] + messages
    else:
        # Update existing system message with current session context
        full_prompt = QUERY_AGENT_SYSTEM_PROMPT + "\n\n" + session_context
        messages[0] = SystemMessage(content=full_prompt)

    print(f"\n[QUERY AGENT NODE] Calling LLM with {len(messages)} messages")
    print(f"[QUERY AGENT NODE] Session ID: {state.get('session_id', 'N/A')}")
    print(f"[QUERY AGENT NODE] Active Prospectus: {state.get('active_prospectus_id', 'None')}")

    response = llm_with_tools.invoke(messages)

    # Debug tool calls
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print(f"[QUERY AGENT NODE] LLM requested {len(response.tool_calls)} tool call(s):")
        for i, tool_call in enumerate(response.tool_calls):
            print(f"  {i+1}. {tool_call['name']}")
    else:
        print(f"[QUERY AGENT NODE] No tool calls - direct response")

    return {'messages': [response]}


def should_continue(state: QueryState) -> str:
    """
    Conditional edge function to decide next step in ReAct loop.

    Decision logic:
    - If last agent response has tool calls -> route to "tools" (ToolNode)
    - If no tool calls -> route to "END" (agent finished, has final response)

    Args:
        state: Current query state

    Returns:
        "continue" to execute tool calls, "end" to finish
    """
    last_message = state['messages'][-1]

    # Check if the last message has tool calls
    if not getattr(last_message, "tool_calls", None):
        print("[QUERY AGENT] No more tool calls - ending conversation turn")
        return "end"

    print("[QUERY AGENT] Tool calls present - continuing to ToolNode")
    return "continue"