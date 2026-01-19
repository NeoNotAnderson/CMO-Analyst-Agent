"""
LangGraph definition for the Query Agent.

ReAct pattern implementation with simple agent loop.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from .state import QueryState
from .nodes import agent_node, should_continue, TOOLS
from langchain_core.messages import HumanMessage, SystemMessage
from .prompts import QUERY_AGENT_SYSTEM_PROMPT
import uuid


def create_query_graph(checkpointer=None):
    """
    Create the ReAct query agent graph with optional checkpointing.

    Workflow (ReAct Loop):
    1. agent_node -> Agent reasons about the query and decides to call tools or respond
    2. Conditional edge:
       - If agent made tool calls -> "tools" (ToolNode executes tools)
       - If no tool calls -> "END" (agent has final response)
    3. tools -> agent_node (tool results feed back to agent for next reasoning step)

    Simple structure:
    - START -> agent_node
    - agent_node -> [should_continue] -> tools OR END
    - tools -> agent_node (loop back)

    Args:
        checkpointer: Optional PostgresSaver for state persistence.
                     If provided, enables conversation memory across invocations.

    Returns:
        Compiled LangGraph with checkpointing enabled (if checkpointer provided)
    """
    # Initialize the graph
    workflow = StateGraph(QueryState)

    # Add nodes and conditional edges
    workflow.add_node('agent', agent_node)
    workflow.add_node('tools', ToolNode(TOOLS))
    workflow.add_edge(START, 'agent')
    workflow.add_conditional_edges(
        'agent',
        should_continue,
        {
            'continue': 'tools',
            'end': END
        }
    )
    workflow.add_edge('tools', 'agent')

    # Compile with checkpointer for persistence
    app = workflow.compile(checkpointer=checkpointer)
    return app


def run_agent(session_id: str, user_query: str, user_id: str = None, config=None):
    """
    Run the query agent on a user's question with conversation persistence.

    This is the main entry point for processing user queries through the agent.
    Uses LangGraph checkpointing to maintain conversation history across turns.

    Args:
        session_id: User session identifier (required for tracking active prospectus)
        user_query: The user's question
        user_id: User ID for thread management (required for persistence)
        config: Optional config dict for callbacks, etc.
                Example: {"callbacks": [callback_handler]}

    Returns:
        Final state after agent execution, including the agent's response

    Example usage:
        result = run_agent(
            session_id="user123",
            user_query="What is a Z-tranche?",
            user_id="1"
        )
        response = result['messages'][-1].content
        print(response)
    """
    # Get session info to populate state
    from api.views import _SESSION_STORE
    from .checkpoint import get_or_create_checkpointer
    from core.models import ConversationThread, Prospectus
    from django.contrib.auth.models import User

    session_data = _SESSION_STORE.get(session_id, {})
    active_prospectus_id = session_data.get('active_prospectus_id')
    prospectus_name = session_data.get('active_prospectus_name')

    # Get or create conversation thread
    thread_id = None
    if user_id and active_prospectus_id:
        try:
            user_obj = User.objects.get(id=user_id)
            prospectus_obj = Prospectus.objects.get(prospectus_id=active_prospectus_id)

            # Get or create thread
            thread, created = ConversationThread.objects.get_or_create(
                user=user_obj,
                prospectus=prospectus_obj
            )
            thread_id = str(thread.thread_id)

            if created:
                print(f"[QUERY AGENT] Created new conversation thread: {thread_id}")
            else:
                print(f"[QUERY AGENT] Using existing conversation thread: {thread_id}")
        except Exception as e:
            print(f"[QUERY AGENT] Warning: Could not create thread: {e}")

    # Create user message
    user_message = HumanMessage(content=user_query)

    # Build config with thread_id for checkpointing
    if config is None:
        config = {}

    if thread_id:
        config["configurable"] = {"thread_id": thread_id}

    # Get checkpointer and create agent (still used for tool call continuity)
    checkpointer = get_or_create_checkpointer() if thread_id else None
    agent = create_query_graph(checkpointer=checkpointer)

    # Use semantic search to get relevant conversation history
    from .conversation_memory import search_relevant_conversation_history, format_conversation_context

    relevant_history = []
    conversation_context = ""

    if thread_id:
        # Search for semantically relevant past messages
        relevant_history = search_relevant_conversation_history(
            thread_id=thread_id,
            current_query=user_query,
            top_k=3,  # Retrieve top 3 semantically similar exchanges
            recent_k=4  # Always include 4 most recent messages
        )

        # Format as context string for system message
        conversation_context = format_conversation_context(relevant_history)

        print(f"[CONVERSATION_MEMORY] Retrieved {len(relevant_history)} relevant messages")
        if relevant_history:
            print(f"[CONVERSATION_MEMORY] Similarity scores: {[f'{m['similarity_score']:.2f}' for m in relevant_history[:5]]}")

    # Build system message with conversation context
    system_content = QUERY_AGENT_SYSTEM_PROMPT
    if conversation_context:
        system_content = f"{QUERY_AGENT_SYSTEM_PROMPT}\n\n{conversation_context}"

    system_message = SystemMessage(content=system_content)

    # Always build fresh state with:
    # 1. System message (with embedded conversation context)
    # 2. Current user message
    # LangGraph checkpointing still handles tool call continuity within a single turn
    state = {
        'session_id': session_id,
        'active_prospectus_id': active_prospectus_id,
        'query_type': None,
        'prospectus_name': prospectus_name,
        'messages': [system_message, user_message],
        'errors': []
    }

    print(f"\n{'='*60}")
    print(f"[QUERY AGENT] Starting query")
    print(f"Session ID: {session_id}")
    print(f"Thread ID: {thread_id}")
    print(f"Query: {user_query}")
    print(f"Active Prospectus ID: {active_prospectus_id}")
    print(f"Prospectus Name: {prospectus_name}")
    print(f"Relevant History Messages: {len(relevant_history)}")
    print(f"{'='*60}\n")

    result = agent.invoke(state, config=config)

    print(f"\n{'='*60}")
    print(f"[QUERY AGENT] Query completed")
    print(f"{'='*60}\n")

    return result

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def extract_response(result: dict) -> str:
    """
    Extract the final text response from agent result.

    Args:
        result: Result dict from run_agent

    Returns:
        str: The agent's final response text
    """
    messages = result.get('messages', [])
    if not messages:
        return "No response generated"

    # Get the last message (should be the agent's final response)
    last_message = messages[-1]

    # Handle AIMessage
    if hasattr(last_message, 'content'):
        return last_message.content

    return str(last_message)


def get_session_info(session_id: str) -> dict:
    """
    Get current session information.

    Args:
        session_id: Session identifier

    Returns:
        dict: Session information including active prospectus
    """
    from .tools import _SESSION_STORE

    if session_id not in _SESSION_STORE:
        return {
            'session_id': session_id,
            'active_prospectus_id': None,
            'active_prospectus_name': None,
            'initialized': False
        }

    session = _SESSION_STORE[session_id]
    return {
        'session_id': session_id,
        'active_prospectus_id': session.get('active_prospectus_id'),
        'active_prospectus_name': session.get('active_prospectus_name'),
        'initialized': True
    }