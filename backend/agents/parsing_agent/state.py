"""
State definitions for the Parsing Agent.

This module defines the state schema that flows through the LangGraph nodes.
"""

from typing import TypedDict, List, Dict, Optional


class ParsingState(TypedDict):
    """
    State for the parsing agent workflow.

    Attributes:
        prospectus_id: UUID of the prospectus being parsed
        prospectus_file_path: Path to the uploaded prospectus PDF
        parsed_pages: List of parsed page objects from Unstructured.io
        section_map: Dictionary mapping section types to their content
        sections: List of extracted sections with hierarchy
        current_step: Current parsing step
        errors: List of error messages if any
        metadata: Additional metadata collected during parsing
    """

    prospectus_id: str
    prospectus_file_path: str
    parsed_pages: List[Dict]
    section_map: Dict[str, List[Dict]]
    sections: List[Dict]
    current_step: str
    errors: List[str]
    metadata: Dict
