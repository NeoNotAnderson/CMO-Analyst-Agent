"""
Answer Helpfulness Evaluator

LLM-as-a-Judge evaluator that measures how helpful the agent's answer is for the user.
Evaluates completeness, clarity, actionability, and appropriate detail level.

Evaluation Target: Final Response
Evaluation Type: LLM-as-a-Judge (GPT-4)
"""

import os
import json
from typing import Dict, Any
from openai import OpenAI
from langsmith.schemas import Run, Example
from langsmith.evaluation import evaluator


HELPFULNESS_PROMPT = """You are evaluating how helpful an AI assistant's answer is for a financial analyst.

User Query: {query}

Assistant Answer:
{answer}

Context: The user is a financial analyst asking about CMO/CMBS prospectus details. They need accurate, clear, and actionable information to make investment decisions.

Evaluate the answer for helpfulness across these dimensions:

1. **Completeness** (0-10): Does it fully address the question?
   - 10: Addresses all aspects of the question thoroughly
   - 7-9: Addresses main aspects, minor details missing
   - 4-6: Partially addresses question, significant gaps
   - 0-3: Doesn't address the question adequately

2. **Clarity** (0-10): Is it easy to understand?
   - 10: Crystal clear, well-structured, no ambiguity
   - 7-9: Clear overall, minor clarity issues
   - 4-6: Somewhat unclear, requires re-reading
   - 0-3: Confusing, hard to understand

3. **Actionability** (0-10): Can the user take action based on this?
   - 10: Provides specific, usable information
   - 7-9: Mostly actionable, some details could be more specific
   - 4-6: Somewhat actionable, lacks specifics
   - 0-3: Too vague to act on

4. **Appropriate Detail** (0-10): Right level of detail?
   - 10: Perfect balance, not too brief or verbose
   - 7-9: Good balance, slightly over/under detailed
   - 4-6: Too brief or too verbose
   - 0-3: Severely lacking or overwhelming with detail

Calculate the overall score as the average of all four dimensions.

You must respond with a valid JSON object in this exact format:
{{
  "completeness": 9,
  "clarity": 8,
  "actionability": 7,
  "appropriate_detail": 8,
  "overall_score": 8.0,
  "reasoning": "Detailed explanation of why you gave these scores. Reference specific parts of the answer.",
  "strengths": ["What the answer does well"],
  "weaknesses": ["What could be improved"],
  "suggestions": "Specific suggestions for improvement"
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


def evaluate_helpfulness_with_llm(
    query: str,
    answer: str,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Use GPT-4 to evaluate answer helpfulness.

    Args:
        query: User's query
        answer: Agent's answer
        model: OpenAI model to use

    Returns:
        Evaluation result with scores and reasoning
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    prompt = HELPFULNESS_PROMPT.format(
        query=query,
        answer=answer
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert evaluator that assesses answer helpfulness. Always respond with valid JSON."},
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
            'completeness': result.get('completeness', 0),
            'clarity': result.get('clarity', 0),
            'actionability': result.get('actionability', 0),
            'appropriate_detail': result.get('appropriate_detail', 0),
            'reasoning': result.get('reasoning', ''),
            'strengths': result.get('strengths', []),
            'weaknesses': result.get('weaknesses', []),
            'suggestions': result.get('suggestions', ''),
            'raw_overall_score': result.get('overall_score', 0)
        }

    except Exception as e:
        return {
            'score': 0.0,
            'completeness': 0,
            'clarity': 0,
            'actionability': 0,
            'appropriate_detail': 0,
            'reasoning': f'Error during evaluation: {str(e)}',
            'strengths': [],
            'weaknesses': [],
            'suggestions': '',
            'raw_overall_score': 0,
            'error': str(e)
        }


@evaluator
def answer_helpfulness_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    LangSmith evaluator for answer helpfulness.

    Evaluates how helpful the answer is across multiple dimensions:
    completeness, clarity, actionability, and appropriate detail level.

    Args:
        run: The LangSmith run to evaluate
        example: The test example with inputs

    Returns:
        Evaluation result with score and dimensional breakdown
    """
    # Extract query
    query = example.inputs.get('query', '')
    if not query:
        return {
            'key': 'answer_helpfulness',
            'score': 0.0,
            'comment': 'No query found in example inputs'
        }

    # Extract answer
    answer = extract_final_answer(run)
    if not answer:
        return {
            'key': 'answer_helpfulness',
            'score': 0.0,
            'comment': 'No answer found in run outputs'
        }

    # Evaluate with LLM
    result = evaluate_helpfulness_with_llm(query, answer)

    # Build comment with dimension breakdown
    comment = result['reasoning']
    if result.get('completeness'):
        comment += f" [Completeness: {result['completeness']}/10, "
        comment += f"Clarity: {result['clarity']}/10, "
        comment += f"Actionability: {result['actionability']}/10, "
        comment += f"Detail: {result['appropriate_detail']}/10]"

    return {
        'key': 'answer_helpfulness',
        'score': result['score'],
        'comment': comment,
        'metadata': {
            'completeness': result['completeness'],
            'clarity': result['clarity'],
            'actionability': result['actionability'],
            'appropriate_detail': result['appropriate_detail'],
            'raw_overall_score': result.get('raw_overall_score', 0),
            'strengths': result.get('strengths', []),
            'weaknesses': result.get('weaknesses', []),
            'suggestions': result.get('suggestions', '')
        }
    }


