"""
Tools for the Parsing Agent.

This module contains tools that the parsing agent can use to:
- Parse PDF using Unstructured.io
- Extract sections and classify them
- Store parsed data in the database
"""

from typing import List, Dict
from langchain_core.tools import tool


@tool
def parse_pdf_with_unstructured(file_path: str) -> List[Dict]:
    """
    Parse a PDF file using Unstructured.io.

    Args:
        file_path: Path to the PDF file

    Returns:
        List of parsed page elements with text, metadata, and structure

    TODO: Implement Unstructured.io integration
    """
    pass


@tool
def classify_sections(parsed_pages: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Classify parsed content into CMO prospectus sections.

    Uses LLM to identify and categorize sections like:
    - Deal Summary, Tranche List, Payment Priority, etc.

    Args:
        parsed_pages: List of parsed page elements

    Returns:
        Dictionary mapping section types to their content

    TODO: Implement LLM-based section classification
    """
    pass


@tool
def build_section_hierarchy(sections: List[Dict]) -> List[Dict]:
    """
    Build hierarchical structure for sections and subsections.

    Args:
        sections: List of classified sections

    Returns:
        List of sections with parent-child relationships

    TODO: Implement hierarchy building logic
    """
    pass


@tool
def store_sections_in_db(prospectus_id: str, sections: List[Dict]) -> bool:
    """
    Store parsed sections in the database.

    Args:
        prospectus_id: UUID of the prospectus
        sections: List of sections to store

    Returns:
        True if successful, False otherwise

    TODO: Implement database storage logic using Django ORM
    """
    pass
