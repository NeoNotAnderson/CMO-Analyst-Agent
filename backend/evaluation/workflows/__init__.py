"""
Evaluation Workflows

Comprehensive workflows for running evaluations and generating reports.

## Workflows

1. **Full Evaluation** - Run all 4 evaluators on a dataset
2. **Trajectory Evaluation** - Evaluate agent tool usage patterns
3. **Report Generation** - Generate HTML/Markdown/JSON/CSV reports

## Usage

### Programmatic API:

```python
from evaluation.workflows import run_full_evaluation, generate_report

# Run evaluation
results = run_full_evaluation(
    dataset_name='cmo-analyst-golden-v1',
    experiment_name='eval-2024-01-15'
)

# Generate HTML report
generate_report(results, 'reports/eval.html', format='html')
```

### Command Line:

```bash
# Run full evaluation
python -m evaluation.workflows.run_evaluation full --dataset cmo-analyst-golden-v1

# Run with trajectory
python -m evaluation.workflows.run_evaluation full --dataset cmo-analyst-golden-v1 --include-trajectory

# Run custom evaluators
python -m evaluation.workflows.run_evaluation custom --dataset cmo-analyst-golden-v1 --evaluators faithfulness correctness

# Save results to file
python -m evaluation.workflows.run_evaluation full --dataset cmo-analyst-golden-v1 --output results.json
```

## Components

- **full_evaluation.py** - Complete evaluation with all 4 evaluators
- **trajectory_evaluation.py** - Tool usage pattern evaluation
- **report_generator.py** - Multi-format report generation
- **run_evaluation.py** - Unified CLI interface
"""

from .full_evaluation import (
    run_full_evaluation,
    get_target_function,
    calculate_summary_stats,
    print_evaluation_summary,
    save_results_to_file
)

from .trajectory_evaluation import (
    trajectory_evaluator,
    evaluate_trajectory,
    parse_expected_trajectory,
    extract_trajectory_from_run,
    calculate_trajectory_similarity,
    detect_inefficiencies
)

from .report_generator import (
    generate_report,
    generate_html_report,
    generate_markdown_report
)

__version__ = '1.0.0'

__all__ = [
    # Full evaluation
    'run_full_evaluation',
    'get_target_function',
    'calculate_summary_stats',
    'print_evaluation_summary',
    'save_results_to_file',

    # Trajectory evaluation
    'trajectory_evaluator',
    'evaluate_trajectory',
    'parse_expected_trajectory',
    'extract_trajectory_from_run',
    'calculate_trajectory_similarity',
    'detect_inefficiencies',

    # Report generation
    'generate_report',
    'generate_html_report',
    'generate_markdown_report',
]
