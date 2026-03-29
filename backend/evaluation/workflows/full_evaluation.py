"""
Full Evaluation Workflow

Runs all 4 evaluators on a dataset and generates comprehensive reports.
Provides both programmatic API and CLI interface.

Usage:
    # Programmatic
    from evaluation.workflows import run_full_evaluation

    results = run_full_evaluation(
        dataset_name='cmo-analyst-golden-v1',
        experiment_name='eval-2024-01-15'
    )

    # CLI
    python full_evaluation.py --dataset cmo-analyst-golden-v1 --output results.json
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langsmith import Client
from langsmith.evaluation import evaluate

from evaluation.evaluators import (
    document_relevance_evaluator,
    answer_faithfulness_evaluator,
    answer_helpfulness_evaluator,
    answer_correctness_evaluator
)


def get_target_function(agent_type: str = 'query') -> Callable:
    """
    Get the target function to evaluate.

    Args:
        agent_type: 'query' or 'parsing'

    Returns:
        Target function that takes inputs dict and returns outputs
    """
    if agent_type == 'query':
        from agents.query_agent.graph import run_agent

        def target(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Run query agent with inputs."""
            result = run_agent(
                session_id=inputs.get('session_id', 'eval-session'),
                user_query=inputs['query'],
                user_id=inputs.get('user_id', 'eval-user'),
                config=inputs.get('config', {})
            )
            return result

        return target

    elif agent_type == 'parsing':
        from agents.parsing_agent.graph import run_agent as run_parsing_agent

        def target(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Run parsing agent with inputs."""
            result = run_parsing_agent(
                prospectus_id=inputs['prospectus_id'],
                config=inputs.get('config', {})
            )
            return result

        return target

    else:
        raise ValueError(f"Unknown agent_type: {agent_type}")


def run_full_evaluation(
    dataset_name: str,
    experiment_name: Optional[str] = None,
    agent_type: str = 'query',
    evaluators: Optional[List[Callable]] = None,
    max_concurrency: int = 5,
    client: Optional[Client] = None
) -> Dict[str, Any]:
    """
    Run full evaluation with all evaluators on a dataset.

    Args:
        dataset_name: Name of the LangSmith dataset
        experiment_name: Name for this evaluation run (auto-generated if None)
        agent_type: 'query' or 'parsing'
        evaluators: List of evaluator functions (uses all 4 by default)
        max_concurrency: Maximum concurrent evaluations
        client: LangSmith client (creates new if None)

    Returns:
        Dict with results summary and metadata
    """
    if client is None:
        client = Client()

    # Generate experiment name if not provided
    if experiment_name is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        experiment_name = f"eval_{dataset_name}_{timestamp}"

    # Use all evaluators by default
    if evaluators is None:
        evaluators = [
            document_relevance_evaluator,
            answer_faithfulness_evaluator,
            answer_helpfulness_evaluator,
            answer_correctness_evaluator
        ]

    print(f"\n{'='*70}")
    print(f"Starting Full Evaluation")
    print(f"{'='*70}")
    print(f"Dataset: {dataset_name}")
    print(f"Experiment: {experiment_name}")
    print(f"Agent Type: {agent_type}")
    print(f"Evaluators: {len(evaluators)}")
    print(f"Max Concurrency: {max_concurrency}")
    print(f"{'='*70}\n")

    # Get target function
    target = get_target_function(agent_type)

    # Run evaluation
    print("Running evaluation...")
    results = evaluate(
        target,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=experiment_name,
        max_concurrency=max_concurrency,
        client=client
    )

    # Calculate summary statistics
    summary = calculate_summary_stats(results)

    # Print results
    print_evaluation_summary(summary, experiment_name)

    return {
        'experiment_name': experiment_name,
        'dataset_name': dataset_name,
        'results': results,
        'summary': summary,
        'timestamp': datetime.now().isoformat()
    }


def calculate_summary_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate summary statistics from evaluation results.

    Args:
        results: List of evaluation result dicts

    Returns:
        Summary statistics dict
    """
    if not results:
        return {
            'total_examples': 0,
            'evaluator_stats': {},
            'overall_pass_rate': 0.0
        }

    # Collect scores by evaluator
    evaluator_scores = {
        'document_relevance': [],
        'answer_faithfulness': [],
        'answer_helpfulness': [],
        'answer_correctness': []
    }

    for result in results:
        # Extract evaluation results from the result dict
        if hasattr(result, 'evaluation_results') and result.evaluation_results:
            eval_results = result.evaluation_results.get('results', [])
            for eval_result in eval_results:
                key = eval_result.get('key', '')
                score = eval_result.get('score')
                if key in evaluator_scores and score is not None:
                    evaluator_scores[key].append(score)

    # Calculate stats for each evaluator
    evaluator_stats = {}
    pass_thresholds = {
        'document_relevance': 0.70,
        'answer_faithfulness': 0.80,
        'answer_helpfulness': 0.70,
        'answer_correctness': 0.80
    }

    total_pass_count = 0
    total_eval_count = 0

    for evaluator_name, scores in evaluator_scores.items():
        if not scores:
            evaluator_stats[evaluator_name] = {
                'count': 0,
                'mean': None,
                'min': None,
                'max': None,
                'pass_rate': None
            }
            continue

        threshold = pass_thresholds.get(evaluator_name, 0.70)
        pass_count = sum(1 for s in scores if s >= threshold)

        evaluator_stats[evaluator_name] = {
            'count': len(scores),
            'mean': sum(scores) / len(scores),
            'min': min(scores),
            'max': max(scores),
            'threshold': threshold,
            'pass_count': pass_count,
            'pass_rate': pass_count / len(scores) if scores else 0
        }

        total_pass_count += pass_count
        total_eval_count += len(scores)

    overall_pass_rate = total_pass_count / total_eval_count if total_eval_count > 0 else 0

    return {
        'total_examples': len(results),
        'evaluator_stats': evaluator_stats,
        'overall_pass_rate': overall_pass_rate
    }


def print_evaluation_summary(summary: Dict[str, Any], experiment_name: str):
    """
    Print formatted evaluation summary.

    Args:
        summary: Summary statistics dict
        experiment_name: Name of the experiment
    """
    print(f"\n{'='*70}")
    print(f"Evaluation Results: {experiment_name}")
    print(f"{'='*70}\n")

    print(f"Total Examples: {summary['total_examples']}")
    print(f"Overall Pass Rate: {summary['overall_pass_rate']:.1%}\n")

    print(f"{'Evaluator':<25} {'Mean':<8} {'Min':<8} {'Max':<8} {'Pass Rate':<10}")
    print(f"{'-'*70}")

    for evaluator_name, stats in summary['evaluator_stats'].items():
        if stats['count'] == 0:
            print(f"{evaluator_name:<25} {'N/A':<8} {'N/A':<8} {'N/A':<8} {'N/A':<10}")
            continue

        mean = f"{stats['mean']:.2f}"
        min_val = f"{stats['min']:.2f}"
        max_val = f"{stats['max']:.2f}"
        pass_rate = f"{stats['pass_rate']:.1%}"

        print(f"{evaluator_name:<25} {mean:<8} {min_val:<8} {max_val:<8} {pass_rate:<10}")

    print(f"\n{'='*70}")
    print(f"View detailed results in LangSmith:")
    print(f"https://smith.langchain.com")
    print(f"{'='*70}\n")


def save_results_to_file(
    results: Dict[str, Any],
    output_path: str,
    format: str = 'json'
):
    """
    Save evaluation results to file.

    Args:
        results: Results dict from run_full_evaluation
        output_path: Path to save results
        format: 'json' or 'csv'
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == 'json':
        # Save full results as JSON
        with open(output_path, 'w') as f:
            # Convert results to serializable format
            serializable_results = {
                'experiment_name': results['experiment_name'],
                'dataset_name': results['dataset_name'],
                'timestamp': results['timestamp'],
                'summary': results['summary']
            }
            json.dump(serializable_results, f, indent=2)

        print(f"✅ Results saved to: {output_path}")

    elif format == 'csv':
        # Save summary as CSV
        import csv

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['Evaluator', 'Mean', 'Min', 'Max', 'Pass Rate', 'Threshold'])

            # Data
            for evaluator_name, stats in results['summary']['evaluator_stats'].items():
                if stats['count'] > 0:
                    writer.writerow([
                        evaluator_name,
                        f"{stats['mean']:.2f}",
                        f"{stats['min']:.2f}",
                        f"{stats['max']:.2f}",
                        f"{stats['pass_rate']:.2%}",
                        f"{stats['threshold']:.2f}"
                    ])

        print(f"✅ Results saved to: {output_path}")

    else:
        raise ValueError(f"Unknown format: {format}")


def main():
    """CLI interface for full evaluation."""
    parser = argparse.ArgumentParser(
        description='Run full evaluation on a dataset',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run evaluation on golden test set
  python full_evaluation.py --dataset cmo-analyst-golden-v1

  # Run with custom experiment name
  python full_evaluation.py --dataset cmo-analyst-golden-v1 --experiment my-eval

  # Save results to file
  python full_evaluation.py --dataset cmo-analyst-golden-v1 --output results.json

  # Run on parsing agent
  python full_evaluation.py --dataset parsing-test-v1 --agent parsing
        """
    )

    parser.add_argument(
        '--dataset',
        required=True,
        help='Name of the LangSmith dataset'
    )

    parser.add_argument(
        '--experiment',
        help='Name for this evaluation run (auto-generated if not provided)'
    )

    parser.add_argument(
        '--agent',
        choices=['query', 'parsing'],
        default='query',
        help='Agent type to evaluate (default: query)'
    )

    parser.add_argument(
        '--output',
        help='Path to save results (optional)'
    )

    parser.add_argument(
        '--format',
        choices=['json', 'csv'],
        default='json',
        help='Output format (default: json)'
    )

    parser.add_argument(
        '--max-concurrency',
        type=int,
        default=5,
        help='Maximum concurrent evaluations (default: 5)'
    )

    args = parser.parse_args()

    try:
        # Run evaluation
        results = run_full_evaluation(
            dataset_name=args.dataset,
            experiment_name=args.experiment,
            agent_type=args.agent,
            max_concurrency=args.max_concurrency
        )

        # Save results if output path provided
        if args.output:
            save_results_to_file(results, args.output, args.format)

        # Exit with success if overall pass rate is good
        if results['summary']['overall_pass_rate'] >= 0.80:
            print("✅ Evaluation PASSED (≥80% pass rate)")
            sys.exit(0)
        else:
            print(f"⚠️  Evaluation needs improvement ({results['summary']['overall_pass_rate']:.1%} pass rate)")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error running evaluation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
