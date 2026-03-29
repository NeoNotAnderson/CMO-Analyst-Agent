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

# LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    # Fallback if langsmith not installed
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    LANGSMITH_AVAILABLE = False

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
    title: str = Field(description="Exact section title from the prospectus")
    parent_title: Optional[str] = Field(description="Parent section title, or null if top-level")


class SectionAnalysis(BaseModel):
    """Schema for section analysis result."""
    sections: List[SectionReference] = Field(description="List of up to 3 most relevant sections")
    reasoning: str = Field(description="Brief explanation for the section selection")


# ============================================================================
# TOOLS: BASIC QUERY AGENT
# ============================================================================

@tool
@traceable(name="classify_query", tags=["tool", "classification"])
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
@traceable(name="get_prospectus_status", tags=["tool", "prospectus"])
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
@traceable(name="trigger_parsing_agent", tags=["tool", "parsing"])
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
@traceable(name="analyze_query_sections", tags=["tool", "section_analysis"])
def analyze_query_sections(user_query: str, prospectus_id: str) -> str:
    """
    Analyze which prospectus sections are relevant to the query.

    Uses the actual section structure from parsed_file (titles and sample text)
    instead of fixed taxonomy categories.

    Args:
        user_query: The user's question
        prospectus_id: Prospectus UUID

    Returns:
        str: JSON with relevant sections including hierarchy information

    Example output:
        {
            "sections": [
                {"title": "SUMMARY", "parent_title": null},
                {"title": "Priority of Distributions", "parent_title": "SUMMARY"}
            ],
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
                "sections": []
            })

        # Build hierarchy structure description for LLM
        sections_structure = get_section_hierarchy_structure(parsed_file['sections'])

        if not sections_structure.strip():
            return json.dumps({
                "error": "No sections found in this prospectus.",
                "sections": []
            })

        # Use LLM to identify relevant sections
        structured_llm = llm.with_structured_output(SectionAnalysis)
        prompt = SECTION_ANALYSIS_PROMPT.format(
            query=user_query,
            available_sections=sections_structure
        )
        result = structured_llm.invoke(prompt)

        # Validate and build section list
        validated_sections = []
        top_level_titles_selected = set()

        # First pass: collect top-level section titles
        for section_ref in result.sections:
            if not section_ref.parent_title:
                top_level_titles_selected.add(section_ref.title)

        # Second pass: validate and filter
        for section_ref in result.sections:
            # Skip subsections if their parent was already selected
            if section_ref.parent_title and section_ref.parent_title in top_level_titles_selected:
                continue

            validated_sections.append({
                "title": section_ref.title,
                "parent_title": section_ref.parent_title
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
@traceable(name="retrieve_sections", tags=["tool", "retrieval"])
def retrieve_sections(prospectus_id: str, sections_data: str) -> str:
    """
    Retrieve section content from parsed_file based on section titles with hierarchy.

    This tool uses the actual section titles from the prospectus (not fixed taxonomy categories)
    to locate and retrieve the complete text content.

    IMPORTANT FOR THE AGENT:
    - This tool retrieves the actual prospectus text content needed to answer the user's question
    - After calling this tool, you will receive the section content in the tool response
    - Use that content to formulate a detailed, accurate answer to the user's question
    - The content includes section titles, page numbers, and the FULL text from those sections

    Args:
        prospectus_id: Prospectus UUID
        sections_data: JSON string from analyze_query_sections output
                      Format: {
                          "sections": [
                              {"title": "SUMMARY", "parent_title": null},
                              {"title": "Priority of Distributions", "parent_title": "SUMMARY"}
                          ],
                          "reasoning": "..."
                      }

    Returns:
        str: Retrieved section content formatted with hierarchy breadcrumbs and full text,
             OR an error message if sections not found

    Example output:
        Retrieved 2 section(s) from the prospectus.
        Use the following COMPLETE content to answer the user's question:

        ================================================================================
        SECTION 1: [SUMMARY] (Page 5)
        ================================================================================

        [Full section text...]

        ================================================================================
        SECTION 2: [SUMMARY > Priority of Distributions] (Page 12)
        ================================================================================

        [Full subsection text...]

        --- TABLE ---
        Summary: Distribution priority waterfall

        Table Data:
          Row 1: Priority: 1 | Description: Trustee fees | Amount: $5,000
          Row 2: Priority: 2 | Description: Servicing fees | Amount: 0.25%
        --- END TABLE ---
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

        # Collect matching sections using title-based hierarchy matching
        matching_sections = []
        for section_ref in section_refs:
            title = section_ref['title']
            parent_title = section_ref.get('parent_title')

            if parent_title:
                # This is a level 2 subsection - find it under the specific parent
                _collect_matching_subsections_by_title(
                    parsed_file['sections'],
                    parent_title=parent_title,
                    target_title=title,
                    matching_sections=matching_sections
                )
            else:
                # This is a level 1 top-level section - find it at top level
                _collect_matching_top_level_by_title(
                    parsed_file['sections'],
                    target_title=title,
                    matching_sections=matching_sections
                )

        if not matching_sections:
            requested = [f"{s.get('parent_title', 'TOP')} > {s['title']}" for s in section_refs]
            return f"No sections found matching the requested titles: {', '.join(requested)}"

        # Format sections with FULL content (proper RAG - no truncation)
        # Since analyze_query_sections returns max 3 sections, context size is manageable
        result = [f"Retrieved {len(matching_sections)} section(s) from the prospectus."]
        result.append("Use the following COMPLETE content to answer the user's question:\n")

        for idx, section in enumerate(matching_sections, 1):
            title = section.get('title', 'Untitled')
            level = section.get('level', 1)
            page_num = section.get('page_num', 'Unknown')
            text = section.get('text', '[No content]')
            table = section.get('table')
            parent_title = section.get('_parent_title', None)  # Added by collection function

            # Build hierarchy breadcrumb
            if parent_title:
                hierarchy_path = f"{parent_title} > {title}"
            else:
                hierarchy_path = title

            # Build section content
            section_content = [f"""
{'='*80}
SECTION {idx}: [{hierarchy_path}] (Page {page_num})
{'='*80}

{text}
"""]

            # Add table if it exists and is not empty
            if table and isinstance(table, dict):
                table_summary = table.get('summary', '')
                table_data = table.get('data', [])

                if table_data:
                    section_content.append("\n--- TABLE ---")
                    if table_summary:
                        section_content.append(f"Summary: {table_summary}")

                    # Format table data
                    section_content.append("\nTable Data:")
                    for row_idx, row in enumerate(table_data, 1):
                        if isinstance(row, dict):
                            row_str = " | ".join(f"{k}: {v}" for k, v in row.items())
                            section_content.append(f"  Row {row_idx}: {row_str}")
                    section_content.append("--- END TABLE ---\n")

            result.append("".join(section_content))

        return "\n".join(result)

    except Prospectus.DoesNotExist:
        return f"Error: Prospectus with ID {prospectus_id} not found."
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON format in categories. {str(e)}"
    except Exception as e:
        return f"Error retrieving sections: {str(e)}"


