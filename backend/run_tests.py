#!/usr/bin/env python
"""
Test runner for CMO Analyst Agent.

Usage:
    # Run all tests
    python run_tests.py

    # Run specific test module
    python run_tests.py chunking
    python run_tests.py retrieval

    # Run with more verbose output
    python run_tests.py -v 2

    # Run specific test class
    python run_tests.py retrieval.HybridSearchIntegrationTestCase
"""

import sys
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.test.utils import get_runner


TEST_MODULES = {
    'chunking': 'agents.query_agent.test_chunking',
    'retrieval': 'agents.query_agent.test_retrieval',
    'parsing': 'agents.parsing_agent.test',
    'all': None  # Run all tests
}


def print_usage():
    """Print usage information."""
    print(__doc__)
    print("\nAvailable test modules:")
    for name, path in TEST_MODULES.items():
        if path:
            print(f"  {name:12} - {path}")
    print()


def main():
    """Run tests based on command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(description='Run CMO Analyst Agent tests')
    parser.add_argument(
        'module',
        nargs='?',
        default='all',
        help='Test module to run (chunking, retrieval, parsing, or all)'
    )
    parser.add_argument(
        '-v', '--verbosity',
        type=int,
        default=2,
        choices=[0, 1, 2, 3],
        help='Test output verbosity (0-3)'
    )
    parser.add_argument(
        '--keepdb',
        action='store_true',
        help='Preserve test database between runs'
    )

    args = parser.parse_args()

    # Get test module path
    if args.module == 'all':
        test_labels = None  # Run all tests
        print("Running all tests...\n")
    elif args.module in TEST_MODULES:
        test_labels = [TEST_MODULES[args.module]]
        print(f"Running {args.module} tests...\n")
    else:
        # Assume it's a full module path
        test_labels = [args.module]
        print(f"Running tests: {args.module}\n")

    # Get test runner
    TestRunner = get_runner(settings)
    test_runner = TestRunner(
        verbosity=args.verbosity,
        interactive=True,
        keepdb=args.keepdb
    )

    # Run tests
    if test_labels:
        failures = test_runner.run_tests(test_labels)
    else:
        # Run all tests in agents app
        failures = test_runner.run_tests(['agents'])

    # Exit with error code if tests failed
    sys.exit(bool(failures))


if __name__ == '__main__':
    main()
