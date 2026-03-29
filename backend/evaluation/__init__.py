"""
LangSmith Evaluation System for CMO Analyst Agent.

This package provides comprehensive evaluation infrastructure including:
- Dataset management (loading, creating, exporting test datasets)
- Custom evaluators (4 production-ready evaluators)
- Evaluation workflows (full evaluation, trajectory, reports)
- Production monitoring (coming in Phase 4)

## Implementation Status
- ✅ Phase 1: Infrastructure (Complete)
- ✅ Phase 2: Custom Evaluators (Complete)
- ✅ Phase 3: Evaluation Workflows (Complete)
- 📋 Phase 4: Production Monitoring (Planned)

## Quick Start

### Run Full Evaluation (CLI)
    cd backend/evaluation/workflows
    python run_evaluation.py full --dataset cmo-analyst-golden-v1

### Run Full Evaluation (Python)
    from evaluation.workflows import run_full_evaluation, generate_report

    # Run evaluation
    results = run_full_evaluation(
        dataset_name='cmo-analyst-golden-v1',
        experiment_name='my-eval'
    )

    # Generate report
    generate_report(results, 'report.html', format='html')

### Dataset Management
    from evaluation import DatasetManager

    # Create dataset from JSON
    manager = DatasetManager()
    dataset = manager.create_dataset_from_json('golden_test_set.json')

### Using Individual Evaluators
    from evaluation.evaluators import (
        document_relevance_evaluator,
        answer_faithfulness_evaluator,
        answer_helpfulness_evaluator,
        answer_correctness_evaluator
    )

    from langsmith.evaluation import evaluate

    results = evaluate(
        target_function,
        data='cmo-analyst-golden-v1',
        evaluators=[
            document_relevance_evaluator,
            answer_faithfulness_evaluator,
            answer_helpfulness_evaluator,
            answer_correctness_evaluator
        ]
    )

Directory structure:
    evaluation/
    ├── __init__.py                  # This file
    ├── dataset_manager.py           # Dataset management
    ├── datasets/                    # Test datasets (JSON)
    │   ├── test_case_template.json
    │   └── golden_test_set.json
    ├── evaluators/                  # Custom evaluators
    │   ├── document_relevance.py
    │   ├── answer_faithfulness.py
    │   ├── answer_helpfulness.py
    │   ├── answer_correctness.py
    │   └── utils.py
    └── workflows/                   # Evaluation workflows
        ├── full_evaluation.py
        ├── trajectory_evaluation.py
        ├── report_generator.py
        └── run_evaluation.py

See LANGSMITH_EVALUATION_PLAN.md for complete implementation details.
"""

from .dataset_manager import DatasetManager

# Import evaluators
from .evaluators import (
    # LangSmith evaluators
    document_relevance_evaluator,
    answer_faithfulness_evaluator,
    answer_helpfulness_evaluator,
    answer_correctness_evaluator,

    # Standalone functions
    evaluate_document_relevance,
    evaluate_answer_faithfulness,
    evaluate_answer_helpfulness,
    evaluate_answer_correctness,
)

# Import workflows
from .workflows import (
    run_full_evaluation,
    generate_report,
    trajectory_evaluator,
    evaluate_trajectory,
)

__version__ = '0.3.0'

__all__ = [
    # Dataset management
    'DatasetManager',

    # LangSmith evaluators
    'document_relevance_evaluator',
    'answer_faithfulness_evaluator',
    'answer_helpfulness_evaluator',
    'answer_correctness_evaluator',
    'trajectory_evaluator',

    # Standalone evaluation functions
    'evaluate_document_relevance',
    'evaluate_answer_faithfulness',
    'evaluate_answer_helpfulness',
    'evaluate_answer_correctness',
    'evaluate_trajectory',

    # Workflows
    'run_full_evaluation',
    'generate_report',
]
