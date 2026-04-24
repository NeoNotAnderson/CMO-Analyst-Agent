"""
Dataset Manager for LangSmith Evaluation System.

This module manages evaluation datasets including:
- Loading test cases from JSON files
- Creating LangSmith datasets
- Exporting production data
- Dataset versioning and management
"""

from langsmith import Client
from typing import List, Dict, Optional
import json
from pathlib import Path
from datetime import datetime


class DatasetManager:
    """Manage LangSmith evaluation datasets."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DatasetManager.

        Args:
            api_key: Optional LangSmith API key. If not provided, uses environment variable.
        """
        self.client = Client(api_key=api_key) if api_key else Client()
        self.datasets_dir = Path(__file__).parent / "datasets"
        self.datasets_dir.mkdir(exist_ok=True)

    def create_dataset_from_json(
        self,
        json_file: str,
        dataset_name: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        Load test cases from JSON file and create LangSmith dataset.

        Args:
            json_file: Path to JSON file (can be filename or full path)
            dataset_name: Name for the dataset (defaults to filename without .json)
            description: Optional description for the dataset

        Returns:
            Dataset object from LangSmith

        Example JSON structure:
            [
              {
                "test_id": "test_001",
                "query": "What tranches are in this deal?",
                "prospectus_id": "uuid-here",
                "reference_answer": "Class A1, A2, B, Z",
                "metadata": {...}
              }
            ]
        """
        # Handle file path
        json_path = Path(json_file)
        if not json_path.is_absolute():
            json_path = self.datasets_dir / json_file

        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")

        # Load test cases
        with open(json_path) as f:
            test_cases = json.load(f)

        print(f"Loaded {len(test_cases)} test cases from {json_path.name}")

        # Generate dataset name from filename if not provided
        if not dataset_name:
            dataset_name = json_path.stem  # filename without .json

        if not description:
            description = f"Evaluation dataset from {json_path.name}"

        # Create dataset in LangSmith
        print(f"Creating dataset '{dataset_name}' in LangSmith...")

        try:
            dataset = self.client.create_dataset(
                dataset_name=dataset_name,
                description=description
            )
            print(f"✓ Dataset created: {dataset.id}")
        except Exception as e:
            # Dataset might already exist
            print(f"Dataset may already exist, trying to read it: {e}")
            dataset = self.client.read_dataset(dataset_name=dataset_name)
            print(f"✓ Using existing dataset: {dataset.id}")

        # Add examples to dataset
        print(f"Adding {len(test_cases)} examples...")

        for i, case in enumerate(test_cases, 1):
            try:
                # Extract inputs and outputs
                inputs = {
                    "query": case["query"],
                }

                # Add optional fields to inputs
                if "prospectus_id" in case:
                    inputs["prospectus_id"] = case["prospectus_id"]
                if "session_id" in case:
                    inputs["session_id"] = case["session_id"]
                if "user_id" in case:
                    inputs["user_id"] = case["user_id"]

                outputs = {}
                if "reference_answer" in case:
                    outputs["reference_answer"] = case["reference_answer"]

                # Prepare metadata
                metadata = {
                    "test_id": case.get("test_id", f"test_{i:03d}"),
                }

                # Add all optional metadata fields
                optional_fields = [
                    "prospectus_name",
                    "query_type",
                    "expected_trajectory",
                    "reference_sections",
                    "expected_facts",
                    "category",
                    "difficulty",
                    "evaluation_focus"
                ]

                for field in optional_fields:
                    if field in case:
                        metadata[field] = case[field]

                # Create example
                self.client.create_example(
                    dataset_id=dataset.id,
                    inputs=inputs,
                    outputs=outputs,
                    metadata=metadata
                )

                if i % 10 == 0:
                    print(f"  Added {i}/{len(test_cases)} examples...")

            except Exception as e:
                print(f"  ✗ Error adding example {i}: {e}")
                continue

        print(f"✓ Dataset '{dataset_name}' created with {len(test_cases)} examples")
        print(f"View at: https://smith.langchain.com/datasets/{dataset.id}")

        return dataset

    def export_production_queries(
        self,
        project_name: str,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """
        Export successful production queries to create test dataset.

        Args:
            project_name: LangSmith project name (e.g., "cmo-analyst-agent-prod")
            limit: Maximum number of queries to export
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of query dictionaries ready for manual review
        """
        print(f"Exporting queries from project: {project_name}")

        # Build filter
        filter_query = 'eq(status, "success")'

        # List successful runs
        runs = self.client.list_runs(
            project_name=project_name,
            filter=filter_query,
            limit=limit
        )

        queries = []

        for run in runs:
            # Skip if no inputs/outputs
            if not run.inputs or not run.outputs:
                continue

            # Extract data
            query_data = {
                "test_id": f"prod_{run.id[:8]}",
                "query": run.inputs.get("user_query", ""),
                "prospectus_id": run.metadata.get("prospectus_id") if run.metadata else None,
                "prospectus_name": run.metadata.get("prospectus_name") if run.metadata else None,
                "session_id": run.metadata.get("session_id") if run.metadata else None,
                "response": run.outputs.get("response", ""),
                "date": run.start_time.isoformat() if run.start_time else None,
                "run_id": str(run.id),
                "duration_ms": (run.end_time - run.start_time).total_seconds() * 1000 if run.end_time and run.start_time else None,
                # Placeholder for manual annotation
                "reference_answer": "TODO: Add reference answer",
                "query_type": "TODO: Add query type",
                "category": "TODO: Add category"
            }

            queries.append(query_data)

        print(f"✓ Exported {len(queries)} queries")

        # Save to JSON for manual review
        output_file = self.datasets_dir / f"production_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(queries, f, indent=2)

        print(f"✓ Saved to: {output_file}")
        print(f"\nNext steps:")
        print(f"1. Review the file and add reference answers")
        print(f"2. Remove or fix any queries with issues")
        print(f"3. Load as dataset: dataset_manager.create_dataset_from_json('{output_file.name}')")

        return queries

    def list_datasets(self):
        """List all datasets in LangSmith."""
        print("Datasets in LangSmith:")
        print("-" * 60)

        datasets = self.client.list_datasets()

        for dataset in datasets:
            example_count = len(list(self.client.list_examples(dataset_id=dataset.id)))
            print(f"• {dataset.name}")
            print(f"  ID: {dataset.id}")
            print(f"  Examples: {example_count}")
            print(f"  Created: {dataset.created_at}")
            print(f"  Description: {dataset.description or 'N/A'}")
            print()

    def delete_dataset(self, dataset_name: str):
        """Delete a dataset by name."""
        try:
            dataset = self.client.read_dataset(dataset_name=dataset_name)
            self.client.delete_dataset(dataset_id=dataset.id)
            print(f"✓ Deleted dataset: {dataset_name}")
        except Exception as e:
            print(f"✗ Error deleting dataset: {e}")

    def list_local_json_files(self):
        """List all JSON files in datasets directory."""
        json_files = list(self.datasets_dir.glob("*.json"))

        if not json_files:
            print(f"No JSON files found in {self.datasets_dir}")
            return []

        print(f"JSON files in {self.datasets_dir}:")
        print("-" * 60)

        for json_file in json_files:
            # Try to load and count test cases
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    count = len(data) if isinstance(data, list) else 1
                print(f"• {json_file.name} ({count} test cases)")
            except Exception as e:
                print(f"• {json_file.name} (error reading: {e})")

        return json_files


# CLI interface
if __name__ == "__main__":
    import sys

    manager = DatasetManager()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python dataset_manager.py create <json_file> [dataset_name]")
        print("  python dataset_manager.py list")
        print("  python dataset_manager.py list-local")
        print("  python dataset_manager.py export <project_name> [limit]")
        print("  python dataset_manager.py delete <dataset_name>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create":
        if len(sys.argv) < 3:
            print("Error: JSON file required")
            print("Usage: python dataset_manager.py create <json_file> [dataset_name]")
            sys.exit(1)

        json_file = sys.argv[2]
        dataset_name = sys.argv[3] if len(sys.argv) > 3 else None

        manager.create_dataset_from_json(json_file, dataset_name)

    elif command == "list":
        manager.list_datasets()

    elif command == "list-local":
        manager.list_local_json_files()

    elif command == "export":
        if len(sys.argv) < 3:
            print("Error: Project name required")
            print("Usage: python dataset_manager.py export <project_name> [limit]")
            sys.exit(1)

        project_name = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 100

        manager.export_production_queries(project_name, limit)

    elif command == "delete":
        if len(sys.argv) < 3:
            print("Error: Dataset name required")
            print("Usage: python dataset_manager.py delete <dataset_name>")
            sys.exit(1)

        dataset_name = sys.argv[2]
        confirm = input(f"Delete dataset '{dataset_name}'? (yes/no): ")

        if confirm.lower() == "yes":
            manager.delete_dataset(dataset_name)
        else:
            print("Cancelled")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
