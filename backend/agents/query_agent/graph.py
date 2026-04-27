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
from .rag_logger import log_query_start, log_query_end

# LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    LANGSMITH_AVAILABLE = False


def create_query_graph():
    """
    Create the ReAct query agent graph.

    Workflow (ReAct Loop):
    - START -> agent_node
    - agent_node -> [should_continue] -> tools OR END
    - tools -> agent_node (loop back)
    """
    workflow = StateGraph(QueryState)
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
    return workflow.compile()


@traceable(
    name="query_agent_execution",
    tags=["agent", "query"],
    metadata={
        "agent_type": "query_agent",
        "framework": "langgraph"
    }
)
def run_agent(session_id: str, user_query: str, user_id: str = None, config=None):
    """
    Run the query agent on a user's question.

    Args:
        session_id: User session identifier (required for tracking active prospectus)
        user_query: The user's question
        user_id: User ID for conversation thread management
        config: Optional config dict for LangSmith callbacks, etc.

    Returns:
        Final state after agent execution, including the agent's response
    """
    from api.views import _SESSION_STORE
    from core.models import ConversationThread, Prospectus
    from django.contrib.auth.models import User

    session_data = _SESSION_STORE.get(session_id, {})
    active_prospectus_id = session_data.get('active_prospectus_id')
    prospectus_name = session_data.get('active_prospectus_name')

    # Get or create conversation thread (used for conversation memory, not checkpointing)
    thread_id = None
    if user_id and active_prospectus_id:
        try:
            user_obj = User.objects.get(id=user_id)
            prospectus_obj = Prospectus.objects.get(prospectus_id=active_prospectus_id)
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
            print(f"[QUERY AGENT] Warning: Could not get/create thread: {e}")

    # Build LangSmith config (no thread_id — checkpointing removed)
    if config is None:
        config = {}
    config.setdefault("metadata", {}).update({
        "session_id": session_id,
        "user_id": user_id,
        "prospectus_id": active_prospectus_id,
        "prospectus_name": prospectus_name,
        "thread_id": thread_id,
        "query_length": len(user_query),
    })
    config.setdefault("tags", []).extend([
        "query_agent",
        f"prospectus:{prospectus_name}" if prospectus_name else "no_prospectus",
    ])

    # Retrieve relevant conversation history via semantic search
    from .conversation_memory import search_relevant_conversation_history, format_conversation_context

    relevant_history = []
    conversation_context = ""
    if thread_id:
        relevant_history = search_relevant_conversation_history(
            thread_id=thread_id,
            current_query=user_query,
            top_k=3,
            recent_k=4
        )
        conversation_context = format_conversation_context(relevant_history)
        print(f"[CONVERSATION_MEMORY] Retrieved {len(relevant_history)} relevant messages")
        if relevant_history:
            scores = [f"{m['similarity_score']:.2f}" for m in relevant_history[:5]]
            print(f"[CONVERSATION_MEMORY] Similarity scores: {scores}")

    # Build system message with embedded conversation context
    system_content = QUERY_AGENT_SYSTEM_PROMPT
    if conversation_context:
        system_content = f"{QUERY_AGENT_SYSTEM_PROMPT}\n\n{conversation_context}"

    state = {
        'session_id': session_id,
        'active_prospectus_id': active_prospectus_id,
        'query_type': None,
        'prospectus_name': prospectus_name,
        'messages': [SystemMessage(content=system_content), HumanMessage(content=user_query)],
        'errors': []
    }

    log_query_start(
        session_id=session_id,
        thread_id=thread_id,
        user_query=user_query,
        prospectus_id=active_prospectus_id,
        prospectus_name=prospectus_name,
    )

    print(f"\n{'='*60}")
    print(f"[QUERY AGENT] Starting query")
    print(f"Session ID:       {session_id}")
    print(f"Thread ID:        {thread_id}")
    print(f"Query:            {user_query}")
    print(f"Prospectus:       {prospectus_name} ({active_prospectus_id})")
    print(f"History messages: {len(relevant_history)}")
    print(f"{'='*60}\n")

    agent = create_query_graph()
    result = agent.invoke(state, config=config)

    messages = result.get("messages", [])
    last = messages[-1] if messages else None
    final_answer = last.content if last and hasattr(last, "content") else str(last)
    log_query_end(final_answer)

    print(f"\n{'='*60}")
    print(f"[QUERY AGENT] Query completed")
    print(f"{'='*60}\n")

    return result


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def extract_response(result: dict) -> str:
    messages = result.get('messages', [])
    if not messages:
        return "No response generated"
    last_message = messages[-1]
    if hasattr(last_message, 'content'):
        return last_message.content
    return str(last_message)


def get_session_info(session_id: str) -> dict:
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
