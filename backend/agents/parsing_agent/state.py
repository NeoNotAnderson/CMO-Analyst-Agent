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
        doc_type: Type of document (supplement or prospectus)
        parsed_index: Parsed index structure from index pages (JSON with hierarchy)
        current_section_idx: Index of section currently being parsed
        parsed_pages: List of all parsed page objects
        section_map: Dictionary mapping section types to their content
        sections: List of extracted sections with full hierarchy
        parsing_complete: Boolean flag indicating if parsing is complete
        current_step: Current parsing step
        errors: List of error messages if any
        metadata: Additional metadata collected during parsing
    """

    prospectus_id: str
    prospectus_file_path: str
    doc_type: str
    parsed_index: Optional[Dict]
    current_section_idx: int
    parsed_pages: List[Dict]
    section_map: Dict[str, List[Dict]]
    sections: List[Dict]
    parsing_complete: bool
    current_step: str
    errors: List[str]
    metadata: Dict
