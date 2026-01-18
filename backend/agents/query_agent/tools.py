"""
Tools for the Query Agent.

This module provides tools for query classification, prospectus management,
section retrieval, and parsing coordination.
"""

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
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


class SectionReference(BaseModel):
    """Schema for a section reference with hierarchy information."""
    category: str = Field(description="Category name")
    parent: Optional[str] = Field(description="Parent category name, or null if top-level")


class SectionAnalysis(BaseModel):
    """Schema for section analysis with hierarchy."""
    sections: List[SectionReference] = Field(description="List of relevant sections with parent information")
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
        str: JSON with relevant sections including hierarchy information

    Example output:
        {
            "sections": [
                {"category": "deal_summary", "parent": null},
                {"category": "payment_priority", "parent": "deal_summary"},
                {"category": "offered_certificates", "parent": "deal_summary"}
            ],
            "reasoning": "User is asking about payment waterfall and tranches..."
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

        # Collect categories organized by top-level parent (hierarchy-aware)
        categories_by_parent = _collect_categories_recursive(parsed_file['sections'])

        if not categories_by_parent:
            return json.dumps({
                "error": "No classified sections found in this prospectus.",
                "categories": []
            })

        # Build a description of available categories for the LLM
        categories_info = []
        for parent, subcats in categories_by_parent.items():
            subcats_list = sorted(subcats - {parent})  # Exclude parent from subcats list
            if subcats_list:
                categories_info.append(f"- {parent}: {', '.join(subcats_list)}")
            else:
                categories_info.append(f"- {parent}")

        available_categories_desc = '\n'.join(categories_info)

        # Use LLM to identify relevant sections with hierarchy information
        structured_llm = llm.with_structured_output(SectionAnalysis)
        prompt = SECTION_ANALYSIS_PROMPT.format(
            query=user_query,
            available_categories=available_categories_desc
        )
        result = structured_llm.invoke(prompt)

        # Validate sections: ensure categories exist and parent relationships are correct
        all_valid_categories = set()
        for parent, subcats in categories_by_parent.items():
            all_valid_categories.update(subcats)

        # Build validated section list with hierarchy
        validated_sections = []
        top_level_categories_selected = set()

        # First pass: collect all top-level categories that were selected
        for section_ref in result.sections:
            category = section_ref.category
            parent = section_ref.parent

            if not parent and category in categories_by_parent:
                top_level_categories_selected.add(category)

        # Second pass: validate and filter sections
        for section_ref in result.sections:
            category = section_ref.category
            parent = section_ref.parent

            # Check if category exists
            if category not in all_valid_categories:
                continue

            # Validate parent relationship
            if parent:
                # This is a subcategory
                # Skip if its parent category was already selected (avoid duplication)
                if parent in top_level_categories_selected:
                    continue

                # Verify it's under the correct parent
                if parent in categories_by_parent and category in categories_by_parent[parent]:
                    validated_sections.append({
                        "category": category,
                        "parent": parent
                    })
            else:
                # This is a top-level category - verify it's actually top-level
                if category in categories_by_parent:
                    validated_sections.append({
                        "category": category,
                        "parent": None
                    })

        return json.dumps({
            "sections": validated_sections,
            "reasoning": result.reasoning
        })

    except Prospectus.DoesNotExist:
        return json.dumps({
            "error": f"Prospectus with ID {prospectus_id} not found.",
            "categories": []
        })


@tool
def retrieve_sections(prospectus_id: str, sections_data: str) -> str:
    """
    Retrieve section content from parsed_file based on section references with hierarchy.

    IMPORTANT FOR THE AGENT:
    - This tool retrieves the actual prospectus text content needed to answer the user's question
    - After calling this tool, you will receive the section content in the tool response
    - Use that content to formulate a detailed, accurate answer to the user's question
    - The content includes section titles, page numbers, and the full text from those sections

    Args:
        prospectus_id: Prospectus UUID
        sections_data: JSON string from analyze_query_sections output
                      Format: {"sections": [{"category": "...", "parent": "..."}], ...}

    Returns:
        str: Retrieved section content formatted with hierarchy breadcrumbs, OR an error message
    """
    from core.models import Prospectus

    try:
        # Parse JSON input
        data = json.loads(sections_data) if isinstance(sections_data, str) else sections_data

        # Extract section references with hierarchy info
        if not isinstance(data, dict) or 'sections' not in data:
            return "Error: Invalid sections_data format. Expected JSON with 'sections' key."

        section_refs = data['sections']

        # Get prospectus with parsed_file
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)
        parsed_file = prospectus.parsed_file

        if not parsed_file or 'sections' not in parsed_file:
            return "No sections available for this prospectus. It may not be fully parsed yet."

        # Collect matching sections using hierarchy-aware matching
        matching_sections = []
        for section_ref in section_refs:
            category = section_ref['category']
            parent = section_ref.get('parent')

            if parent:
                # This is a level 2 subcategory - find it under the specific parent
                _collect_matching_subsections(
                    parsed_file['sections'],
                    parent_category=parent,
                    target_category=category,
                    matching_sections=matching_sections
                )
            else:
                # This is a level 1 top-level category - find it at top level
                _collect_matching_top_level_sections(
                    parsed_file['sections'],
                    target_category=category,
                    matching_sections=matching_sections
                )

        if not matching_sections:
            requested = [f"{s.get('parent', 'TOP')} > {s['category']}" for s in section_refs]
            return f"No sections found matching the requested categories: {', '.join(requested)}"

        # Format sections with FULL content (proper RAG - no truncation)
        # Since analyze_query_sections returns max 3 sections, context size is manageable
        result = [f"Retrieved {len(matching_sections)} section(s) from the prospectus."]
        result.append("Use the following COMPLETE content to answer the user's question:\n")

        for idx, section in enumerate(matching_sections, 1):
            title = section.get('title', 'Untitled')
            category = section.get('category', 'unclassified')
            level = section.get('level', 1)
            page_num = section.get('page_num', 'Unknown')
            text = section.get('text', '[No content]')
            parent_title = section.get('_parent_title', None)  # Added by collection function

            # Build hierarchy breadcrumb
            if parent_title:
                hierarchy_path = f"{parent_title} > {title}"
            else:
                hierarchy_path = title

            # Return FULL text - no truncation (this is proper RAG)
            # The LLM context window is large enough to handle 3 full sections
            result.append(f"""
{'='*80}
SECTION {idx}: [{hierarchy_path}] (Page {page_num})
{'='*80}

{text}

""")

        return "\n".join(result)

    except Prospectus.DoesNotExist:
        return f"Error: Prospectus with ID {prospectus_id} not found."
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON format in categories. {str(e)}"
    except Exception as e:
        return f"Error retrieving sections: {str(e)}"


