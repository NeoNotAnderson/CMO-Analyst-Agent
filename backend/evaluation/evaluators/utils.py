"""
Shared utility functions for evaluators.

This module provides common helper functions used across multiple evaluators.
"""

from typing import Dict, Any, List, Optional
from langsmith.schemas import Run


def extract_final_answer(run: Run) -> str:
    """
    Extract the final answer from a LangSmith run.

    Args:
        run: The LangSmith run object

    Returns:
        The final answer as a string
    """
    if not run.outputs:
        return ""

    if isinstance(run.outputs, dict):
        # Try common output keys
        for key in ['output', 'answer', 'response', 'messages']:
            if key in run.outputs:
                output = run.outputs[key]

                # Handle string output
                if isinstance(output, str):
                    return output

                # Handle list output (LangGraph messages format)
                elif isinstance(output, list):
                    if output and isinstance(output[-1], dict):
                        return output[-1].get('content', '')

                # Handle dict output
                elif isinstance(output, dict):
                    return output.get('content', str(output))

    # Fallback: convert entire output to string
    return str(run.outputs)


def extract_retrieved_sections(run: Run) -> List[str]:
    """
    Extract section names from retrieve_sections tool outputs.

    Args:
        run: The LangSmith run object

    Returns:
        List of section names that were retrieved
    """
    sections = []

    if not run.outputs:
        return sections

    # Check if this run has child runs (tool calls)
    if hasattr(run, 'child_runs') and run.child_runs:
        for child_run in run.child_runs:
            # Look for retrieve_sections tool calls
            if child_run.name == 'retrieve_sections':
                output = child_run.outputs
                if output and isinstance(output, dict):
                    content = output.get('output', '')
                    if content:
                        sections.append(str(content))

    return sections


def extract_retrieved_content(run: Run) -> str:
    """
    Extract full content from retrieve_sections tool outputs.

    Args:
        run: The LangSmith run object

    Returns:
        Combined content from all retrieved sections
    """
    sections = extract_retrieved_sections(run)
    return "\n\n---\n\n".join(sections) if sections else "No sections retrieved"


def extract_tool_calls(run: Run) -> List[Dict[str, Any]]:
    """
    Extract all tool calls from a run.

    Args:
        run: The LangSmith run object

    Returns:
        List of tool call information (name, inputs, outputs)
    """
    tool_calls = []

    if not hasattr(run, 'child_runs') or not run.child_runs:
        return tool_calls

    for child_run in run.child_runs:
        tool_call = {
            'name': child_run.name,
            'inputs': child_run.inputs if hasattr(child_run, 'inputs') else {},
            'outputs': child_run.outputs if hasattr(child_run, 'outputs') else {},
            'start_time': child_run.start_time if hasattr(child_run, 'start_time') else None,
            'end_time': child_run.end_time if hasattr(child_run, 'end_time') else None,
        }
        tool_calls.append(tool_call)

    return tool_calls


def extract_trajectory(run: Run) -> List[str]:
    """
    Extract the agent's trajectory (sequence of tool calls).

    Args:
        run: The LangSmith run object

    Returns:
        List of tool names in execution order
    """
    tool_calls = extract_tool_calls(run)

    # Sort by start_time if available
    if tool_calls and tool_calls[0].get('start_time'):
        tool_calls.sort(key=lambda x: x.get('start_time'))

    return [tool['name'] for tool in tool_calls]


def get_reference_answer(example) -> Optional[str]:
    """
    Get reference answer from example outputs or metadata.

    Args:
        example: The LangSmith example object

    Returns:
        Reference answer if available, None otherwise
    """
    # Try outputs first
    if hasattr(example, 'outputs') and example.outputs:
        if isinstance(example.outputs, dict):
            ref = example.outputs.get('reference_answer')
            if ref:
                return ref

    # Try metadata
    if hasattr(example, 'metadata') and example.metadata:
        if isinstance(example.metadata, dict):
            ref = example.metadata.get('reference_answer')
            if ref:
                return ref

    return None


def get_expected_sections(example) -> Optional[List[str]]:
    """
    Get expected sections from example metadata.

    Args:
        example: The LangSmith example object

    Returns:
        List of expected section names if available, None otherwise
    """
    if hasattr(example, 'metadata') and example.metadata:
        if isinstance(example.metadata, dict):
            return example.metadata.get('reference_sections')

    return None


def get_expected_trajectory(example) -> Optional[str]:
    """
    Get expected trajectory from example metadata.

    Args:
        example: The LangSmith example object

    Returns:
        Expected trajectory string if available, None otherwise
    """
    if hasattr(example, 'metadata') and example.metadata:
        if isinstance(example.metadata, dict):
            return example.metadata.get('expected_trajectory')

    return None


def normalize_score(score: float, min_val: float = 0.0, max_val: float = 10.0) -> float:
    """
    Normalize a score to 0-1 range.

    Args:
        score: The score to normalize
        min_val: Minimum value of the input range
        max_val: Maximum value of the input range

    Returns:
        Normalized score between 0 and 1
    """
    if max_val == min_val:
        return 1.0 if score >= max_val else 0.0

    normalized = (score - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))  # Clamp to [0, 1]


def calculate_f1_score(precision: float, recall: float) -> float:
    """
    Calculate F1 score from precision and recall.

    Args:
        precision: Precision value (0-1)
        recall: Recall value (0-1)

    Returns:
        F1 score (0-1)
    """
    if precision + recall == 0:
        return 0.0

    return 2 * (precision * recall) / (precision + recall)


def format_score_comment(
    reasoning: str,
    score_breakdown: Optional[Dict[str, float]] = None,
    additional_info: Optional[str] = None
) -> str:
    """
    Format a comment string with score breakdown.

    Args:
        reasoning: Main reasoning text
        score_breakdown: Dict of score components (e.g., {"precision": 0.8, "recall": 0.9})
        additional_info: Additional context to append

    Returns:
        Formatted comment string
    """
    comment = reasoning

    if score_breakdown:
        breakdown_str = ", ".join(
            f"{key}: {value:.2f}" for key, value in score_breakdown.items()
        )
        comment += f" [{breakdown_str}]"

    if additional_info:
        comment += f" {additional_info}"

    return comment


if __name__ == '__main__':
    # Test utility functions
    print("Evaluator Utilities - Test\n")
    print("=" * 70)

    # Test normalize_score
    print("\nTest normalize_score:")
    print(f"  normalize_score(5, 0, 10) = {normalize_score(5, 0, 10)}")
    print(f"  normalize_score(8, 0, 10) = {normalize_score(8, 0, 10)}")
    print(f"  normalize_score(10, 0, 10) = {normalize_score(10, 0, 10)}")

    # Test calculate_f1_score
    print("\nTest calculate_f1_score:")
    print(f"  F1(precision=0.8, recall=0.9) = {calculate_f1_score(0.8, 0.9):.3f}")
    print(f"  F1(precision=1.0, recall=1.0) = {calculate_f1_score(1.0, 1.0):.3f}")
    print(f"  F1(precision=0.5, recall=0.5) = {calculate_f1_score(0.5, 0.5):.3f}")

    # Test format_score_comment
    print("\nTest format_score_comment:")
    comment = format_score_comment(
        reasoning="The answer is mostly correct",
        score_breakdown={"precision": 0.85, "recall": 0.90},
        additional_info="(Missing 1 key point)"
    )
    print(f"  {comment}")

    print("\n" + "=" * 70)
