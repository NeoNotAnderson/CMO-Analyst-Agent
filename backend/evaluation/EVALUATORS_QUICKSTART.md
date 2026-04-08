# Evaluators Quick Start Guide

Quick reference for using the 5 custom evaluators (4 core + 1 trajectory).

---

## Installation

```bash
# Install dependencies
pip install langsmith openai

# Set environment variables
export OPENAI_API_KEY="your-openai-api-key"
export LANGCHAIN_API_KEY="your-langsmith-api-key"
```

---

## The 5 Evaluators

### 1. Document Relevance (Unit Test)
✅ **Fast** • 🎯 **Deterministic** • ⚡ **No LLM cost**

Checks if retrieved chunks/sections are relevant to the query. Supports both hybrid search (`retrieve_relevant_chunks`) and legacy retrieval (`retrieve_sections`).

```python
from evaluation.evaluators import evaluate_document_relevance

result = evaluate_document_relevance(
    query="What tranches are in this deal?",
    retrieved_sections=["Description of Certificates", "Certificate Table"],
    expected_sections=["Description of Certificates", "Certificate Table"]
)

print(f"Score: {result['score']:.2f}")  # 1.00 (perfect match)
```

### 2. Answer Faithfulness (LLM-as-a-Judge)
🤖 **GPT-4** • 🔍 **Hallucination Detection** • 💰 **~$0.01/eval**

Verifies all claims are supported by source documents. Works with both hybrid search and legacy retrieval.

```python
from evaluation.evaluators import evaluate_answer_faithfulness

result = evaluate_answer_faithfulness(
    query="What tranches are in this deal?",
    answer="This deal has Class A-1, A-2, B, and C certificates.",
    retrieved_sections="Section: Description\nClass A-1, A-2, B, C..."
)

print(f"Score: {result['score']:.2f}")
print(f"Claims: {len(result['metadata']['claims'])}")
print(f"Supported: {result['metadata']['supported_count']}")
```

### 3. Answer Helpfulness (LLM-as-a-Judge)
🤖 **GPT-4** • 📊 **4 Dimensions** • 💰 **~$0.01/eval**

Evaluates completeness, clarity, actionability, and detail level.

```python
from evaluation.evaluators import evaluate_answer_helpfulness

result = evaluate_answer_helpfulness(
    query="What tranches are in this deal?",
    answer="This deal has four classes: A-1, A-2, B, and C..."
)

print(f"Overall: {result['score']:.2f}")
print(f"Completeness: {result['metadata']['completeness']}/10")
print(f"Clarity: {result['metadata']['clarity']}/10")
print(f"Actionability: {result['metadata']['actionability']}/10")
print(f"Detail: {result['metadata']['appropriate_detail']}/10")
```

### 4. Answer Correctness (Hybrid)
🤖 **GPT-4 + Entity Matching** • ✅ **Ground Truth** • 💰 **~$0.01/eval**

Compares answer against reference answer (70% semantic + 30% exact match).

```python
from evaluation.evaluators import evaluate_answer_correctness

result = evaluate_answer_correctness(
    query="What tranches are in this deal?",
    reference_answer="Classes A-1, A-2, A-3, A-4, B, C, D",
    actual_answer="The deal has A-1, A-2, A-3, A-4, B, C, and D certificates"
)

print(f"Overall: {result['score']:.2f}")
print(f"LLM Score: {result['metadata']['llm_score']:.2f}")
print(f"Exact Match: {result['metadata']['exact_match_score']:.2f}")
print(f"Matched: {result['metadata']['key_points_matched']}")
print(f"Missing: {result['metadata']['key_points_missing']}")
```

### 5. Trajectory (Rule-Based)
⚡ **Fast** • 🎯 **Deterministic** • ⚡ **No LLM cost**

Evaluates agent's tool call sequence for correctness and efficiency.

```python
from evaluation.workflows import evaluate_trajectory

result = evaluate_trajectory(
    actual_trajectory=['classify_query', 'retrieve_relevant_chunks'],
    expected_trajectory='classify_query -> retrieve_relevant_chunks'
)

print(f"Score: {result['score']:.2f}")
print(f"Matched Tools: {result['matched_tools']}")
print(f"Extra Tools: {result['extra_tools']}")
print(f"Has Duplicates: {result['has_duplicates']}")
```

---

## Using with LangSmith

### Run All 5 Evaluators on Dataset

