"""
Simple script to validate dataset JSON files without requiring LangSmith.
"""

import json
from pathlib import Path


def validate_test_case(case: dict, case_number: int) -> list:
    """Validate a single test case structure."""
    errors = []
    required_fields = ['test_id', 'query']
    optional_fields = [
        'prospectus_id', 'prospectus_name', 'session_id', 'user_id',
        'reference_answer', 'query_type', 'category', 'difficulty',
        'expected_trajectory', 'reference_sections', 'expected_facts',
        'evaluation_focus', 'metadata'
    ]

    # Check required fields
    for field in required_fields:
        if field not in case:
            errors.append(f"Test case {case_number}: Missing required field '{field}'")

    # Check field types
    if 'test_id' in case and not isinstance(case['test_id'], str):
        errors.append(f"Test case {case_number}: 'test_id' must be a string")

    if 'query' in case and not isinstance(case['query'], str):
        errors.append(f"Test case {case_number}: 'query' must be a string")

    if 'reference_sections' in case and not isinstance(case['reference_sections'], list):
        errors.append(f"Test case {case_number}: 'reference_sections' must be a list")

    if 'expected_facts' in case and not isinstance(case['expected_facts'], list):
        errors.append(f"Test case {case_number}: 'expected_facts' must be a list")

    if 'evaluation_focus' in case and not isinstance(case['evaluation_focus'], list):
        errors.append(f"Test case {case_number}: 'evaluation_focus' must be a list")

    # Validate enum values
    valid_query_types = ['general', 'calculation', 'section_specific', 'comparison', 'definition']
    if 'query_type' in case and case['query_type'] not in valid_query_types:
        errors.append(f"Test case {case_number}: Invalid 'query_type' (must be one of {valid_query_types})")

    valid_categories = ['structure', 'cash_flow', 'legal', 'risk', 'general']
    if 'category' in case and case['category'] not in valid_categories:
        errors.append(f"Test case {case_number}: Invalid 'category' (must be one of {valid_categories})")

    valid_difficulties = ['easy', 'medium', 'hard']
    if 'difficulty' in case and case['difficulty'] not in valid_difficulties:
        errors.append(f"Test case {case_number}: Invalid 'difficulty' (must be one of {valid_difficulties})")

    return errors


def validate_dataset_file(file_path: Path) -> dict:
    """Validate a dataset JSON file."""
    result = {
        'file': file_path.name,
        'valid': True,
        'errors': [],
        'warnings': [],
        'test_case_count': 0
    }

    try:
        with open(file_path) as f:
            data = json.load(f)

        # Check if data is a list
        if not isinstance(data, list):
            result['valid'] = False
            result['errors'].append("File must contain an array of test cases")
            return result

        result['test_case_count'] = len(data)

        # Validate each test case
        for i, case in enumerate(data, 1):
            if not isinstance(case, dict):
                result['errors'].append(f"Test case {i} must be an object")
                result['valid'] = False
                continue

            errors = validate_test_case(case, i)
            result['errors'].extend(errors)
            if errors:
                result['valid'] = False

        # Check for duplicate test_ids
        test_ids = [case.get('test_id') for case in data if 'test_id' in case]
        if len(test_ids) != len(set(test_ids)):
            result['warnings'].append("Duplicate test_id values found")

    except json.JSONDecodeError as e:
        result['valid'] = False
        result['errors'].append(f"Invalid JSON: {e}")
    except Exception as e:
        result['valid'] = False
        result['errors'].append(f"Error reading file: {e}")

    return result


def main():
    """Validate all JSON files in the datasets directory."""
    datasets_dir = Path(__file__).parent / "datasets"

    if not datasets_dir.exists():
        print(f"❌ Datasets directory not found: {datasets_dir}")
        return

    json_files = list(datasets_dir.glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {datasets_dir}")
        return

    print(f"Validating {len(json_files)} dataset file(s)...\n")
    print("=" * 70)

    all_valid = True

    for json_file in json_files:
        result = validate_dataset_file(json_file)

        print(f"\n📄 {result['file']}")
        print(f"   Test cases: {result['test_case_count']}")

        if result['valid']:
            print(f"   ✅ Valid")
        else:
            print(f"   ❌ Invalid")
            all_valid = False

        if result['errors']:
            print(f"\n   Errors:")
            for error in result['errors']:
                print(f"     • {error}")

        if result['warnings']:
            print(f"\n   Warnings:")
            for warning in result['warnings']:
                print(f"     ⚠️  {warning}")

    print("\n" + "=" * 70)

    if all_valid:
        print("\n✅ All dataset files are valid!")
        print("\nNext steps:")
        print("1. Ensure LangSmith API key is set in .env")
        print("2. Install langsmith: pip install langsmith")
        print("3. Create dataset: python dataset_manager.py create golden_test_set.json")
    else:
        print("\n❌ Some dataset files have errors. Please fix them before uploading.")


if __name__ == "__main__":
    main()
