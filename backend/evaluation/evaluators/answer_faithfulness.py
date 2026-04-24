"""
Answer Faithfulness Evaluator

LLM-as-a-Judge evaluator that checks if the agent's answer is grounded in retrieved documents.
Detects hallucinations by verifying all claims are supported by source documents.
Supports both hybrid search (retrieve_relevant_chunks) and legacy section retrieval (retrieve_sections).

Evaluation Target: Final Response
Evaluation Type: LLM-as-a-Judge (GPT-4)
"""

import os
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from langsmith.schemas import Run, Example
from langsmith.evaluation import evaluator


FAITHFULNESS_PROMPT = """You are evaluating whether an AI assistant's answer is grounded in source documents.

User Query: {query}

Source Documents:
{retrieved_sections}

Assistant Answer:
{answer}

Evaluate the answer for faithfulness by following these steps:

1. Identify all factual claims in the answer
2. For each claim, determine if it's supported by the source documents
3. Flag any claims that are not supported (hallucinations)

Scoring Guide:
- 10: All claims are directly supported by sources, no hallucinations
- 7-9: Most claims supported, minor unsupported details that don't change meaning
- 4-6: Some claims supported, some hallucinations present
- 0-3: Mostly hallucinated content, not grounded in sources

You must respond with a valid JSON object in this exact format:
{{
  "claims": [
    {{
      "claim": "specific claim from the answer",
      "supported": true,
      "source": "where this is found in source documents"
    }},
    {{
      "claim": "another specific claim",
      "supported": false,
      "reason": "why this is not supported"
    }}
  ],
  "faithfulness_score": 9,
  "reasoning": "detailed explanation of the score"
}}"""


def extract_retrieved_content(run: Run) -> str:
    """Extract content from retrieve_relevant_chunks or retrieve_sections tool outputs."""
    sections = []

    if not run.outputs:
        return ""

    # Check if this is the main agent run with child runs
    if hasattr(run, 'child_runs') and run.child_runs:
        for child_run in run.child_runs:
            # Look for retrieve_relevant_chunks tool calls (NEW hybrid search)
            if child_run.name == 'retrieve_relevant_chunks':
                output = child_run.outputs
                if output and isinstance(output, dict):
                    content = output.get('output', '')
                    if content:
                        sections.append(str(content))

            # Also support legacy retrieve_sections tool (for backward compatibility)
            elif child_run.name == 'retrieve_sections':
                output = child_run.outputs
                if output and isinstance(output, dict):
                    content = output.get('output', '')
                    if content:
                        sections.append(str(content))

    return "\n\n---\n\n".join(sections) if sections else "No sections retrieved"


def extract_final_answer(run: Run) -> str:
    """Extract the final answer from the run outputs."""
    if not run.outputs:
        return ""

    # The final answer is in the main run's output
    if isinstance(run.outputs, dict):
        # Check for common output keys
        for key in ['output', 'answer', 'response', 'messages']:
            if key in run.outputs:
                output = run.outputs[key]
                # Handle different output formats
                if isinstance(output, str):
                    return output
                elif isinstance(output, list):
                    # LangGraph messages format
                    if output and isinstance(output[-1], dict):
                        return output[-1].get('content', '')
                elif isinstance(output, dict):
                    return output.get('content', str(output))

    return str(run.outputs)


