"""
Trajectory Evaluation Workflow

Evaluates agent trajectories (tool call sequences) to ensure the agent follows
expected reasoning paths and doesn't make unnecessary tool calls.

Usage:
    # Programmatic
    from evaluation.workflows import evaluate_trajectory

    result = evaluate_trajectory(
        actual_trajectory=['classify_query', 'analyze_query_sections', 'retrieve_sections'],
        expected_trajectory='classify_query -> analyze_query_sections -> retrieve_sections'
    )

    # CLI
    python trajectory_evaluation.py --dataset cmo-analyst-golden-v1
"""

import re
import sys
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langsmith.schemas import Run, Example
from langsmith.evaluation import evaluator


def parse_expected_trajectory(expected: str) -> List[str]:
    """
    Parse expected trajectory string into list of tool names.

    Args:
        expected: String like "tool1 -> tool2 -> tool3"

    Returns:
        List of tool names
    """
    if not expected:
        return []

    # Split by arrow or comma
    tools = re.split(r'\s*(?:->|,)\s*', expected.strip())

    # Clean tool names
    tools = [t.strip() for t in tools if t.strip()]

    return tools


def extract_trajectory_from_run(run: Run) -> List[str]:
    """
    Extract tool call sequence from a LangSmith run.

    Args:
        run: The LangSmith run object

    Returns:
        List of tool names in execution order
    """
    trajectory = []

    if not hasattr(run, 'child_runs') or not run.child_runs:
        return trajectory

    # Collect all tool calls with their start times
    tool_calls = []
    for child_run in run.child_runs:
        if hasattr(child_run, 'name') and hasattr(child_run, 'start_time'):
            tool_calls.append({
                'name': child_run.name,
                'start_time': child_run.start_time
            })

    # Sort by start time
    tool_calls.sort(key=lambda x: x['start_time'])

    # Extract names
    trajectory = [tc['name'] for tc in tool_calls]

    return trajectory


def calculate_trajectory_similarity(
    actual: List[str],
    expected: List[str]
) -> Dict[str, Any]:
    """
    Calculate similarity between actual and expected trajectories.

    Args:
        actual: Actual tool call sequence
        expected: Expected tool call sequence

    Returns:
        Dict with similarity metrics
    """
    if not expected:
        # No expected trajectory, just check if actual is non-empty
        return {
            'score': 1.0 if actual else 0.0,
            'match': actual == expected,
            'reasoning': 'No expected trajectory specified',
            'actual_length': len(actual),
            'expected_length': 0
        }

    if not actual:
        return {
            'score': 0.0,
            'match': False,
            'reasoning': 'No tool calls made',
            'actual_length': 0,
            'expected_length': len(expected)
        }

    # Check for exact match
    if actual == expected:
        return {
            'score': 1.0,
            'match': True,
            'reasoning': 'Perfect trajectory match',
            'actual_length': len(actual),
            'expected_length': len(expected),
            'matched_tools': actual,
            'missing_tools': [],
            'extra_tools': [],
            'order_correct': True
        }

    # Calculate partial match
    actual_set = set(actual)
    expected_set = set(expected)

    matched = actual_set & expected_set
    missing = expected_set - actual_set
    extra = actual_set - expected_set

    # Check order of matched tools
    order_correct = True
    actual_matched_indices = [i for i, t in enumerate(actual) if t in expected_set]
    expected_matched_indices = [i for i, t in enumerate(expected) if t in actual_set]

    if len(actual_matched_indices) > 1:
        # Check if relative order is preserved
        for i in range(len(actual_matched_indices) - 1):
            actual_idx = actual_matched_indices[i]
            next_actual_idx = actual_matched_indices[i + 1]

            actual_tool = actual[actual_idx]
            next_actual_tool = actual[next_actual_idx]

            # Find positions in expected
            try:
                expected_pos = expected.index(actual_tool)
                next_expected_pos = expected.index(next_actual_tool)

                if expected_pos > next_expected_pos:
                    order_correct = False
                    break
            except ValueError:
                continue

    # Calculate score
    precision = len(matched) / len(actual_set) if actual_set else 0
    recall = len(matched) / len(expected_set) if expected_set else 0

    f1_score = 0
    if precision + recall > 0:
        f1_score = 2 * (precision * recall) / (precision + recall)

    # Adjust score based on order
    score = f1_score
    if not order_correct:
        score *= 0.8  # Penalize incorrect order

    # Penalize extra tools (inefficiency)
    if extra:
        extra_penalty = len(extra) * 0.1
        score = max(0, score - extra_penalty)

    # Build reasoning
    reasoning = f"Matched {len(matched)}/{len(expected_set)} expected tools. "
    if missing:
        reasoning += f"Missing: {', '.join(missing)}. "
    if extra:
        reasoning += f"Extra: {', '.join(extra)}. "
    if not order_correct:
        reasoning += "Order incorrect. "

    return {
        'score': score,
        'match': False,
        'reasoning': reasoning.strip(),
        'actual_length': len(actual),
        'expected_length': len(expected),
        'matched_tools': list(matched),
        'missing_tools': list(missing),
        'extra_tools': list(extra),
        'order_correct': order_correct,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score
    }


