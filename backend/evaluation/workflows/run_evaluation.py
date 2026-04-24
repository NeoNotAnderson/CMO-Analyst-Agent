#!/usr/bin/env python3
"""
Unified CLI for Running Evaluations

Provides a single command-line interface for all evaluation workflows.

Usage:
    # Run full evaluation (all 4 evaluators)
    python run_evaluation.py full --dataset cmo-analyst-golden-v1

    # Run with trajectory evaluation
    python run_evaluation.py full --dataset cmo-analyst-golden-v1 --include-trajectory

    # Run only trajectory evaluation
    python run_evaluation.py trajectory --dataset cmo-analyst-golden-v1

    # Run specific evaluators
    python run_evaluation.py custom --dataset cmo-analyst-golden-v1 --evaluators faithfulness correctness

    # Save results
    python run_evaluation.py full --dataset cmo-analyst-golden-v1 --output results.json
"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langsmith.evaluation import evaluate
from langsmith import Client

from evaluation.evaluators import (
    document_relevance_evaluator,
    answer_faithfulness_evaluator,
    answer_helpfulness_evaluator,
    answer_correctness_evaluator
)
from evaluation.workflows.trajectory_evaluation import trajectory_evaluator
from evaluation.workflows.full_evaluation import (
    run_full_evaluation,
    get_target_function,
    save_results_to_file
)


EVALUATOR_MAP = {
    'relevance': document_relevance_evaluator,
    'faithfulness': answer_faithfulness_evaluator,
    'helpfulness': answer_helpfulness_evaluator,
    'correctness': answer_correctness_evaluator,
    'trajectory': trajectory_evaluator
}


def run_full_workflow(args):
    """Run full evaluation workflow."""
    # Select evaluators
    evaluators = [
        document_relevance_evaluator,
        answer_faithfulness_evaluator,
        answer_helpfulness_evaluator,
        answer_correctness_evaluator
    ]

    # Add trajectory evaluator if requested
    if args.include_trajectory:
        evaluators.append(trajectory_evaluator)

    # Run evaluation
    results = run_full_evaluation(
        dataset_name=args.dataset,
        experiment_name=args.experiment,
        agent_type=args.agent,
        evaluators=evaluators,
        max_concurrency=args.max_concurrency
    )

    # Save results if requested
    if args.output:
        save_results_to_file(results, args.output, args.format)

    return results


def run_trajectory_workflow(args):
    """Run trajectory evaluation only."""
    print(f"\n{'='*70}")
    print(f"Running Trajectory Evaluation")
    print(f"{'='*70}\n")

    target = get_target_function(args.agent)
    client = Client()

    results = evaluate(
        target,
        data=args.dataset,
        evaluators=[trajectory_evaluator],
        experiment_prefix=args.experiment or f"trajectory_{args.dataset}",
        max_concurrency=args.max_concurrency,
        client=client
    )

    print(f"\n✅ Trajectory evaluation complete")
    print(f"View results: https://smith.langchain.com\n")

    return results


def run_custom_workflow(args):
    """Run custom selection of evaluators."""
    if not args.evaluators:
        print("Error: --evaluators required for custom workflow", file=sys.stderr)
        sys.exit(1)

    # Map evaluator names to evaluator functions
    selected_evaluators = []
    for eval_name in args.evaluators:
        if eval_name not in EVALUATOR_MAP:
            print(f"Error: Unknown evaluator '{eval_name}'", file=sys.stderr)
            print(f"Available: {', '.join(EVALUATOR_MAP.keys())}", file=sys.stderr)
            sys.exit(1)
        selected_evaluators.append(EVALUATOR_MAP[eval_name])

    print(f"\n{'='*70}")
    print(f"Running Custom Evaluation")
    print(f"{'='*70}")
    print(f"Evaluators: {', '.join(args.evaluators)}\n")

    # Run evaluation
    results = run_full_evaluation(
        dataset_name=args.dataset,
        experiment_name=args.experiment,
        agent_type=args.agent,
        evaluators=selected_evaluators,
        max_concurrency=args.max_concurrency
    )

    # Save results if requested
    if args.output:
        save_results_to_file(results, args.output, args.format)

    return results


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Unified CLI for running evaluations',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Create subcommands
    subparsers = parser.add_subparsers(dest='command', help='Evaluation workflow to run')
    subparsers.required = True

    # Common arguments
    def add_common_args(subparser):
        subparser.add_argument(
            '--dataset',
            required=True,
            help='Name of the LangSmith dataset'
        )
        subparser.add_argument(
            '--experiment',
            help='Name for this evaluation run (auto-generated if not provided)'
        )
        subparser.add_argument(
            '--agent',
            choices=['query', 'parsing'],
            default='query',
            help='Agent type to evaluate (default: query)'
        )
        subparser.add_argument(
            '--output',
            help='Path to save results (optional)'
        )
        subparser.add_argument(
            '--format',
            choices=['json', 'csv'],
            default='json',
            help='Output format (default: json)'
        )
        subparser.add_argument(
            '--max-concurrency',
            type=int,
            default=5,
            help='Maximum concurrent evaluations (default: 5)'
        )

    # Full evaluation workflow
    full_parser = subparsers.add_parser(
        'full',
        help='Run full evaluation with all 4 evaluators'
    )
    add_common_args(full_parser)
    full_parser.add_argument(
        '--include-trajectory',
        action='store_true',
        help='Also evaluate agent trajectories'
    )

    # Trajectory evaluation workflow
    trajectory_parser = subparsers.add_parser(
        'trajectory',
        help='Run trajectory evaluation only'
    )
    add_common_args(trajectory_parser)

    # Custom evaluation workflow
    custom_parser = subparsers.add_parser(
        'custom',
        help='Run custom selection of evaluators'
    )
    add_common_args(custom_parser)
    custom_parser.add_argument(
        '--evaluators',
        nargs='+',
        choices=['relevance', 'faithfulness', 'helpfulness', 'correctness', 'trajectory'],
        help='Evaluators to run'
    )

    # List available evaluators
    list_parser = subparsers.add_parser(
        'list',
        help='List available evaluators'
    )

    args = parser.parse_args()

    # Handle list command
    if args.command == 'list':
        print("\nAvailable Evaluators:")
        print("-" * 70)
        print("  relevance      - Document Relevance (Unit Test)")
        print("  faithfulness   - Answer Faithfulness (LLM-as-a-Judge)")
        print("  helpfulness    - Answer Helpfulness (LLM-as-a-Judge)")
        print("  correctness    - Answer Correctness (Hybrid)")
        print("  trajectory     - Agent Trajectory (Rule-Based)")
        print()
        return

    # Run appropriate workflow
    try:
        if args.command == 'full':
            results = run_full_workflow(args)
        elif args.command == 'trajectory':
            results = run_trajectory_workflow(args)
        elif args.command == 'custom':
            results = run_custom_workflow(args)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)

        # Check pass rate and exit accordingly
        if hasattr(results, 'summary'):
            pass_rate = results['summary'].get('overall_pass_rate', 0)
            if pass_rate >= 0.80:
                print("✅ Evaluation PASSED (≥80% pass rate)")
                sys.exit(0)
            else:
                print(f"⚠️  Evaluation needs improvement ({pass_rate:.1%} pass rate)")
                sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Evaluation interrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error running evaluation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
