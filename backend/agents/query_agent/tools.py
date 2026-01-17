"""
Tools for the Query Agent.

This module provides tools for query classification, prospectus management,
section retrieval, and parsing coordination.
"""

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize LLM for tool implementations
llm = ChatOpenAI(
    model='gpt-5-nano',
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0
)


# Import session store from API views (shared state)
from api.views import _SESSION_STORE

# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class QueryClassification(BaseModel):
    """Schema for query classification."""
    query_type: str = Field(description="Either 'general_cmo' or 'deal_specific'")
    reasoning: str = Field(description="Brief explanation for the classification")


class SectionAnalysis(BaseModel):
    """Schema for section analysis."""
    categories: List[str] = Field(description="List of relevant categories to retrieve from the prospectus")
    reasoning: str = Field(description="Brief explanation for the section selection")


# ============================================================================
# TOOLS: BASIC QUERY AGENT
# ============================================================================

@tool
def classify_query(user_query: str) -> str:
    """
    Classify user query into question type.

    Determines whether the user is asking a general CMO question or a
    deal-specific question that requires prospectus data.

    Args:
        user_query: The user's question

    Returns:
        str: "general_cmo" or "deal_specific"

    Examples:
        "What is a Z-tranche?" → "general_cmo"
        "What tranches are in this deal?" → "deal_specific"
    """
    from .prompts import CLASSIFICATION_PROMPT

    structured_llm = llm.with_structured_output(QueryClassification)
    prompt = CLASSIFICATION_PROMPT.format(query=user_query)
    result = structured_llm.invoke(prompt)

    return result.query_type


@tool
def get_prospectus_status(prospectus_id: str) -> str:
    """
    Get parsing status of a prospectus.

    Args:
        prospectus_id: Prospectus UUID

    Returns:
        str: JSON with status details
    """
    from core.models import Prospectus

    try:
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)

        # Count sections from parsed_file
        sections_count = 0
        if prospectus.parsed_file and 'sections' in prospectus.parsed_file:
            sections_count = len(prospectus.parsed_file['sections'])

        status_info = {
            'prospectus_id': str(prospectus.prospectus_id),
            'prospectus_name': prospectus.prospectus_name,
            'parse_status': prospectus.parse_status,
            'sections_parsed': sections_count,
            'upload_date': prospectus.upload_date.isoformat()
        }

        return json.dumps(status_info, indent=2)

    except Prospectus.DoesNotExist:
        return f"Error: Prospectus with ID {prospectus_id} not found."


@tool
def trigger_parsing_agent(prospectus_id: str) -> str:
    """
    Trigger the Parsing Agent to parse a prospectus.

    This tool starts the parsing process asynchronously. The user should
    be informed that parsing may take several minutes.

    Args:
        prospectus_id: Prospectus UUID

    Returns:
        str: Confirmation that parsing has started
    """
    from core.models import Prospectus
    import threading

    try:
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)

        # Import and run parsing agent in background
        from agents.parsing_agent.graph import run_agent

        def run_parsing():
            try:
                run_agent(prospectus)
            except Exception as e:
                prospectus.parse_status = Prospectus.ParseStatus.FAILED
                prospectus.metadata['error'] = str(e)
                prospectus.save()

        thread = threading.Thread(target=run_parsing, daemon=True)
        thread.start()

        return f"Parsing started for prospectus '{prospectus.prospectus_name}'. This may take 5-10 minutes depending on document size. Please check back shortly."

    except Prospectus.DoesNotExist:
        return f"Error: Prospectus with ID {prospectus_id} not found."


# ============================================================================
# TOOLS: DEAL-SPECIFIC PATH
# ============================================================================