@evaluator
def trajectory_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    LangSmith evaluator for agent trajectory.

    Checks if the agent followed the expected tool call sequence.

    Args:
        run: The LangSmith run to evaluate
        example: The test example with expected trajectory in metadata

    Returns:
        Evaluation result with score and reasoning
    """
    # Extract expected trajectory from metadata
    expected_trajectory_str = None
    if hasattr(example, 'metadata') and example.metadata:
        expected_trajectory_str = example.metadata.get('expected_trajectory')

    if not expected_trajectory_str:
        return {
            'key': 'trajectory',
            'score': None,
            'comment': 'No expected trajectory specified - skipping evaluation'
        }

    expected_trajectory = parse_expected_trajectory(expected_trajectory_str)

    # Extract actual trajectory from run
    actual_trajectory = extract_trajectory_from_run(run)

    # Calculate similarity
    result = calculate_trajectory_similarity(actual_trajectory, expected_trajectory)

    # Build comment
    comment = result['reasoning']
    comment += f" (Actual: {' -> '.join(actual_trajectory) if actual_trajectory else 'none'})"

    return {
        'key': 'trajectory',
        'score': result['score'],
        'comment': comment,
        'metadata': {
            'actual_trajectory': actual_trajectory,
            'expected_trajectory': expected_trajectory,
            'matched_tools': result.get('matched_tools', []),
            'missing_tools': result.get('missing_tools', []),
            'extra_tools': result.get('extra_tools', []),
            'order_correct': result.get('order_correct', False),
            'precision': result.get('precision', 0),
            'recall': result.get('recall', 0)
        }
    }


# Standalone function
def evaluate_trajectory(
    actual_trajectory: List[str],
    expected_trajectory: str
) -> Dict[str, Any]:
    """
    Standalone function to evaluate trajectory.

    Args:
        actual_trajectory: List of tool names in execution order
        expected_trajectory: Expected trajectory string (e.g., "tool1 -> tool2")

    Returns:
        Evaluation result
    """
    expected = parse_expected_trajectory(expected_trajectory)
    result = calculate_trajectory_similarity(actual_trajectory, expected)

    comment = result['reasoning']
    comment += f" (Actual: {' -> '.join(actual_trajectory) if actual_trajectory else 'none'})"

    return {
        'key': 'trajectory',
        'score': result['score'],
        'comment': comment,
        'metadata': {
            'actual_trajectory': actual_trajectory,
            'expected_trajectory': expected,
            'matched_tools': result.get('matched_tools', []),
            'missing_tools': result.get('missing_tools', []),
            'extra_tools': result.get('extra_tools', []),
            'order_correct': result.get('order_correct', False)
        }
    }


def detect_inefficiencies(trajectory: List[str]) -> Dict[str, Any]:
    """
    Detect common inefficiencies in agent trajectories.

    Args:
        trajectory: List of tool names in execution order

    Returns:
        Dict with inefficiency analysis
    """
    issues = []

    # Check for repeated tool calls
    tool_counts = {}
    for tool in trajectory:
        tool_counts[tool] = tool_counts.get(tool, 0) + 1

    repeated_tools = {tool: count for tool, count in tool_counts.items() if count > 1}
    if repeated_tools:
        for tool, count in repeated_tools.items():
            issues.append(f"{tool} called {count} times (potential redundancy)")

    # Check for unnecessary sequence patterns
    if len(trajectory) >= 2:
        # Look for back-and-forth patterns
        for i in range(len(trajectory) - 1):
            if i + 2 < len(trajectory):
                if trajectory[i] == trajectory[i + 2]:
                    issues.append(f"Back-and-forth pattern: {trajectory[i]} -> {trajectory[i+1]} -> {trajectory[i]}")
                    break

    # Check trajectory length
    if len(trajectory) > 10:
        issues.append(f"Long trajectory ({len(trajectory)} tools) - may indicate inefficiency")

    return {
        'has_issues': len(issues) > 0,
        'issues': issues,
        'repeated_tools': repeated_tools,
        'total_tools': len(trajectory),
        'unique_tools': len(set(trajectory))
    }


if __name__ == '__main__':
    # Example usage for testing
    print("Trajectory Evaluation - Test Cases\n")
    print("=" * 70)

    # Test 1: Perfect match
    print("\nTest 1: Perfect trajectory match")
    print("-" * 70)
    result1 = evaluate_trajectory(
        actual_trajectory=['classify_query', 'analyze_query_sections', 'retrieve_sections'],
        expected_trajectory='classify_query -> analyze_query_sections -> retrieve_sections'
    )
    print(f"Score: {result1['score']:.2f}")
    print(f"Comment: {result1['comment']}")

    # Test 2: Missing tool
    print("\n" + "=" * 70)
    print("\nTest 2: Missing tool (skipped analyze_query_sections)")
    print("-" * 70)
    result2 = evaluate_trajectory(
        actual_trajectory=['classify_query', 'retrieve_sections'],
        expected_trajectory='classify_query -> analyze_query_sections -> retrieve_sections'
    )
    print(f"Score: {result2['score']:.2f}")
    print(f"Comment: {result2['comment']}")
    print(f"Missing: {result2['metadata']['missing_tools']}")

    # Test 3: Extra tools
    print("\n" + "=" * 70)
    print("\nTest 3: Extra unnecessary tool calls")
    print("-" * 70)
    result3 = evaluate_trajectory(
        actual_trajectory=['classify_query', 'analyze_query_sections', 'some_other_tool', 'retrieve_sections', 'classify_query'],
        expected_trajectory='classify_query -> analyze_query_sections -> retrieve_sections'
    )
    print(f"Score: {result3['score']:.2f}")
    print(f"Comment: {result3['comment']}")
    print(f"Extra: {result3['metadata']['extra_tools']}")

    # Test 4: Wrong order
    print("\n" + "=" * 70)
    print("\nTest 4: Wrong order")
    print("-" * 70)
    result4 = evaluate_trajectory(
        actual_trajectory=['retrieve_sections', 'analyze_query_sections', 'classify_query'],
        expected_trajectory='classify_query -> analyze_query_sections -> retrieve_sections'
    )
    print(f"Score: {result4['score']:.2f}")
    print(f"Comment: {result4['comment']}")
    print(f"Order correct: {result4['metadata']['order_correct']}")

    # Test 5: Detect inefficiencies
    print("\n" + "=" * 70)
    print("\nTest 5: Detect inefficiencies")
    print("-" * 70)
    trajectory = ['classify_query', 'retrieve_sections', 'classify_query', 'analyze_query_sections', 'retrieve_sections']
    inefficiencies = detect_inefficiencies(trajectory)
    print(f"Trajectory: {' -> '.join(trajectory)}")
    print(f"Has issues: {inefficiencies['has_issues']}")
    print(f"Issues:")
    for issue in inefficiencies['issues']:
        print(f"  - {issue}")
    print(f"Repeated tools: {inefficiencies['repeated_tools']}")

    print("\n" + "=" * 70)
