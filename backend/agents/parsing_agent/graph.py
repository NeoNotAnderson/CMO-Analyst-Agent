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

def run_agent(prospectus: Prospectus):
    system_message = SystemMessage(content=
        """
        You are a financial document parsing assistant specialized in CMO prospectuses.

        Your task is to parse the prospectus and save all structured information to the database.

        Available tools allow you to:
        - Check if parsing is already complete
        - Parse index pages to understand document structure  
        - Parse individual sections and pages
        - Save results to database

        Think step by step and use the appropriate tools to complete the parsing task.
        """)
    
    user_message = HumanMessage(content=f"Here is the CMO prospectus: {prospectus.prospectus_name}, parsing is consist of two steps, you need to first parse the index, from which you can get the file strcuture. After that, parse the rest of the file based on the parsed index. Use the tools provided and save the result to database.")
    state = {
        'prospectus': prospectus,
        'messages': [system_message, user_message],
        'errors': []
    }
    agent = create_parsing_graph()
    return agent.invoke(state)