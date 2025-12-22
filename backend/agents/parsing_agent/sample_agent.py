from tools import *
from typing import TypedDict, Dict, List, Annotated
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain.messages import HumanMessage, SystemMessage
from langchain_core.messages import BaseMessage
from dotenv import load_dotenv
import os
import operator

load_dotenv()
api_key=os.getenv("OPENAI_API_KEY")
llm = OpenAI(model='gpt-5-nano', api_key=api_key)
tools = [find_index_pages, parsed_pages_exist_in_db, convert_pages_to_images, parse_page_images_with_openai, build_prompt_for_index_parsing, store_parsed_pages_in_db]
llm_with_tools = llm.bind_tools(tools)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    file_name: str
    count: int

def agent(state: AgentState):
    messages = state['messages']
    state['count'] += 1
    response = llm_with_tools.invoke(messages)
    return {'message': [response]}

def should_continue(state: AgentState):
    last_message = state['message'][-1]
    if not hasattr(last_message, "tool_calls") and not last_message.tool_calls:
        return "end"
    return "continue"

workflow = StateGraph(AgentState)
workflow.add_node('agent', agent)
workflow.add_node('tools', ToolNode(tools))

workflow.add_conditional_edges(
    'agent',
    should_continue, 
    {
        'continue': 'tools',
        'end': END
    }
)
workflow.add_edge('tools', 'agent')
app = workflow.compile()

def run_agent(file_name: str):
    system_message = SystemMessage(content="You are an financial assistant who will help me extract the index page of a CMO prospectus.")
    user_message = HumanMessage(content=f"here is the CMO prospectus: {file_name}, please find the index pages and parse them into json object using the tools provided")
    state = AgentState()
    state['file_name'] = file_name
    state['messages'] = [system_message, user_message]
    state['count'] = 0
    resutls = app.invoke(state)

    for msg in resutls['messages']:
        if hasattr(msg, 'content') and not msg.content:
            #TODO: add the mesages in the database
            #TODO: extract the parsed index and put them in the database:
            print(msg.content)

if __name__ == "__main__":
    #TODO: in the future, run agent should be triggered automatically after user upload a file.
    run_agent('JPM03_supplement.pdf')