```python
from langsmith.evaluation import evaluate
from evaluation.evaluators import (
    document_relevance_evaluator,
    answer_faithfulness_evaluator,
    answer_helpfulness_evaluator,
    answer_correctness_evaluator
)
from evaluation.workflows import trajectory_evaluator

# Define your target function
def run_query(inputs):
    from agents.query_agent.graph import run_agent
    return run_agent(
        session_id=inputs.get('session_id', 'eval-session'),
        user_query=inputs['query'],
        prospectus_id=inputs.get('prospectus_id')
    )

# Run evaluation with all 5 evaluators
results = evaluate(
    run_query,
    data="cmo-analyst-golden-v1",  # Your dataset name
    evaluators=[
        # Core 4: Output quality
        document_relevance_evaluator,
        answer_faithfulness_evaluator,
        answer_helpfulness_evaluator,
        answer_correctness_evaluator,
        # 5th: Execution path
        trajectory_evaluator
    ],
    experiment_prefix="eval-run"
)

print(f"Evaluated {len(results)} examples")
```

### View Results

```bash
# Results available at:
# https://smith.langchain.com/projects/[your-project]/datasets/[dataset-id]
```

---

## Testing Individual Evaluators

Each evaluator has a test suite:

```bash
cd backend/evaluation/evaluators

# Test each evaluator
python3 document_relevance.py
python3 answer_faithfulness.py
python3 answer_helpfulness.py
python3 answer_correctness.py
```

---

## Pass/Fail Thresholds

| Evaluator | Threshold | Score Range |
|-----------|-----------|-------------|
| Document Relevance | ≥ 0.70 | 0.0 - 1.0 |
| Answer Faithfulness | ≥ 0.80 | 0.0 - 1.0 |
| Answer Helpfulness | ≥ 0.70 | 0.0 - 1.0 |
| Answer Correctness | ≥ 0.80 | 0.0 - 1.0 |

---

## Common Patterns

### Pattern 1: Quick Quality Check

```python
from evaluation.evaluators import (
    evaluate_answer_faithfulness,
    evaluate_answer_correctness
)

# Check if answer is faithful and correct
faith = evaluate_answer_faithfulness(query, answer, sections)
correct = evaluate_answer_correctness(query, reference, answer)

if faith['score'] >= 0.8 and correct['score'] >= 0.8:
    print("✅ High quality answer")
else:
    print("❌ Needs improvement")
    print(f"  Faithfulness: {faith['score']:.2f}")
    print(f"  Correctness: {correct['score']:.2f}")
```

### Pattern 2: Evaluate All Dimensions

```python
from evaluation.evaluators import (
    evaluate_document_relevance,
    evaluate_answer_faithfulness,
    evaluate_answer_helpfulness,
    evaluate_answer_correctness
)

# Comprehensive evaluation
scores = {
    'relevance': evaluate_document_relevance(query, sections, expected)['score'],
    'faithfulness': evaluate_answer_faithfulness(query, answer, content)['score'],
    'helpfulness': evaluate_answer_helpfulness(query, answer)['score'],
    'correctness': evaluate_answer_correctness(query, reference, answer)['score']
}

avg_score = sum(scores.values()) / len(scores)
print(f"Average Score: {avg_score:.2f}")
print(f"Breakdown: {scores}")
```

### Pattern 3: Batch Evaluation

```python
test_cases = [
    {"query": "...", "reference": "...", "answer": "..."},
    {"query": "...", "reference": "...", "answer": "..."},
    # ... more cases
]

results = []
for case in test_cases:
    result = evaluate_answer_correctness(
        case['query'],
        case['reference'],
        case['answer']
    )
    results.append(result)

avg_score = sum(r['score'] for r in results) / len(results)
print(f"Average Correctness: {avg_score:.2f}")
```

---

## Troubleshooting

### Issue: "No module named 'langsmith'"
```bash
pip install langsmith
```

### Issue: "OPENAI_API_KEY not set"
```bash
export OPENAI_API_KEY="your-key-here"
```

### Issue: LLM evaluators fail with API error
- Check OpenAI API key is valid
- Check you have GPT-4 access
- Check API rate limits

### Issue: Document relevance returns 0.0
- Verify retrieved_sections is not empty
- Check section names match expected format
- Try without expected_sections (keyword mode)

---

## Performance Tips

1. **Use Document Relevance first** - It's fast and cheap, filter before expensive LLM evals
2. **Batch API calls** - Evaluate multiple examples at once
3. **Cache results** - Don't re-evaluate same examples
4. **Use sampling** - For large datasets, evaluate random sample first
5. **Parallel execution** - Run evaluations in parallel for speed

---

## Next Steps

1. Test evaluators on sample data
2. Run evaluation on golden test set
3. Review results in LangSmith
4. Adjust thresholds based on results
5. Integrate into CI/CD pipeline

---

**See Also**:
- [EVALUATION_PHASE2_COMPLETE.md](../../EVALUATION_PHASE2_COMPLETE.md) - Full Phase 2 documentation
- [README.md](../README.md) - Evaluation system overview
- [LANGSMITH_EVALUATION_PLAN.md](../../LANGSMITH_EVALUATION_PLAN.md) - Complete plan
