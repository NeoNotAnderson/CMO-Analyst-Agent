"""
Document Relevance Evaluator

Unit test evaluator that checks if retrieved documents/sections are relevant to the query.
This is a fast, deterministic evaluator using keyword matching and semantic similarity.

Evaluation Target: Trajectory (tool outputs, specifically retrieve_sections)
Evaluation Type: Unit Test (deterministic, no LLM needed)
"""

from typing import Dict, Any, List, Optional
import re
from langsmith.schemas import Run, Example
from langsmith.evaluation import evaluator


def extract_retrieved_sections(run: Run) -> List[str]:
    """Extract section names from retrieve_sections tool outputs in the run."""
    sections = []

    if not run.outputs:
        return sections

    # Check if this is the main agent run with child runs
    if hasattr(run, 'child_runs') and run.child_runs:
        for child_run in run.child_runs:
            # Look for retrieve_sections tool calls
            if child_run.name == 'retrieve_sections':
                output = child_run.outputs
                if output and isinstance(output, dict):
                    # Extract section names from the output
                    output_str = str(output.get('output', ''))
                    # Pattern: Section names are typically in quotes or after "Section:" or "###"
                    section_patterns = [
                        r'Section:\s*([^\n]+)',
                        r'###\s*([^\n]+)',
                        r'"([^"]+)"',
                    ]
                    for pattern in section_patterns:
                        matches = re.findall(pattern, output_str)
                        sections.extend(matches)

    return sections


def extract_query_keywords(query: str) -> List[str]:
    """Extract important keywords from the query."""
    # Remove common stop words
    stop_words = {
        'what', 'is', 'are', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
        'of', 'and', 'or', 'but', 'this', 'that', 'these', 'those', 'how',
        'why', 'when', 'where', 'who', 'which', 'can', 'could', 'would', 'should'
    }

    # Tokenize and filter
    words = re.findall(r'\b\w+\b', query.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]

    return keywords


def calculate_keyword_overlap(query_keywords: List[str], section_text: str) -> float:
    """Calculate percentage of query keywords found in section text."""
    if not query_keywords:
        return 0.0

    section_lower = section_text.lower()
    matches = sum(1 for keyword in query_keywords if keyword in section_lower)

    return matches / len(query_keywords)


