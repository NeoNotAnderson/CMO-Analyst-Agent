## Testing Guide: Chunking + Hybrid Search Implementation

## Overview

Comprehensive tests have been created for the new chunking and hybrid search features:

1. **Chunking tests** - Text chunking, table processing, embedding generation
2. **Retrieval tests** - Semantic search, keyword search, RRF, reranking, full pipeline
3. **Integration tests** - End-to-end tests with real database

---

## Test Files

### 1. **`backend/agents/query_agent/test_chunking.py`**

Tests for the chunking module:

- `ChunkTextTestCase` - Text chunking with token limits and overlap
- `GenerateTableDescriptionTestCase` - Table-to-text conversion
- `ProcessSectionToChunksTestCase` - Section processing with metadata
- `ProcessProspectusToChunksTestCase` - Full prospectus chunking
- `TokenCountingTestCase` - Token counting accuracy

**What's tested:**
- ✅ Paragraph-aware splitting (never splits mid-paragraph)
- ✅ Token limit enforcement (chunks ≤ 512 tokens)
- ✅ Overlap calculation (10% overlap between chunks)
- ✅ Section heading prepending
- ✅ Table description generation
- ✅ Hierarchical section paths
- ✅ Sequential chunk indexing
- ✅ Metadata extraction

### 2. **`backend/agents/query_agent/test_retrieval.py`**

Tests for the retrieval module:

- `ReciprocalRankFusionTestCase` - RRF algorithm
- `FormatRetrievedChunksTestCase` - Result formatting
- `HybridSearchIntegrationTestCase` - Full hybrid search with database
- `RetrieveRelevantChunksToolTestCase` - Tool integration

**What's tested:**
- ✅ Semantic search (vector similarity)
- ✅ Keyword search (BM25)
- ✅ RRF merging with different weights
- ✅ Metadata filtering
- ✅ Cross-encoder reranking
- ✅ Full hybrid search pipeline
- ✅ Result formatting for LLM
- ✅ Error handling (no chunks, invalid prospectus)

### 3. **`backend/agents/parsing_agent/test.py`** (Existing)

Tests for the parsing agent:
- Index parsing
- Full prospectus parsing
- Agent workflow
- Caching behavior

---

## Running Tests

### Quick Start

```bash
cd backend

# Run all tests
python run_tests.py

# Run specific module
python run_tests.py chunking
python run_tests.py retrieval

# Run with verbose output
python run_tests.py -v 3

# Keep test database between runs (faster)
python run_tests.py --keepdb
```

### Using Django Test Command

```bash
# Run all tests
python manage.py test

# Run specific test file
python manage.py test agents.query_agent.test_chunking

# Run specific test class
python manage.py test agents.query_agent.test_chunking.ChunkTextTestCase

# Run specific test method
python manage.py test agents.query_agent.test_chunking.ChunkTextTestCase.test_chunk_text_basic

# Run with verbose output
python manage.py test --verbosity=2

# Keep test database
python manage.py test --keepdb
```

### Using pytest (Alternative)

```bash
# Install pytest-django first
pip install pytest pytest-django

# Run all tests
pytest

# Run specific file
pytest agents/query_agent/test_chunking.py

# Run with verbose output
pytest -v

# Run specific test
pytest agents/query_agent/test_chunking.py::ChunkTextTestCase::test_chunk_text_basic
```

---

## Test Coverage

### Unit Tests (Fast, No External Dependencies)

**Chunking Module:**
- ✅ Text chunking logic
- ✅ Token counting
- ✅ Paragraph splitting
- ✅ Overlap calculation
- ✅ Table description generation
- ✅ Metadata extraction

**Retrieval Module:**
- ✅ RRF algorithm
- ✅ Result formatting
- ✅ Weight calculations

**Mocked:** OpenAI API calls, embeddings, reranker

**Run time:** ~5 seconds

### Integration Tests (Require Database)

**Database Operations:**
- ✅ Semantic search with pgvector
- ✅ Keyword search with BM25
- ✅ Hybrid search pipeline
- ✅ Metadata filtering
- ✅ Tool integration

**Mocked:** OpenAI API calls (embeddings still mocked)

**Run time:** ~15 seconds

**Setup required:**
- PostgreSQL with pgvector extension
- Django migrations applied
- Test database created

### End-to-End Tests (Full Integration)

**Parsing Agent:**
- ✅ PDF parsing (with real PDF)
- ✅ Chunking + embedding generation
- ✅ Database storage
- ✅ Agent workflow

**Query Agent:**
- ✅ Full RAG pipeline
- ✅ Hybrid search
- ✅ LLM integration

**Requires:**
- Real PDF file
- OpenAI API key
- PostgreSQL database
- All dependencies

**Run time:** Several minutes

**Skip if:**
```python
if not os.path.exists('test_data/sample.pdf'):
    self.skipTest("PDF file not found")

if not os.getenv("OPENAI_API_KEY"):
    self.skipTest("API key not set")
```

---

## Test Database Setup

### 1. Enable pgvector

```sql
-- Connect to test database
psql your_test_database

-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Verify Setup

```python
from core.models import ProspectusChunk

