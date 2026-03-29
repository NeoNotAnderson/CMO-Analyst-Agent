"""
Answer Correctness Evaluator

Hybrid evaluator that measures if the answer matches a reference "ground truth" answer.
Uses both LLM-as-a-Judge (semantic similarity) and exact match (for factual queries).

Evaluation Target: Final Response
Evaluation Type: Hybrid (LLM-as-a-Judge + Unit Test)
"""

import os
import json
import re
from typing import Dict, Any, List, Optional, Set
from openai import OpenAI
from langsmith.schemas import Run, Example
from langsmith.evaluation import evaluator


CORRECTNESS_PROMPT = """You are evaluating whether an AI assistant's answer is correct by comparing it to a reference answer.

User Query: {query}

Reference Answer (Ground Truth):
{reference_answer}

Assistant Answer:
{actual_answer}

Compare the assistant's answer to the reference answer across these dimensions:

1. **Semantic Equivalence** (0-10): Do they convey the same information?
   - 10: Semantically identical, same meaning
   - 7-9: Very similar, minor phrasing differences
   - 4-6: Partially similar, some differences
   - 0-3: Different meanings

2. **Factual Consistency** (0-10): Are all facts consistent?
   - 10: All facts match perfectly
   - 7-9: Most facts match, minor discrepancies
   - 4-6: Some facts match, some don't
   - 0-3: Facts contradict reference

3. **Completeness** (0-10): Does assistant answer cover all key points from reference?
   - 10: All key points covered
   - 7-9: Most key points covered
   - 4-6: Some key points covered
   - 0-3: Few or no key points covered

Calculate overall score as the average of all three dimensions.

You must respond with a valid JSON object in this exact format:
{{
  "semantic_equivalence": 9,
  "factual_consistency": 10,
  "completeness": 8,
  "overall_score": 9.0,
  "key_points_matched": ["point 1", "point 2"],
  "key_points_missing": ["missing point"],
  "factual_errors": ["any contradictions"],
  "reasoning": "Detailed explanation of the score"
}}"""


def extract_final_answer(run: Run) -> str:
    """Extract the final answer from the run outputs."""
    if not run.outputs:
        return ""

    if isinstance(run.outputs, dict):
        for key in ['output', 'answer', 'response', 'messages']:
            if key in run.outputs:
                output = run.outputs[key]
                if isinstance(output, str):
                    return output
                elif isinstance(output, list):
                    if output and isinstance(output[-1], dict):
                        return output[-1].get('content', '')
                elif isinstance(output, dict):
                    return output.get('content', str(output))

    return str(run.outputs)


def extract_entities(text: str) -> Set[str]:
    """Extract key entities (numbers, names, terms) from text."""
    entities = set()

    # Extract numbers (including decimals and percentages)
    numbers = re.findall(r'\b\d+\.?\d*%?\b', text)
    entities.update(numbers)

    # Extract capitalized terms (likely proper nouns or class names)
    capitalized = re.findall(r'\b[A-Z][A-Za-z0-9\-]*\b', text)
    entities.update(capitalized)

    # Extract quoted terms
    quoted = re.findall(r'"([^"]+)"', text)
    entities.update(quoted)

    return entities


def calculate_exact_match_score(reference: str, actual: str) -> Dict[str, Any]:
    """
    Calculate exact match score using entity extraction.

    Args:
        reference: Reference answer
        actual: Actual answer

    Returns:
        Dict with score and details
    """
    ref_entities = extract_entities(reference)
    actual_entities = extract_entities(actual)

    if not ref_entities:
        return {
            'score': 1.0 if reference.lower().strip() in actual.lower() else 0.0,
            'matched_entities': [],
            'missing_entities': [],
            'extra_entities': []
        }

    matched = ref_entities & actual_entities
    missing = ref_entities - actual_entities
    extra = actual_entities - ref_entities

    # Calculate F1 score
    precision = len(matched) / len(actual_entities) if actual_entities else 0
    recall = len(matched) / len(ref_entities) if ref_entities else 0

    if precision + recall > 0:
        f1_score = 2 * (precision * recall) / (precision + recall)
    else:
        f1_score = 0.0

    return {
        'score': f1_score,
        'matched_entities': list(matched),
        'missing_entities': list(missing),
        'extra_entities': list(extra),
        'precision': precision,
        'recall': recall
    }


