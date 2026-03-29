# LangSmith Evaluation System

Comprehensive evaluation infrastructure for the CMO Analyst Agent using LangSmith.

## Overview

This evaluation system provides:
- **Dataset Management**: Create and manage test datasets from JSON files or production data
- **Custom Evaluators**: 4 production-ready evaluators (document relevance, faithfulness, helpfulness, correctness)
- **Evaluation Workflows**: Automated evaluation pipelines (Coming in Phase 3)
- **Production Monitoring**: Continuous quality monitoring in production (Coming in Phase 4)

## Implementation Status

- ✅ **Phase 1**: Infrastructure Setup (Complete)
- ✅ **Phase 2**: Custom Evaluators (Complete)
- 🔄 **Phase 3**: Evaluation Workflows (Next)
- 📋 **Phase 4**: Production Monitoring (Planned)

## Quick Start

### 1. Setup LangSmith

Ensure LangSmith is configured in your `.env`:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=cmo-analyst-agent-dev
```

### 2. Create a Test Dataset

#### From JSON file:

```python
from evaluation import DatasetManager

manager = DatasetManager()

# Create dataset from golden test set
dataset = manager.create_dataset_from_json(
    json_file='golden_test_set.json',
    dataset_name='cmo-analyst-golden-v1',
    description='Golden test set for CMO Analyst Agent v1'
)
```

#### Command line:

```bash
cd backend/evaluation
python dataset_manager.py create golden_test_set.json cmo-analyst-golden-v1
```

### 3. Export Production Queries

Export real user queries to create test datasets:

```python
manager = DatasetManager()

queries = manager.export_production_queries(
    project_name='cmo-analyst-agent-prod',
    limit=100
)
# Review the exported JSON file, add reference answers, then upload as dataset
```

Command line:

```bash
python dataset_manager.py export cmo-analyst-agent-prod 100
```

### 4. Run Evaluations

```python
from langsmith.evaluation import evaluate
from evaluation.evaluators import (
    document_relevance_evaluator,
    answer_faithfulness_evaluator,
    answer_helpfulness_evaluator,
    answer_correctness_evaluator
)

# Run all evaluators on dataset
results = evaluate(
    target_function,
    data="cmo-analyst-golden-v1",
    evaluators=[
        document_relevance_evaluator,
        answer_faithfulness_evaluator,
        answer_helpfulness_evaluator,
        answer_correctness_evaluator
    ]
)
```

See [EVALUATORS_QUICKSTART.md](EVALUATORS_QUICKSTART.md) for detailed evaluator usage.

### 5. Manage Datasets

```python
# List all datasets
manager.list_datasets()

# List local JSON files
manager.list_local_json_files()

# Delete a dataset
manager.delete_dataset('old-dataset-name')
```

## Test Case Format

Test cases use the following JSON structure:

```json
{
  "test_id": "unique_identifier",
  "query": "User's question",
  "prospectus_id": "UUID of prospectus",
  "prospectus_name": "Deal name",
  "reference_answer": "Expected answer",
  "query_type": "general|calculation|section_specific|comparison|definition",
  "category": "structure|cash_flow|legal|risk|general",
  "difficulty": "easy|medium|hard",
  "expected_trajectory": "classify_query -> analyze_query_sections -> retrieve_sections",
  "reference_sections": ["Section 1", "Section 2"],
  "expected_facts": ["Fact 1", "Fact 2"],
  "evaluation_focus": ["document_relevance", "faithfulness", "helpfulness", "correctness"]
}
```

See `datasets/test_case_template.json` for the complete template.

## Dataset Files

### Golden Test Set (`golden_test_set.json`)

10 carefully crafted test cases covering:
- **Easy queries**: Basic factual retrieval (Who is the master servicer?)
- **Medium queries**: Definitions and calculations (What is a Z-tranche?)
- **Hard queries**: Complex synthesis (Compare yields, Key risk factors)

Query types:
- Section-specific (6 cases)
- Definition (3 cases)
- Calculation (1 case)
- Comparison (1 case)

Categories:
- Structure (5 cases)
- Cash flow (2 cases)
- Risk (1 case)
- Legal (1 case)
- General (1 case)

### Production Export Template

When exporting production queries, each entry includes:
```json
{
  "test_id": "prod_12345678",
  "query": "User's actual query",
  "response": "Agent's actual response",
  "prospectus_id": "UUID",
  "session_id": "session_id",
  "run_id": "langsmith_run_id",
  "date": "2024-01-15T10:30:00",
  "duration_ms": 2500,
  "reference_answer": "TODO: Add reference answer",
  "query_type": "TODO: Add query type",
  "category": "TODO: Add category"
}
```

**Workflow:**
1. Export production queries: `python dataset_manager.py export cmo-analyst-agent-prod 100`
2. Review the JSON file and fill in TODOs (reference answers, query types, categories)
3. Upload as dataset: `python dataset_manager.py create production_export_20240115_103000.json`

## CLI Usage

The `dataset_manager.py` script provides a command-line interface:

```bash
# Create dataset from JSON
python dataset_manager.py create <json_file> [dataset_name]