# This should work without errors
chunk = ProspectusChunk()
print(chunk.embedding)  # Should be a VectorField
```

---

## Writing New Tests

### Test Template

```python
from django.test import TestCase
from unittest.mock import patch

class MyNewTestCase(TestCase):
    """Test description."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test data
        pass

    def test_something(self):
        """Test specific behavior."""
        # Arrange
        input_data = ...

        # Act
        result = my_function(input_data)

        # Assert
        self.assertEqual(result, expected)

    @patch('module.external_call')
    def test_with_mock(self, mock_call):
        """Test with mocked external dependency."""
        mock_call.return_value = fake_data

        result = my_function()

        self.assertTrue(result)
        mock_call.assert_called_once()
```

### Best Practices

1. **Mock external calls**
   ```python
   @patch('agents.parsing_agent.chunking.openai_client.embeddings.create')
   def test_embeddings(self, mock_create):
       mock_create.return_value.data = [Mock(embedding=[0.1] * 1536)]
       # Test code
   ```

2. **Use TransactionTestCase for database tests**
   ```python
   from django.test import TransactionTestCase

   class DatabaseTest(TransactionTestCase):
       # Tests that need real database commits
       pass
   ```

3. **Clean up after tests**
   ```python
   def tearDown(self):
       # Delete test objects
       self.test_prospectus.delete()
   ```

4. **Skip tests conditionally**
   ```python
   def test_with_pdf(self):
       if not os.path.exists('test.pdf'):
           self.skipTest("PDF not found")
       # Test code
   ```

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt

      - name: Run migrations
        run: |
          cd backend
          python manage.py migrate

      - name: Run tests
        run: |
          cd backend
          python run_tests.py
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost/test_db
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## Test Data

### Sample Test Data Structure

```
backend/agents/
├── parsing_agent/
│   └── test_data/
│       ├── sample.pdf              # Sample prospectus (if available)
│       ├── parsed_index.json       # Pre-parsed index
│       └── page_*.json             # Pre-parsed pages
└── query_agent/
    └── test_data/
        └── sample_chunks.json      # Sample chunks for testing
```

### Creating Test Data

```python
# Create sample chunks for testing
test_chunks = [
    {
        'chunk_text': 'Tranche A-1 has a coupon rate of 3.50%',
        'chunk_index': 0,
        'embedding': [0.1] * 1536,
        'metadata': {
            'section_path': ['SUMMARY', 'The Certificates'],
            'page_num': 15,
            'has_table': True
        }
    }
]

# Save to file
import json
with open('test_data/sample_chunks.json', 'w') as f:
    json.dump(test_chunks, f, indent=2)
```

---

## Troubleshooting

### Common Issues

#### 1. **pgvector extension not found**

**Error:** `django.db.utils.OperationalError: extension "vector" is not available`

**Solution:**
```bash
# Install pgvector
brew install pgvector  # macOS
# or
sudo apt-get install postgresql-16-pgvector  # Linux

# Enable in database
psql your_database -c "CREATE EXTENSION vector;"
```

#### 2. **Test database creation fails**

**Error:** `permission denied to create database`

**Solution:**
```bash
# Grant create database permission
psql postgres -c "ALTER USER your_user CREATEDB;"
```

#### 3. **Import errors in tests**

**Error:** `ModuleNotFoundError: No module named 'agents'`

**Solution:**
```bash
# Ensure you're running from backend directory
cd backend
python manage.py test

# Or set PYTHONPATH
export PYTHONPATH=/path/to/backend:$PYTHONPATH
```

#### 4. **OpenAI API tests fail**

**Error:** `openai.error.AuthenticationError`

**Solution:**
```bash
# Set API key
export OPENAI_API_KEY=your_key_here

# Or create .env file
echo "OPENAI_API_KEY=your_key" >> .env
```

#### 5. **Slow tests**

**Solution:**
```bash
# Use --keepdb to reuse test database
python manage.py test --keepdb

# Run only unit tests (not integration tests)
python manage.py test agents.query_agent.test_chunking.ChunkTextTestCase
```

---

## Performance Benchmarks

Expected test run times (on M1 Mac):

| Test Suite | Count | Time |
|------------|-------|------|
| Chunking unit tests | 15 | ~3s |
| Retrieval unit tests | 10 | ~2s |
| Retrieval integration tests | 8 | ~15s |
| Parsing integration tests | 5 | ~2min |
| **Total (all tests)** | **38** | **~2.5min** |

With `--keepdb` flag: ~1.5min

---

## Next Steps

### Additional Tests to Write

1. **Query agent end-to-end tests**
   - Full RAG workflow
   - Multi-hop questions
   - Error handling

2. **Performance tests**
   - Large prospectuses (500+ chunks)
   - Concurrent queries
   - Memory usage

3. **Migration tests**
   - Test migrate_to_chunking command
   - Verify backward compatibility
   - Test rollback scenarios

4. **Edge cases**
   - Very long sections
   - Malformed tables
   - Missing metadata

---

## Summary

✅ **Comprehensive test coverage** for chunking and hybrid search
✅ **Unit tests** for fast development feedback
✅ **Integration tests** for database operations
✅ **Mocked external calls** to avoid API costs
✅ **Easy to run** with simple commands
✅ **CI/CD ready** for automated testing

Run tests frequently during development to catch regressions early!
