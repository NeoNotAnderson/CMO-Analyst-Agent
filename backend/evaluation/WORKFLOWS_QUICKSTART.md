# Evaluation Workflows Quick Start

Quick reference for running evaluation workflows.

---

## Setup

```bash
# Install dependencies
pip install langsmith openai

# Set environment variables
export OPENAI_API_KEY="your-openai-api-key"
export LANGCHAIN_API_KEY="your-langsmith-api-key"
export LANGCHAIN_TRACING_V2="true"
```

---

## Run Evaluation (Quickest Way)

```bash
cd backend/evaluation/workflows

# Run full evaluation on golden test set
python run_evaluation.py full --dataset cmo-analyst-golden-v1
```

**Output**:
```
======================================================================
Starting Full Evaluation
======================================================================
Dataset: cmo-analyst-golden-v1
Experiment: eval_cmo-analyst-golden-v1_20240115_143022
Agent Type: query
Evaluators: 4
Max Concurrency: 5
======================================================================

Running evaluation...

======================================================================
Evaluation Results: eval_cmo-analyst-golden-v1_20240115_143022
======================================================================

Total Examples: 10
Overall Pass Rate: 85.0%

Evaluator                 Mean     Min      Max      Pass Rate
----------------------------------------------------------------------
document_relevance        0.92     0.75     1.00     90.0%
answer_faithfulness       0.88     0.70     0.95     80.0%
answer_helpfulness        0.85     0.65     0.95     90.0%
answer_correctness        0.82     0.60     0.95     80.0%

======================================================================
✅ Evaluation PASSED (≥80% pass rate)
```

---

## CLI Commands

### Full Evaluation

```bash
# Basic - all 4 evaluators
python run_evaluation.py full --dataset cmo-analyst-golden-v1

# With trajectory evaluation (5 evaluators)
python run_evaluation.py full --dataset cmo-analyst-golden-v1 --include-trajectory

# Save results to file
python run_evaluation.py full --dataset cmo-analyst-golden-v1 --output results.json

# Custom experiment name
python run_evaluation.py full --dataset cmo-analyst-golden-v1 --experiment my-test-run

# Increase concurrency
python run_evaluation.py full --dataset cmo-analyst-golden-v1 --max-concurrency 10
```

### Trajectory Evaluation Only

```bash
python run_evaluation.py trajectory --dataset cmo-analyst-golden-v1
```

### Custom Evaluators

```bash
# Run specific evaluators
python run_evaluation.py custom \
  --dataset cmo-analyst-golden-v1 \
  --evaluators faithfulness correctness

# Run all evaluators including trajectory
python run_evaluation.py custom \
  --dataset cmo-analyst-golden-v1 \
  --evaluators relevance faithfulness helpfulness correctness trajectory
```

### List Available Evaluators

```bash
python run_evaluation.py list
```

**Output**:
```
Available Evaluators:
----------------------------------------------------------------------
  relevance      - Document Relevance (Unit Test)
  faithfulness   - Answer Faithfulness (LLM-as-a-Judge)
  helpfulness    - Answer Helpfulness (LLM-as-a-Judge)
  correctness    - Answer Correctness (Hybrid)
  trajectory     - Agent Trajectory (Rule-Based)
```

---

## Programmatic API

### Run Full Evaluation

```python
from evaluation.workflows import run_full_evaluation

results = run_full_evaluation(
    dataset_name='cmo-analyst-golden-v1',
    experiment_name='my-eval',
    agent_type='query',
    max_concurrency=5
)

# Access results
print(f"Total Examples: {results['summary']['total_examples']}")
print(f"Pass Rate: {results['summary']['overall_pass_rate']:.1%}")

for evaluator, stats in results['summary']['evaluator_stats'].items():
    print(f"{evaluator}: {stats['mean']:.2f} (pass rate: {stats['pass_rate']:.1%})")
```

### Generate Reports

```python
from evaluation.workflows import generate_report

# HTML report with visualizations
generate_report(results, 'reports/eval.html', format='html')

# Markdown for documentation
generate_report(results, 'reports/eval.md', format='markdown')

# JSON for programmatic access
generate_report(results, 'reports/eval.json', format='json')

# CSV for Excel/Sheets
generate_report(results, 'reports/eval.csv', format='csv')
```

### Evaluate Trajectory

```python
from evaluation.workflows import evaluate_trajectory

result = evaluate_trajectory(
    actual_trajectory=['classify_query', 'analyze_query_sections', 'retrieve_sections'],
    expected_trajectory='classify_query -> analyze_query_sections -> retrieve_sections'
)

print(f"Score: {result['score']:.2f}")
print(f"Matched: {result['metadata']['matched_tools']}")
print(f"Missing: {result['metadata']['missing_tools']}")
```

---

## Output Formats

### Console Output

Immediate feedback with:
- Progress indicators
- Summary statistics
- Pass/fail status
- Per-evaluator breakdown
- LangSmith link

### JSON Output

```json
{
  "experiment_name": "eval_golden_20240115",
  "dataset_name": "cmo-analyst-golden-v1",
  "timestamp": "2024-01-15T14:30:22",
  "summary": {
    "total_examples": 10,
    "overall_pass_rate": 0.85,
    "evaluator_stats": {
      "document_relevance": {
        "count": 10,
        "mean": 0.92,
        "min": 0.75,
        "max": 1.0,
        "threshold": 0.70,
        "pass_count": 9,
        "pass_rate": 0.90
      }
    }
  }
}
```