def _collect_categories_recursive(sections: List) -> Dict[str, set]:
    """
    Recursively collect categories organized by top-level parent category.

    This preserves the hierarchy to avoid ambiguity when subsection names might
    appear under different top-level sections.

    Args:
        sections: List of section dicts from parsed_file (top-level sections)

    Returns:
        Dictionary mapping top-level category -> set of subcategories under it
        Example: {
            'deal_summary': {'offered_certificates', 'payment_priority', 'key_dates'},
            'risk_factors': {'prepayment_risk', 'interest_rate_risk'}
        }
        Top-level categories also include themselves in the result.
    """
    categories_by_parent = {}

    for section in sections:
        category = section.get('category')
        level = section.get('level', 1)

        if not category:
            continue

        # This is a top-level section (level 1)
        if level == 1:
            # Add top-level category as a key with itself
            if category not in categories_by_parent:
                categories_by_parent[category] = {category}  # Include itself

            # Collect all subcategories under this top-level section
            if 'sections' in section and section['sections']:
                subcategories = _collect_subcategories(section['sections'])
                categories_by_parent[category].update(subcategories)

    return categories_by_parent


def _collect_subcategories(sections: List) -> set:
    """
    Recursively collect all subcategories from nested sections.

    Args:
        sections: List of subsection dicts

    Returns:
        Set of all category values found in these sections and their descendants
    """
    subcategories = set()

    for section in sections:
        category = section.get('category')
        if category:
            subcategories.add(category)

        # Recurse into deeper nested sections
        if 'sections' in section and section['sections']:
            deeper_subcats = _collect_subcategories(section['sections'])
            subcategories.update(deeper_subcats)

    return subcategories


def _collect_matching_top_level_sections(
    sections: List,
    target_category: str,
    matching_sections: List
) -> None:
    """
    Collect top-level sections (level 1) that match the target category.
    When a top-level section is matched, it includes all its subsections.

    Args:
        sections: List of top-level section dicts from parsed_file
        target_category: Category value to match at level 1
        matching_sections: List to accumulate matching section objects
    """
    for section in sections:
        category = section.get('category')
        level = section.get('level', 1)

        # Only match level 1 sections
        if level == 1 and category == target_category:
            matching_sections.append(section)
            # Note: When returning a top-level section, we include the entire section
            # with all its subsections, so the user gets complete context


def _collect_matching_subsections(
    sections: List,
    parent_category: str,
    target_category: str,
    matching_sections: List
) -> None:
    """
    Collect level 2 subsections that match the target category under a specific parent.
    This ensures we only retrieve subsections from the correct parent hierarchy.

    Args:
        sections: List of top-level section dicts from parsed_file
        parent_category: Parent category to search within
        target_category: Subcategory value to match at level 2
        matching_sections: List to accumulate matching section objects
    """
    for section in sections:
        parent_cat = section.get('category')
        level = section.get('level', 1)

        # Find the parent section first (level 1)
        if level == 1 and parent_cat == parent_category:
            # Now search for the target subcategory within this parent's subsections
            if 'sections' in section and section['sections']:
                parent_title = section.get('title', 'Untitled')
                for subsection in section['sections']:
                    sub_category = subsection.get('category')
                    if sub_category == target_category:
                        # Add parent title for breadcrumb display
                        subsection['_parent_title'] = parent_title
                        matching_sections.append(subsection)


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