def get_section_hierarchy_structure(sections: List[Dict]) -> str:
    """
    Build a hierarchical structure representation of parsed_file sections for LLM prompt.

    This function creates a formatted string showing the actual section structure from
    the prospectus, including titles and sample text. Used in SECTION_ANALYSIS_PROMPT
    to help the LLM identify which sections are most relevant to a user's query.

    The output format uses actual section titles and content samples (not fixed categories),
    making it flexible for any prospectus structure.

    Args:
        sections: List of top-level section dicts from parsed_file
                 Each section should have: title, sample_text, and optionally subsections

    Returns:
        Formatted string representation of the hierarchy

    Example output:
        1. title: "SUMMARY"
           sample_text: This prospectus relates to the issuance of certificates...
           subsections:
             1.1 title: "The Certificates"
                sample_text: The following certificates are being offered...
             1.2 title: "Priority of Distributions"
                sample_text: On each distribution date, available funds...

        2. title: "RISK FACTORS"
           sample_text: Investment in the certificates involves risks...
           subsections:
             2.1 title: "Prepayment Risk"
                sample_text: The rate of prepayment on the mortgage loans...
    """
    result = []

    for idx, section in enumerate(sections, 1):
        title = section.get('title', 'Untitled')
        sample_text = section.get('sample_text', '')
        subsections = section.get('sections', [])

        # Format top-level section
        result.append(f'{idx}. title: "{title}"')
        if sample_text:
            clean_sample = sample_text.replace('\n', ' ').strip()
            if len(clean_sample) > 150:
                clean_sample = clean_sample[:150] + "..."
            result.append(f'   sample_text: {clean_sample}')

        # Format subsections
        if subsections:
            result.append('   subsections:')
            for sub_idx, subsection in enumerate(subsections, 1):
                sub_title = subsection.get('title', 'Untitled')
                sub_sample = subsection.get('sample_text', '')

                result.append(f'     {idx}.{sub_idx} title: "{sub_title}"')
                if sub_sample:
                    clean_sub_sample = sub_sample.replace('\n', ' ').strip()
                    if len(clean_sub_sample) > 120:
                        clean_sub_sample = clean_sub_sample[:120] + "..."
                    result.append(f'        sample_text: {clean_sub_sample}')

        result.append('')  # Empty line between sections

    return '\n'.join(result)


def _collect_matching_top_level_by_title(
    sections: List,
    target_title: str,
    matching_sections: List
) -> None:
    """
    Collect top-level sections (level 1) that match the target title.

    This function searches for sections by their actual title (not category).
    When a top-level section is matched, the entire section including all its
    subsections is added to matching_sections, providing complete context.

    Args:
        sections: List of top-level section dicts from parsed_file
        target_title: Exact section title to match at level 1 (case-sensitive)
        matching_sections: List to accumulate matching section objects (modified in place)

    Returns:
        None (modifies matching_sections in place)
    """
    for section in sections:
        title = section.get('title', '')
        level = section.get('level', 1)

        # Only match level 1 sections by title
        if level == 1 and title == target_title:
            matching_sections.append(section)