### HTML Report

Beautiful visual report with:
- Responsive design
- Summary cards
- Progress bars
- Status badges
- Metric breakdowns
- Direct LangSmith link

### Markdown Report

```markdown
# Evaluation Report

**Dataset:** cmo-analyst-golden-v1
**Pass Rate:** 85.0%
**Status:** ✅ PASS

| Evaluator | Mean | Pass Rate | Status |
|-----------|------|-----------|--------|
| Document Relevance | 0.92 | 90.0% | ✅ Pass |
| Answer Faithfulness | 0.88 | 80.0% | ✅ Pass |
| Answer Helpfulness | 0.85 | 90.0% | ✅ Pass |
| Answer Correctness | 0.82 | 80.0% | ✅ Pass |
```

---

## Common Workflows

### 1. Quick Quality Check

```bash
# Run evaluation and get immediate feedback
python run_evaluation.py full --dataset cmo-analyst-golden-v1
```

### 2. Detailed Analysis

```bash
# Run with trajectory and save results
python run_evaluation.py full \
  --dataset cmo-analyst-golden-v1 \
  --include-trajectory \
  --output results.json

# Generate HTML report for visual analysis
python -c "
from evaluation.workflows import generate_report
import json
with open('results.json') as f:
    results = json.load(f)
generate_report(results, 'report.html', 'html')
"

# Open in browser
open report.html
```

### 3. CI/CD Integration

```bash
# Run evaluation with strict pass criteria
python run_evaluation.py full \
  --dataset cmo-analyst-golden-v1 \
  --output results.json

# Exit code: 0 if pass rate ≥80%, 1 otherwise
echo "Exit code: $?"
```

### 4. Custom Evaluation

```python
from evaluation.workflows import run_full_evaluation
from evaluation.evaluators import (
    answer_faithfulness_evaluator,
    answer_correctness_evaluator
)

# Run only critical evaluators
results = run_full_evaluation(
    dataset_name='cmo-analyst-golden-v1',
    evaluators=[
        answer_faithfulness_evaluator,
        answer_correctness_evaluator
    ]
)
```

---

## Pass/Fail Thresholds

| Evaluator | Individual Threshold | Overall Target |
|-----------|---------------------|----------------|
| Document Relevance | ≥ 0.70 | ≥ 80% pass rate |
| Answer Faithfulness | ≥ 0.80 | ≥ 80% pass rate |
| Answer Helpfulness | ≥ 0.70 | ≥ 80% pass rate |
| Answer Correctness | ≥ 0.80 | ≥ 80% pass rate |
| Trajectory | ≥ 0.70 | ≥ 80% pass rate |

**Overall Pass**: ≥80% of all evaluations meet their threshold

---

## Performance

| Dataset Size | Time (5 concurrent) | Cost (USD) |
|--------------|---------------------|------------|
| 10 examples | ~1-2 minutes | ~$0.30 |
| 50 examples | ~5-10 minutes | ~$1.50 |
| 100 examples | ~10-20 minutes | ~$3.00 |

**Cost Breakdown**:
- Document Relevance: Free (no LLM)
- LLM Evaluators (3×): ~$0.01 each
- Trajectory: Free (rule-based)

---

## Troubleshooting

### Issue: "No module named 'langsmith'"
```bash
pip install langsmith
```

### Issue: "OPENAI_API_KEY not set"
```bash
export OPENAI_API_KEY="your-key"
```

### Issue: "Dataset not found"
```bash
# List available datasets
python -c "from langsmith import Client; c = Client(); [print(d.name) for d in c.list_datasets()]"

# Create dataset from golden test set
cd backend/evaluation
python dataset_manager.py create golden_test_set.json cmo-analyst-golden-v1
```

### Issue: Evaluation too slow
```bash
# Increase concurrency
python run_evaluation.py full --dataset cmo-analyst-golden-v1 --max-concurrency 10

# Run only fast evaluators
python run_evaluation.py custom --dataset cmo-analyst-golden-v1 --evaluators relevance trajectory
```

### Issue: Need to debug failures
1. Run evaluation: `python run_evaluation.py full --dataset cmo-analyst-golden-v1`
2. Go to LangSmith: https://smith.langchain.com
3. Navigate to your project
4. Click on "Datasets" → "cmo-analyst-golden-v1"
5. Click on "Testing" to view detailed results
6. Filter by failed evaluations
7. Click on individual traces for debugging

---

## Next Steps

1. **Run your first evaluation**: `python run_evaluation.py full --dataset cmo-analyst-golden-v1`
2. **Generate a report**: Save results and create HTML report
3. **Review in LangSmith**: Analyze failures and edge cases
4. **Integrate with CI/CD**: Add to GitHub Actions
5. **Set up monitoring**: Schedule regular evaluation runs

---

**See Also**:
- [EVALUATION_PHASE3_COMPLETE.md](../../EVALUATION_PHASE3_COMPLETE.md) - Complete Phase 3 documentation
- [full_evaluation.py](full_evaluation.py) - Full evaluation workflow
- [run_evaluation.py](run_evaluation.py) - CLI interface
- [report_generator.py](report_generator.py) - Report generation