def check_section_relevance(query: str, sections: List[str], expected_sections: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Check if retrieved sections are relevant to the query.

    Args:
        query: The user's query
        sections: List of retrieved section names
        expected_sections: Optional list of expected section names from test case

    Returns:
        Dict with score, reasoning, and details
    """
    if not sections:
        return {
            'score': 0.0,
            'reasoning': 'No sections were retrieved',
            'details': {
                'retrieved_count': 0,
                'expected_count': len(expected_sections) if expected_sections else None,
                'overlap': [],
                'missing': expected_sections if expected_sections else []
            }
        }

    query_keywords = extract_query_keywords(query)

    # Calculate relevance score
    if expected_sections:
        # If we have expected sections, check overlap
        retrieved_set = set(s.lower().strip() for s in sections)
        expected_set = set(s.lower().strip() for s in expected_sections)

        overlap = retrieved_set & expected_set
        missing = expected_set - retrieved_set
        extra = retrieved_set - expected_set

        # Score based on precision and recall
        precision = len(overlap) / len(retrieved_set) if retrieved_set else 0
        recall = len(overlap) / len(expected_set) if expected_set else 0

        # F1 score
        if precision + recall > 0:
            score = 2 * (precision * recall) / (precision + recall)
        else:
            score = 0.0

        reasoning = f"Retrieved {len(sections)} sections. "
        if overlap:
            reasoning += f"Matched {len(overlap)}/{len(expected_sections)} expected sections. "
        if missing:
            reasoning += f"Missing: {', '.join(missing)}. "
        if extra:
            reasoning += f"Extra: {', '.join(extra)}. "

        return {
            'score': score,
            'reasoning': reasoning.strip(),
            'details': {
                'retrieved_count': len(sections),
                'expected_count': len(expected_sections),
                'overlap': list(overlap),
                'missing': list(missing),
                'extra': list(extra),
                'precision': precision,
                'recall': recall
            }
        }
    else:
        # No expected sections, use keyword matching
        relevance_scores = [calculate_keyword_overlap(query_keywords, section) for section in sections]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0

        # Score interpretation:
        # > 0.5: High relevance (most keywords present)
        # 0.2-0.5: Medium relevance (some keywords present)
        # < 0.2: Low relevance (few keywords present)

        score = min(avg_relevance * 2, 1.0)  # Scale to 0-1

        if score >= 0.7:
            relevance_label = "high"
        elif score >= 0.4:
            relevance_label = "medium"
        else:
            relevance_label = "low"

        reasoning = f"Retrieved {len(sections)} sections with {relevance_label} relevance "
        reasoning += f"(avg keyword overlap: {avg_relevance:.1%})"

        return {
            'score': score,
            'reasoning': reasoning,
            'details': {
                'retrieved_count': len(sections),
                'query_keywords': query_keywords,
                'avg_keyword_overlap': avg_relevance,
                'section_scores': dict(zip(sections, relevance_scores))
            }
        }


@evaluator
def document_relevance_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    LangSmith evaluator for document relevance.

    Checks if the sections retrieved during agent execution are relevant to the query.
    Uses expected_sections from metadata if available, otherwise uses keyword matching.

    Args:
        run: The LangSmith run to evaluate
        example: The test example with inputs and expected outputs

    Returns:
        Evaluation result with score, reasoning, and details
    """
    # Extract query
    query = example.inputs.get('query', '')
    if not query:
        return {
            'key': 'document_relevance',
            'score': 0.0,
            'comment': 'No query found in example inputs'
        }

    # Extract expected sections from metadata
    expected_sections = None
    if example.metadata:
        expected_sections = example.metadata.get('reference_sections')

    # Extract retrieved sections from run
    retrieved_sections = extract_retrieved_sections(run)

    # Check relevance
    result = check_section_relevance(query, retrieved_sections, expected_sections)

    return {
        'key': 'document_relevance',
        'score': result['score'],
        'comment': result['reasoning'],
        'metadata': result['details']
    }


# Standalone function for testing without LangSmith
def evaluate_document_relevance(
    query: str,
    retrieved_sections: List[str],
    expected_sections: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Standalone function to evaluate document relevance.

    Useful for testing and debugging without running through LangSmith.

    Args:
        query: The user's query
        retrieved_sections: List of section names that were retrieved
        expected_sections: Optional list of expected section names

    Returns:
        Evaluation result with score, reasoning, and details
    """
    result = check_section_relevance(query, retrieved_sections, expected_sections)
    return {
        'key': 'document_relevance',
        'score': result['score'],
        'comment': result['reasoning'],
        'metadata': result['details']
    }


if __name__ == '__main__':
    # Example usage for testing
    print("Document Relevance Evaluator - Test Cases\n")
    print("=" * 70)

    # Test case 1: Perfect match
    print("\nTest 1: Perfect match")
    result = evaluate_document_relevance(
        query="What tranches are in this deal?",
        retrieved_sections=["Description of the Certificates", "Certificate Table"],
        expected_sections=["Description of the Certificates", "Certificate Table"]
    )
    print(f"Score: {result['score']:.2f}")
    print(f"Comment: {result['comment']}")
    print(f"Details: {result['metadata']}")

    # Test case 2: Partial match
    print("\n" + "=" * 70)
    print("\nTest 2: Partial match (missing one section)")
    result = evaluate_document_relevance(
        query="What is the credit enhancement for Class A?",
        retrieved_sections=["Certificate Table"],
        expected_sections=["Credit Enhancement", "Certificate Table"]
    )
    print(f"Score: {result['score']:.2f}")
    print(f"Comment: {result['comment']}")
    print(f"Details: {result['metadata']}")

    # Test case 3: No sections retrieved
    print("\n" + "=" * 70)
    print("\nTest 3: No sections retrieved")
    result = evaluate_document_relevance(
        query="What is the lockout period?",
        retrieved_sections=[],
        expected_sections=["Prepayment Provisions", "Lockout Period"]
    )
    print(f"Score: {result['score']:.2f}")
    print(f"Comment: {result['comment']}")
    print(f"Details: {result['metadata']}")

    # Test case 4: No expected sections (keyword matching)
    print("\n" + "=" * 70)
    print("\nTest 4: Keyword-based relevance (no expected sections)")
    result = evaluate_document_relevance(
        query="What are the risk factors for this investment?",
        retrieved_sections=[
            "Risk Factors",
            "Credit Risk and Default",
            "Interest Rate and Market Risk"
        ],
        expected_sections=None
    )
    print(f"Score: {result['score']:.2f}")
    print(f"Comment: {result['comment']}")
    print(f"Details: {result['metadata']}")

    print("\n" + "=" * 70)