def _collect_matching_subsections_by_title(
    sections: List,
    parent_title: str,
    target_title: str,
    matching_sections: List
) -> None:
    """
    Collect level 2 subsections that match the target title under a specific parent.

    This function ensures hierarchy-aware retrieval: if multiple sections across different
    parents have the same subsection title, only the one under the specified parent is returned.
    This prevents ambiguity and ensures accurate section retrieval.

    The matched subsection gets a '_parent_title' field added for breadcrumb display.

    Args:
        sections: List of top-level section dicts from parsed_file
        parent_title: Exact parent section title to search within (level 1)
        target_title: Exact subsection title to match (level 2)
        matching_sections: List to accumulate matching section objects (modified in place)

    Returns:
        None (modifies matching_sections in place)

    Example:
        If parent_title="SUMMARY" and target_title="Priority of Distributions",
        this will find the "Priority of Distributions" subsection ONLY under "SUMMARY",
        even if another section also has a subsection with the same name.
    """
    for section in sections:
        section_title = section.get('title', '')
        level = section.get('level', 1)

        # Find the parent section first (level 1)
        if level == 1 and section_title == parent_title:
            # Now search for the target subsection within this parent's subsections
            if 'sections' in section and section['sections']:
                for subsection in section['sections']:
                    sub_title = subsection.get('title', '')
                    if sub_title == target_title:
                        # Add parent title for breadcrumb display
                        subsection['_parent_title'] = section_title
                        matching_sections.append(subsection)


# ============================================================================
# TOOLS: NEW HYBRID SEARCH RETRIEVAL
# ============================================================================

@tool
@traceable(name="retrieve_relevant_chunks", tags=["tool", "hybrid_search"])
def retrieve_relevant_chunks(user_query: str, prospectus_id: str) -> str:
    """
    Retrieve relevant chunks from prospectus using hybrid search (semantic + keyword + reranking).

    This tool replaces the old ToC-based section selection and automatically handles
    both specific questions (e.g., "What is the coupon rate of Tranche A-1?") and
    general questions (e.g., "What are the main risk factors?").

    The hybrid search combines:
    - Semantic search (vector similarity) for conceptual understanding
    - Keyword search (BM25) for exact term matching
    - Reciprocal Rank Fusion to merge results
    - Cross-encoder reranking for final relevance scoring

    Args:
        user_query: The user's question about the prospectus
        prospectus_id: Prospectus UUID

    Returns:
        str: Formatted chunks with metadata and citations

    Example:
        Query: "What is the coupon rate of Tranche A-1?"
        Returns: Relevant chunks containing the answer with page numbers and section citations
    """
    from core.models import Prospectus
    from .retrieval import hybrid_search, format_retrieved_chunks

    try:
        # Check if prospectus exists
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)

        # Check if chunks exist
        if not prospectus.chunks.exists():
            return (
                "This prospectus has not been indexed for hybrid search yet. "
                "The chunking process may still be running. Please try again in a moment, "
                "or use the older section-based retrieval as a fallback."
            )

        print(f"[TOOL] Running hybrid search for query: {user_query}")

        # Run hybrid search with balanced defaults
        # The hybrid search + reranking automatically adapts to query type
        chunks = hybrid_search(
            query=user_query,
            prospectus_id=prospectus_id,
            top_k=15,              # Good default for most queries
            retrieval_k=40,        # Retrieve more candidates for reranking
            metadata_filters=None, # No filtering - let search handle it
            search_strategy='hybrid',  # Balanced semantic + keyword
            use_reranking=True     # Cross-encoder for final scoring
        )

        # Format results for LLM consumption
        formatted_output = format_retrieved_chunks(chunks, include_metadata=True)

        print(f"[TOOL] Retrieved {len(chunks)} chunks")
        return formatted_output

    except Prospectus.DoesNotExist:
        return f"Error: Prospectus with ID {prospectus_id} not found."
    except Exception as e:
        return f"Error during retrieval: {str(e)}"


# ============================================================================
# TOOL LISTS
# ============================================================================

# New hybrid search tools (primary)
NEW_TOOLS = [
    retrieve_relevant_chunks,
]

# Legacy ToC-based tools (kept for backward compatibility)
LEGACY_TOOLS = [
    analyze_query_sections,
    retrieve_sections,
]

# Core tools (always available)
CORE_TOOLS = [
    classify_query,
    get_prospectus_status,
    trigger_parsing_agent,
]

# Default tool set: Use NEW hybrid search tool + core tools
# This is the simplified, production-ready configuration
ALL_TOOLS = CORE_TOOLS + NEW_TOOLS

# Alternative: Use legacy ToC-based tools (for backward compatibility if needed)
# ALL_TOOLS = CORE_TOOLS + LEGACY_TOOLS

# Alternative: Use both (for A/B testing or gradual migration)
# ALL_TOOLS = CORE_TOOLS + NEW_TOOLS + LEGACY_TOOLS