# Standalone function for testing
def evaluate_answer_helpfulness(
    query: str,
    answer: str,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Standalone function to evaluate answer helpfulness.

    Args:
        query: User's query
        answer: Agent's answer
        model: OpenAI model to use

    Returns:
        Evaluation result
    """
    result = evaluate_helpfulness_with_llm(query, answer, model)

    comment = result['reasoning']
    if result.get('completeness'):
        comment += f" [Completeness: {result['completeness']}/10, "
        comment += f"Clarity: {result['clarity']}/10, "
        comment += f"Actionability: {result['actionability']}/10, "
        comment += f"Detail: {result['appropriate_detail']}/10]"

    return {
        'key': 'answer_helpfulness',
        'score': result['score'],
        'comment': comment,
        'metadata': {
            'completeness': result['completeness'],
            'clarity': result['clarity'],
            'actionability': result['actionability'],
            'appropriate_detail': result['appropriate_detail'],
            'raw_overall_score': result.get('raw_overall_score', 0),
            'strengths': result.get('strengths', []),
            'weaknesses': result.get('weaknesses', []),
            'suggestions': result.get('suggestions', '')
        }
    }


if __name__ == '__main__':
    # Example usage for testing
    print("Answer Helpfulness Evaluator - Test\n")
    print("=" * 70)

    query = "What tranches are in this deal?"

    # Test 1: Helpful, complete answer
    print("\nTest 1: Helpful, complete answer")
    print("-" * 70)
    answer1 = """This deal consists of four certificate classes:

1. **Class A-1** - Senior certificates with first priority for principal and interest payments
2. **Class A-2** - Senior certificates with second priority
3. **Class B** - Subordinate certificates providing credit enhancement to Class A
4. **Class C** - Most subordinate class, highest risk/return

The Class A certificates have a total original principal balance of $300 million and benefit from subordination provided by Classes B and C."""

    result1 = evaluate_answer_helpfulness(query, answer1)
    print(f"Overall Score: {result1['score']:.2f}")
    print(f"\nDimensional Scores:")
    print(f"  Completeness: {result1['metadata']['completeness']}/10")
    print(f"  Clarity: {result1['metadata']['clarity']}/10")
    print(f"  Actionability: {result1['metadata']['actionability']}/10")
    print(f"  Detail: {result1['metadata']['appropriate_detail']}/10")
    print(f"\nReasoning: {result1['metadata'].get('reasoning', result1['comment'])}")

    if result1['metadata'].get('strengths'):
        print(f"\nStrengths:")
        for s in result1['metadata']['strengths']:
            print(f"  + {s}")

    # Test 2: Too brief answer
    print("\n" + "=" * 70)
    print("\nTest 2: Too brief, incomplete answer")
    print("-" * 70)
    answer2 = "Classes A-1, A-2, B, and C."

    result2 = evaluate_answer_helpfulness(query, answer2)
    print(f"Overall Score: {result2['score']:.2f}")
    print(f"\nDimensional Scores:")
    print(f"  Completeness: {result2['metadata']['completeness']}/10")
    print(f"  Clarity: {result2['metadata']['clarity']}/10")
    print(f"  Actionability: {result2['metadata']['actionability']}/10")
    print(f"  Detail: {result2['metadata']['appropriate_detail']}/10")

    if result2['metadata'].get('weaknesses'):
        print(f"\nWeaknesses:")
        for w in result2['metadata']['weaknesses']:
            print(f"  - {w}")

    if result2['metadata'].get('suggestions'):
        print(f"\nSuggestions: {result2['metadata']['suggestions']}")

    # Test 3: Overly verbose answer
    print("\n" + "=" * 70)
    print("\nTest 3: Overly verbose answer")
    print("-" * 70)
    answer3 = """Let me provide you with an extremely detailed explanation about the tranches in this deal. First, let me explain what a tranche is - it's a French word meaning "slice" and in the context of structured finance... [continues for 500 words with excessive background information before actually answering the question]"""

    result3 = evaluate_answer_helpfulness(query, answer3)
    print(f"Overall Score: {result3['score']:.2f}")
    print(f"\nDimensional Scores:")
    print(f"  Completeness: {result3['metadata']['completeness']}/10")
    print(f"  Clarity: {result3['metadata']['clarity']}/10")
    print(f"  Actionability: {result3['metadata']['actionability']}/10")
    print(f"  Detail: {result3['metadata']['appropriate_detail']}/10")

    print("\n" + "=" * 70)