def evaluate_correctness_with_llm(
    query: str,
    reference_answer: str,
    actual_answer: str,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Use GPT-4 to evaluate answer correctness.

    Args:
        query: User's query
        reference_answer: Reference/ground truth answer
        actual_answer: Agent's actual answer
        model: OpenAI model to use

    Returns:
        Evaluation result with score and reasoning
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    prompt = CORRECTNESS_PROMPT.format(
        query=query,
        reference_answer=reference_answer,
        actual_answer=actual_answer
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert evaluator that assesses answer correctness. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # Normalize overall score to 0-1 range
        overall_score = result.get('overall_score', 0) / 10.0

        return {
            'score': overall_score,
            'semantic_equivalence': result.get('semantic_equivalence', 0),
            'factual_consistency': result.get('factual_consistency', 0),
            'completeness': result.get('completeness', 0),
            'key_points_matched': result.get('key_points_matched', []),
            'key_points_missing': result.get('key_points_missing', []),
            'factual_errors': result.get('factual_errors', []),
            'reasoning': result.get('reasoning', ''),
            'raw_overall_score': result.get('overall_score', 0)
        }

    except Exception as e:
        return {
            'score': 0.0,
            'semantic_equivalence': 0,
            'factual_consistency': 0,
            'completeness': 0,
            'key_points_matched': [],
            'key_points_missing': [],
            'factual_errors': [],
            'reasoning': f'Error during evaluation: {str(e)}',
            'raw_overall_score': 0,
            'error': str(e)
        }


def evaluate_correctness_hybrid(
    query: str,
    reference_answer: str,
    actual_answer: str,
    use_exact_match: bool = True,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Hybrid evaluation combining exact match and LLM-as-a-Judge.

    Args:
        query: User's query
        reference_answer: Reference answer
        actual_answer: Agent's answer
        use_exact_match: Whether to include exact match scoring
        model: OpenAI model to use

    Returns:
        Combined evaluation result
    """
    # LLM-based evaluation
    llm_result = evaluate_correctness_with_llm(query, reference_answer, actual_answer, model)

    if not use_exact_match:
        return llm_result

    # Exact match evaluation
    exact_result = calculate_exact_match_score(reference_answer, actual_answer)

    # Combine scores (weighted average: 70% LLM, 30% exact match)
    combined_score = 0.7 * llm_result['score'] + 0.3 * exact_result['score']

    return {
        'score': combined_score,
        'llm_score': llm_result['score'],
        'exact_match_score': exact_result['score'],
        'semantic_equivalence': llm_result['semantic_equivalence'],
        'factual_consistency': llm_result['factual_consistency'],
        'completeness': llm_result['completeness'],
        'key_points_matched': llm_result['key_points_matched'],
        'key_points_missing': llm_result['key_points_missing'],
        'factual_errors': llm_result['factual_errors'],
        'matched_entities': exact_result['matched_entities'],
        'missing_entities': exact_result['missing_entities'],
        'reasoning': llm_result['reasoning'],
        'raw_overall_score': llm_result.get('raw_overall_score', 0)
    }


@evaluator
def answer_correctness_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    LangSmith evaluator for answer correctness.

    Compares the agent's answer to a reference answer using hybrid approach:
    - LLM-as-a-Judge for semantic similarity
    - Exact match for factual entity matching

    Args:
        run: The LangSmith run to evaluate
        example: The test example with inputs and expected outputs

    Returns:
        Evaluation result with score and detailed comparison
    """
    # Extract query
    query = example.inputs.get('query', '')
    if not query:
        return {
            'key': 'answer_correctness',
            'score': 0.0,
            'comment': 'No query found in example inputs'
        }

    # Extract reference answer
    reference_answer = None
    if example.outputs:
        reference_answer = example.outputs.get('reference_answer')
    if not reference_answer and example.metadata:
        reference_answer = example.metadata.get('reference_answer')

    if not reference_answer:
        return {
            'key': 'answer_correctness',
            'score': None,
            'comment': 'No reference answer provided - skipping correctness evaluation'
        }

    # Extract actual answer
    actual_answer = extract_final_answer(run)
    if not actual_answer:
        return {
            'key': 'answer_correctness',
            'score': 0.0,
            'comment': 'No answer found in run outputs'
        }

    # Evaluate with hybrid approach
    result = evaluate_correctness_hybrid(query, reference_answer, actual_answer)

    # Build comment
    comment = result['reasoning']
    if result.get('llm_score') is not None:
        comment += f" [LLM: {result['llm_score']:.2f}, Exact: {result['exact_match_score']:.2f}]"

    matched = len(result.get('key_points_matched', []))
    missing = len(result.get('key_points_missing', []))
    if matched or missing:
        comment += f" (Matched {matched} key points"
        if missing:
            comment += f", missing {missing}"
        comment += ")"

    return {
        'key': 'answer_correctness',
        'score': result['score'],
        'comment': comment,
        'metadata': {
            'llm_score': result.get('llm_score'),
            'exact_match_score': result.get('exact_match_score'),
            'semantic_equivalence': result.get('semantic_equivalence', 0),
            'factual_consistency': result.get('factual_consistency', 0),
            'completeness': result.get('completeness', 0),
            'key_points_matched': result.get('key_points_matched', []),
            'key_points_missing': result.get('key_points_missing', []),
            'factual_errors': result.get('factual_errors', []),
            'matched_entities': result.get('matched_entities', []),
            'missing_entities': result.get('missing_entities', []),
            'raw_overall_score': result.get('raw_overall_score', 0)
        }
    }


# Standalone function for testing
def evaluate_answer_correctness(
    query: str,
    reference_answer: str,
    actual_answer: str,
    use_exact_match: bool = True,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Standalone function to evaluate answer correctness.

    Args:
        query: User's query
        reference_answer: Reference answer
        actual_answer: Agent's answer
        use_exact_match: Whether to include exact match scoring
        model: OpenAI model to use

    Returns:
        Evaluation result
    """
    result = evaluate_correctness_hybrid(query, reference_answer, actual_answer, use_exact_match, model)

    comment = result['reasoning']
    if result.get('llm_score') is not None:
        comment += f" [LLM: {result['llm_score']:.2f}, Exact: {result['exact_match_score']:.2f}]"

    matched = len(result.get('key_points_matched', []))
    missing = len(result.get('key_points_missing', []))
    if matched or missing:
        comment += f" (Matched {matched} key points"
        if missing:
            comment += f", missing {missing}"
        comment += ")"

    return {
        'key': 'answer_correctness',
        'score': result['score'],
        'comment': comment,
        'metadata': {
            'llm_score': result.get('llm_score'),
            'exact_match_score': result.get('exact_match_score'),
            'semantic_equivalence': result.get('semantic_equivalence', 0),
            'factual_consistency': result.get('factual_consistency', 0),
            'completeness': result.get('completeness', 0),
            'key_points_matched': result.get('key_points_matched', []),
            'key_points_missing': result.get('key_points_missing', []),
            'factual_errors': result.get('factual_errors', []),
            'matched_entities': result.get('matched_entities', []),
            'missing_entities': result.get('missing_entities', []),
            'raw_overall_score': result.get('raw_overall_score', 0)
        }
    }


if __name__ == '__main__':
    # Example usage for testing
    print("Answer Correctness Evaluator - Test\n")
    print("=" * 70)

    query = "What tranches are in this deal?"
    reference = "The deal consists of Class A-1, A-2, A-3, A-4, A-S, B, C, D, E, F, and X-A certificates."

    # Test 1: Perfect match
    print("\nTest 1: Semantically equivalent answer")
    print("-" * 70)
    actual1 = "This deal has the following certificate classes: A-1, A-2, A-3, A-4, A-S, B, C, D, E, F, and X-A."

    result1 = evaluate_answer_correctness(query, reference, actual1)
    print(f"Overall Score: {result1['score']:.2f}")
    print(f"  LLM Score: {result1['metadata']['llm_score']:.2f}")
    print(f"  Exact Match Score: {result1['metadata']['exact_match_score']:.2f}")
    print(f"\nMatched entities: {result1['metadata']['matched_entities']}")
    print(f"Reasoning: {result1['metadata'].get('reasoning', result1['comment'])[:200]}...")

    # Test 2: Incomplete answer
    print("\n" + "=" * 70)
    print("\nTest 2: Incomplete answer (missing tranches)")
    print("-" * 70)
    actual2 = "The deal has Class A-1, A-2, and B certificates."

    result2 = evaluate_answer_correctness(query, reference, actual2)
    print(f"Overall Score: {result2['score']:.2f}")
    print(f"  LLM Score: {result2['metadata']['llm_score']:.2f}")
    print(f"  Exact Match Score: {result2['metadata']['exact_match_score']:.2f}")
    print(f"\nKey points matched: {result2['metadata']['key_points_matched']}")
    print(f"Key points missing: {result2['metadata']['key_points_missing']}")
    print(f"Missing entities: {result2['metadata']['missing_entities']}")

    # Test 3: Incorrect answer
    print("\n" + "=" * 70)
    print("\nTest 3: Incorrect answer with errors")
    print("-" * 70)
    actual3 = "The deal consists of Class M-1, M-2, Junior, and Senior tranches."

    result3 = evaluate_answer_correctness(query, reference, actual3)
    print(f"Overall Score: {result3['score']:.2f}")
    print(f"  LLM Score: {result3['metadata']['llm_score']:.2f}")
    print(f"  Exact Match Score: {result3['metadata']['exact_match_score']:.2f}")
    print(f"\nFactual errors: {result3['metadata']['factual_errors']}")

    print("\n" + "=" * 70)