# List datasets in LangSmith
python dataset_manager.py list

# List local JSON files
python dataset_manager.py list-local

# Export production queries
python dataset_manager.py export <project_name> [limit]

# Delete a dataset
python dataset_manager.py delete <dataset_name>
```

### Examples:

```bash
# Create golden test set
python dataset_manager.py create golden_test_set.json cmo-analyst-golden-v1

# Export 50 production queries
python dataset_manager.py export cmo-analyst-agent-prod 50

# List all datasets
python dataset_manager.py list

# Delete old dataset
python dataset_manager.py delete old-test-dataset
```

## Next Steps

### Phase 2: Custom Evaluators (Weeks 2-3)

Implement custom evaluators:
- `document_relevance.py` - Check if retrieved documents are relevant
- `answer_faithfulness.py` - Verify answer uses only retrieved info
- `answer_helpfulness.py` - Assess completeness and clarity
- `answer_correctness.py` - Compare against reference answer

### Phase 3: Evaluation Workflows (Week 3)

Create evaluation workflows:
- Full response evaluation
- Trajectory evaluation (tool usage patterns)
- Single-step evaluation (individual tool performance)

### Phase 4: Production Monitoring (Week 4)

Set up continuous monitoring:
- Automated evaluation runs
- Quality metric dashboards
- Alerting on regressions

## Viewing Results

Access evaluation results in LangSmith:

1. Go to https://smith.langchain.com
2. Navigate to your project (e.g., `cmo-analyst-agent-dev`)
3. Click "Datasets" to view all datasets
4. Click "Testing" to view evaluation results

Filter traces by:
- Tags: `evaluation`, `golden_test_set`
- Metadata: `dataset_name`, `test_id`

## Directory Structure

```
evaluation/
├── README.md                       # This file
├── __init__.py                     # Package initialization
├── dataset_manager.py              # Dataset management utilities
├── datasets/                       # Test datasets
│   ├── test_case_template.json    # Template for creating test cases
│   ├── golden_test_set.json       # Golden test set (10 cases)
│   └── production_export_*.json   # Exported production queries
├── evaluators/                     # Custom evaluators (Phase 2)
│   ├── document_relevance.py
│   ├── answer_faithfulness.py
│   ├── answer_helpfulness.py
│   └── answer_correctness.py
└── workflows/                      # Evaluation workflows (Phase 3)
    ├── full_evaluation.py
    └── trajectory_evaluation.py
```

## Troubleshooting

### Dataset Creation Fails

**Error**: `Dataset already exists`
**Solution**: Either use the existing dataset or delete it first:
```bash
python dataset_manager.py delete dataset-name
```

### LangSmith API Key Not Set

**Error**: `LANGCHAIN_API_KEY is not set`
**Solution**: Add your API key to `.env`:
```bash
LANGCHAIN_API_KEY=your-api-key-here
```

### No Test Cases Found

**Error**: `Loaded 0 test cases`
**Solution**: Check JSON file format. Ensure it's an array of test case objects.

## References

- Full evaluation plan: `LANGSMITH_EVALUATION_PLAN.md`
- LangSmith documentation: https://docs.smith.langchain.com/
- Dataset schema: `datasets/test_case_template.json`