@tool
def analyze_query_sections(user_query: str, prospectus_id: str) -> str:
    """
    Analyze which prospectus sections are relevant to the query.

    Args:
        user_query: The user's question
        prospectus_id: Prospectus UUID

    Returns:
        str: JSON with relevant categories

    Example output:
        {
            "categories": ["payment_priority", "offered_certificates"],
            "reasoning": "User is asking about payment waterfall..."
        }
    """
    from core.models import Prospectus
    from .prompts import SECTION_ANALYSIS_PROMPT

    try:
        # Get prospectus with parsed_file
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)
        parsed_file = prospectus.parsed_file

        if not parsed_file or 'sections' not in parsed_file:
            return json.dumps({
                "error": "No sections available for this prospectus. It may not be fully parsed yet.",
                "categories": []
            })

        # Collect all available categories from parsed_file
        available_categories = set()
        _collect_categories_recursive(parsed_file['sections'], available_categories)

        if not available_categories:
            return json.dumps({
                "error": "No classified sections found in this prospectus.",
                "categories": []
            })

        # Use LLM to identify relevant sections
        structured_llm = llm.with_structured_output(SectionAnalysis)
        prompt = SECTION_ANALYSIS_PROMPT.format(query=user_query)
        result = structured_llm.invoke(prompt)

        # Filter to only available categories
        filtered_categories = [c for c in result.categories if c in available_categories]

        return json.dumps({
            "categories": filtered_categories,
            "reasoning": result.reasoning
        })

    except Prospectus.DoesNotExist:
        return json.dumps({
            "error": f"Prospectus with ID {prospectus_id} not found.",
            "categories": []
        })


@tool
def retrieve_sections(prospectus_id: str, categories: str) -> str:
    """
    Retrieve section content from parsed_file based on categories.

    Args:
        prospectus_id: Prospectus UUID
        categories: JSON string with list of categories to retrieve

    Returns:
        str: Formatted section content with titles and page numbers

    Example output:
        ================================================================================
        Payment Priority (Page 25, Level 2)
        Category: payment_priority (Confidence: 0.98)
        ================================================================================

        [Section text content here...]


        ================================================================================
        Offered Certificates (Page 6, Level 2)
        Category: offered_certificates (Confidence: 0.95)
        ================================================================================

        [Section text content here...]
    """
    from core.models import Prospectus

    try:
        # Parse JSON input
        categories_list = json.loads(categories) if isinstance(categories, str) else categories

        # Get prospectus with parsed_file
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)
        parsed_file = prospectus.parsed_file

        if not parsed_file or 'sections' not in parsed_file:
            return "No sections available for this prospectus. It may not be fully parsed yet."

        # Collect matching sections recursively
        matching_sections = []
        _collect_matching_sections_recursive(
            parsed_file['sections'],
            categories_list,
            matching_sections
        )

        if not matching_sections:
            return f"No sections found matching the categories: {', '.join(categories_list)}"

        # Format sections with content
        result = []
        for section in matching_sections:
            title = section.get('title', 'Untitled')
            category = section.get('category', 'unclassified')
            confidence = section.get('confidence', 0.0)
            level = section.get('level', 1)
            page_num = section.get('page_num', 'Unknown')
            text = section.get('text', '[No content]')

            result.append(f"""
                            {'='*80}
                            {title} (Page {page_num}, Level {level})
                            Category: {category} (Confidence: {confidence:.2f})
                            {'='*80}

                            {text}
                            """)

        return "\n\n".join(result)

    except Prospectus.DoesNotExist:
        return f"Error: Prospectus with ID {prospectus_id} not found."
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON format in categories. {str(e)}"
    except Exception as e:
        return f"Error retrieving sections: {str(e)}"


def _collect_categories_recursive(sections: List, available_categories: set) -> None:
    """
    Recursively collect all unique categories from sections and nested sections.

    Args:
        sections: List of section dicts from parsed_file
        available_categories: Set to accumulate unique category values
    """
    for section in sections:
        category = section.get('category')
        if category:
            available_categories.add(category)

        # Recurse into nested sections (key is 'sections', not 'subsections')
        if 'sections' in section and section['sections']:
            _collect_categories_recursive(section['sections'], available_categories)


def _collect_matching_sections_recursive(
    sections: List,
    target_categories: List[str],
    matching_sections: List
) -> None:
    """
    Recursively collect sections that match any of the target categories.

    Args:
        sections: List of section dicts from parsed_file
        target_categories: List of category values to match
        matching_sections: List to accumulate matching section objects
    """
    for section in sections:
        category = section.get('category')

        # If this section matches, add it
        if category and category in target_categories:
            matching_sections.append(section)

        # Always recurse into nested sections (they might match even if parent doesn't)
        if 'sections' in section and section['sections']:
            _collect_matching_sections_recursive(
                section['sections'],
                target_categories,
                matching_sections
            )

# ============================================================================
# TOOL LISTS
# ============================================================================

ALL_TOOLS = [
    # Query classification and routing
    classify_query,

    # Prospectus management
    get_prospectus_status,

    # Parsing coordination
    trigger_parsing_agent,

    # Section analysis and retrieval
    analyze_query_sections,
    retrieve_sections,
]
