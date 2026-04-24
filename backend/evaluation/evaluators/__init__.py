"""
Custom Evaluators for CMO Analyst Agent.

This package provides four custom evaluators for comprehensive quality assessment:

1. **Document Relevance** - Unit test evaluator checking if retrieved sections are relevant
2. **Answer Faithfulness** - LLM-as-a-Judge checking answer is grounded in sources
3. **Answer Helpfulness** - LLM-as-a-Judge assessing completeness, clarity, actionability
4. **Answer Correctness** - Hybrid evaluator comparing against reference answers

Usage with LangSmith:
    from evaluation.evaluators import (
        document_relevance_evaluator,
        answer_faithfulness_evaluator,
        answer_helpfulness_evaluator,
        answer_correctness_evaluator
    )

    # Use in evaluation workflow
    from langsmith.evaluation import evaluate

    results = evaluate(
        dataset_name="cmo-analyst-golden-v1",
        evaluators=[
            document_relevance_evaluator,
            answer_faithfulness_evaluator,
            answer_helpfulness_evaluator,
            answer_correctness_evaluator
        ]
    )

Standalone usage (for testing):
    from evaluation.evaluators import (
        evaluate_document_relevance,
        evaluate_answer_faithfulness,
        evaluate_answer_helpfulness,
        evaluate_answer_correctness
    )

    # Test individual evaluators
    result = evaluate_answer_correctness(
        query="What tranches are in this deal?",
        reference_answer="Classes A-1, A-2, B, C",
        actual_answer="The deal has A-1, A-2, B, and C certificates"
    )
"""

# LangSmith evaluators (decorated with @evaluator)
from .document_relevance import document_relevance_evaluator
from .answer_faithfulness import answer_faithfulness_evaluator
from .answer_helpfulness import answer_helpfulness_evaluator
from .answer_correctness import answer_correctness_evaluator

# Standalone evaluation functions
from .document_relevance import evaluate_document_relevance
from .answer_faithfulness import evaluate_answer_faithfulness
from .answer_helpfulness import evaluate_answer_helpfulness
from .answer_correctness import evaluate_answer_correctness

# Utility functions
from .utils import (
    extract_final_answer,
    extract_retrieved_sections,
    extract_retrieved_content,
    extract_tool_calls,
    extract_trajectory,
    get_reference_answer,
    get_expected_sections,
    get_expected_trajectory,
    normalize_score,
    calculate_f1_score,
    format_score_comment
)

__version__ = '1.0.0'

__all__ = [
    # LangSmith evaluators
    'document_relevance_evaluator',
    'answer_faithfulness_evaluator',
    'answer_helpfulness_evaluator',
    'answer_correctness_evaluator',

    # Standalone functions
    'evaluate_document_relevance',
    'evaluate_answer_faithfulness',
    'evaluate_answer_helpfulness',
    'evaluate_answer_correctness',

    # Utility functions
    'extract_final_answer',
    'extract_retrieved_sections',
    'extract_retrieved_content',
    'extract_tool_calls',
    'extract_trajectory',
    'get_reference_answer',
    'get_expected_sections',
    'get_expected_trajectory',
    'normalize_score',
    'calculate_f1_score',
    'format_score_comment',
]
