"""
LangGraph definition for the Parsing Agent.

ReAct pattern implementation with simple agent loop.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from .state import ParsingState
from .nodes import agent_node, should_continue, TOOLS
from langchain_core.messages import HumanMessage, SystemMessage
from core.models import Prospectus

def create_parsing_graph():
    """
    Create the ReAct parsing agent graph.

    Workflow (ReAct Loop):
    1. agent_node -> Agent reasons and decides to call tools or finish
    2. Conditional edge:
       - If agent made tool calls -> "tools" (ToolNode executes tools)
       - If no tool calls -> "END" (parsing complete)
    3. tools -> agent_node (tool results feed back to agent for next reasoning step)

    Simple structure:
    - START -> agent_node
    - agent_node -> [should_continue] -> tools OR END
    - tools -> agent_node (loop back)

    Returns:
        Compiled LangGraph
    """
    # Initialize the graph
    workflow = StateGraph(ParsingState)

    # Add nodes and conditional edges
    workflow.add_node('agent', agent_node)
    workflow.add_node('tool', ToolNode(TOOLS))
    workflow.add_edge(START, 'agent')
    workflow.add_conditional_edges(
        'agent',
        should_continue,
        {
            'continue': 'tool',
            'end': END
        }
    )
    workflow.add_edge('tool', 'agent')
    app = workflow.compile()
    return app

def run_agent(prospectus: Prospectus, config=None):
    """
    Run the parsing agent on a prospectus.

    Args:
        prospectus: Prospectus object to parse
        config: Optional config dict for callbacks, etc.
                Example: {"callbacks": [callback_handler]}

    Returns:
        Final state after agent execution
    """
    system_message = SystemMessage(content=
        f"""
        You are a financial document parsing assistant specialized in CMO prospectuses.

        Your task is to parse the prospectus and save all structured information to the database.

        The prospectus ID is: {prospectus.prospectus_id}
        The prospectus name is: {prospectus.prospectus_name}

        Available tools allow you to:
        - Check if parsing is already complete (use prospectus_id)
        - Parse index pages to understand document structure
        - Parse individual sections and pages
        - Save results to database (use prospectus_id)

        IMPORTANT CONSTRAINTS:
        - When converting pages to images, ONLY convert 1-2 pages at a time (maximum)
        - When parsing images with OpenAI, ONLY send 1-2 pages at a time
        - Processing too many pages at once will exceed token limits

        WORKFLOW:
        1. Check the parse status using check_parse_status
        2. Based on the status, execute the required steps:
           - If status is 'pending' or 'parsing_index':
             * Determine doc type
             * Find index pages
             * Convert index pages to images (max 2 pages at a time)
             * Parse index images with OpenAI
           - If status is 'parsing_sections':
             * Call parse_prospectus_with_parsed_index (this is ONE tool call)
           - If status is 'completed':
             * Parsing is already done, report success

        Think step by step and use the appropriate tools to complete the parsing task.
        Use the prospectus_id when calling tools that require it.
        """)

    user_message = HumanMessage(content=f"Parse the CMO prospectus with ID {prospectus.prospectus_id}. Parsing consists of two steps: (1) parse the index to get the file structure, (2) parse the rest based on the index, Use the tools provided and save results to database.")
    state = {
        'prospectus': prospectus,
        'messages': [system_message, user_message],
        'errors': []
    }
    agent = create_parsing_graph()
    return agent.invoke(state, config=config)