def evaluate_faithfulness_with_llm(
    query: str,
    answer: str,
    retrieved_sections: str,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Use GPT-4 to evaluate answer faithfulness.

    Args:
        query: User's query
        answer: Agent's answer
        retrieved_sections: Retrieved document content
        model: OpenAI model to use

    Returns:
        Evaluation result with score and reasoning
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    prompt = FAITHFULNESS_PROMPT.format(
        query=query,
        retrieved_sections=retrieved_sections,
        answer=answer
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert evaluator that assesses answer faithfulness. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # Normalize score to 0-1 range
        score = result.get('faithfulness_score', 0) / 10.0

        return {
            'score': score,
            'claims': result.get('claims', []),
            'reasoning': result.get('reasoning', ''),
            'raw_score': result.get('faithfulness_score', 0)
        }

    except Exception as e:
        return {
            'score': 0.0,
            'claims': [],
            'reasoning': f'Error during evaluation: {str(e)}',
            'raw_score': 0,
            'error': str(e)
        }


@evaluator
def answer_faithfulness_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    LangSmith evaluator for answer faithfulness.

    Checks if the agent's answer is grounded in retrieved documents/chunks.
    Supports both hybrid search (retrieve_relevant_chunks) and legacy retrieval (retrieve_sections).
    Uses GPT-4 to identify claims and verify they're supported by sources.

    Args:
        run: The LangSmith run to evaluate
        example: The test example with inputs

    Returns:
        Evaluation result with score, reasoning, and claim analysis
    """
    # Extract query
    query = example.inputs.get('query', '')
    if not query:
        return {
            'key': 'answer_faithfulness',
            'score': 0.0,
            'comment': 'No query found in example inputs'
        }

    # Extract answer and retrieved sections
    answer = extract_final_answer(run)
    if not answer:
        return {
            'key': 'answer_faithfulness',
            'score': 0.0,
            'comment': 'No answer found in run outputs'
        }

    retrieved_sections = extract_retrieved_content(run)

    # Evaluate with LLM
    result = evaluate_faithfulness_with_llm(query, answer, retrieved_sections)

    # Count supported vs unsupported claims
    claims = result.get('claims', [])
    supported_count = sum(1 for c in claims if c.get('supported', False))
    total_claims = len(claims)

    comment = result['reasoning']
    if total_claims > 0:
        comment += f" ({supported_count}/{total_claims} claims supported)"

    return {
        'key': 'answer_faithfulness',
        'score': result['score'],
        'comment': comment,
        'metadata': {
            'claims': claims,
            'supported_count': supported_count,
            'total_claims': total_claims,
            'raw_score': result.get('raw_score', 0)
        }
    }


# Standalone function for testing
def evaluate_answer_faithfulness(
    query: str,
    answer: str,
    retrieved_sections: str,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Standalone function to evaluate answer faithfulness.

    Args:
        query: User's query
        answer: Agent's answer
        retrieved_sections: Retrieved document content
        model: OpenAI model to use

    Returns:
        Evaluation result
    """
    result = evaluate_faithfulness_with_llm(query, answer, retrieved_sections, model)

    claims = result.get('claims', [])
    supported_count = sum(1 for c in claims if c.get('supported', False))
    total_claims = len(claims)

    comment = result['reasoning']
    if total_claims > 0:
        comment += f" ({supported_count}/{total_claims} claims supported)"

    return {
        'key': 'answer_faithfulness',
        'score': result['score'],
        'comment': comment,
        'metadata': {
            'claims': claims,
            'supported_count': supported_count,
            'total_claims': total_claims,
            'raw_score': result.get('raw_score', 0)
        }
    }


if __name__ == '__main__':
    # Example usage for testing
    print("Answer Faithfulness Evaluator - Test\n")
    print("=" * 70)

    query = "What tranches are in this deal?"

    retrieved_sections = """
    Section: Description of the Certificates

    The certificates consist of the following classes:
    - Class A-1 Senior Certificates
    - Class A-2 Senior Certificates
    - Class B Subordinate Certificates
    - Class C Subordinate Certificates

    The Class A certificates have a total original principal balance of $300 million.
    """

    # Test 1: Faithful answer
    print("\nTest 1: Faithful answer (all claims supported)")
    print("-" * 70)
    answer1 = "This deal consists of four certificate classes: Class A-1, Class A-2, Class B, and Class C. The Class A certificates are senior and have a total principal balance of $300 million."

    result1 = evaluate_answer_faithfulness(query, answer1, retrieved_sections)
    print(f"Score: {result1['score']:.2f}")
    print(f"Comment: {result1['comment']}")
    print(f"\nClaims analysis:")
    for claim in result1['metadata']['claims']:
        status = "✓" if claim.get('supported') else "✗"
        print(f"  {status} {claim['claim']}")

    # Test 2: Answer with hallucination
    print("\n" + "=" * 70)
    print("\nTest 2: Answer with hallucination")
    print("-" * 70)
    answer2 = "This deal has Class A-1, A-2, B, C, and D certificates. The deal was issued in January 2024 and has a 5-year maturity."

    result2 = evaluate_answer_faithfulness(query, answer2, retrieved_sections)
    print(f"Score: {result2['score']:.2f}")
    print(f"Comment: {result2['comment']}")
    print(f"\nClaims analysis:")
    for claim in result2['metadata']['claims']:
        status = "✓" if claim.get('supported') else "✗"
        print(f"  {status} {claim['claim']}")
        if not claim.get('supported'):
            print(f"      Reason: {claim.get('reason', 'N/A')}")

    print("\n" + "=" * 70)
