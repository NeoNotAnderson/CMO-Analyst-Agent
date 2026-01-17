# Retrieval Methods Comparison: Current vs Semantic Search

## Overview

This document compares the **current taxonomy-based retrieval** approach with **semantic search using vector embeddings**.

---

## Current Implementation: Taxonomy-Based Retrieval

### How It Works

```
User Query: "What is the payment priority waterfall?"
    ↓
LLM Analysis (classify_query_sections)
    ↓
Identifies: category="deal_summary", subcategory="payment_priority"
    ↓
Database Query: SectionMap.objects.filter(category=..., subcategory=...)
    ↓
Returns: All sections matching exact category/subcategory
    ↓
Retrieves content from Prospectus.parsed_file
```

### Technical Implementation

**Step 1: Classification Schema**
```python
# Standardized taxonomy (from models.py)
class Category(models.TextChoices):
    DEAL_SUMMARY = 'deal_summary'
    RISK_DESCRIPTION = 'risk_factors'
    CERTIFICATE_DESCRIPTION = 'certificate_structure'
    COLLATERAL_DESCRIPTION = 'collateral_description'

class Subcategory(models.TextChoices):
    PAYMENT_PRIORITY = 'payment_priority'
    INTEREST_DISTRIBUTION = 'interest_distribution'
    PRINCIPAL_DISTRIBUTION = 'principal_distribution'
    # ... ~20 subcategories total
```

**Step 2: Query Analysis**
```python
@tool
def analyze_query_sections(user_query: str, prospectus_id: str) -> dict:
    """
    Use LLM to map query to taxonomy categories.

    Example:
        Query: "What are the prepayment risks?"
        → {
            "categories": ["risk_factors"],
            "subcategories": ["prepayment_risk"]
          }
    """
    # LLM classifies query into predefined categories
    # Returns structured output (Pydantic schema)
```

**Step 3: Database Retrieval**
```python
@tool
def retrieve_sections(prospectus_id: str, categories: list, subcategories: list) -> str:
    """
    Exact match retrieval from database.
    """
    sections = SectionMap.objects.filter(
        prospectus_id=prospectus_id,
        category__in=categories,
        subcategory__in=subcategories
    )

    # Retrieve actual content from parsed_file
    # Return formatted sections
```

### Advantages

| Advantage | Explanation |
|-----------|-------------|
| **Simple to implement** | No additional infrastructure (embeddings, vector DB) |
| **Fast retrieval** | Direct database index lookup (O(1) with proper indexes) |
| **Deterministic** | Same query → same sections every time |
| **Interpretable** | Clear why sections were selected (category match) |
| **Low latency** | PostgreSQL indexed query (~1-10ms) |
| **No preprocessing** | Sections classified during parsing (already done) |
| **Low cost** | No embedding API calls during retrieval |
| **Good for structured data** | CMO prospectuses have standard structure |

### Disadvantages

| Disadvantage | Explanation |
|--------------|-------------|
| **Rigid taxonomy** | Limited to predefined categories (~20 subcategories) |
| **Brittle to edge cases** | If query doesn't map cleanly to taxonomy → poor results |
| **No semantic understanding** | Can't handle synonyms or paraphrasing well |
| **All-or-nothing** | Returns entire section even if only 1 paragraph relevant |
| **No ranking** | All matching sections treated equally |
| **Classification errors** | If LLM misclassifies query → wrong sections retrieved |

### Real-World Examples

**Works Well:**
```
Query: "Show me the payment priority waterfall"
→ Maps to: subcategory="payment_priority"
→ Retrieves: Payment Priority section (pages 25-28)
→ Result: ✅ Correct section retrieved
```

**Edge Case Issue:**
```
Query: "How does the deal handle defaults on the underlying mortgages?"
→ Could map to: "default_loss" OR "risk_factors" OR "credit_enhancement"
→ LLM must choose ONE or ALL
→ If chooses wrong one → misses relevant content
```

---

## Alternative: Semantic Search with Vector Embeddings

### How It Works

```
User Query: "What is the payment priority waterfall?"
    ↓
Embed query using OpenAI/Cohere (1536-dim vector)
    ↓
Cosine similarity search in vector database (pgvector)
    ↓
Returns: Top K most similar text chunks (e.g., K=5)
    ↓
Ranked by relevance score
    ↓
Include top chunks in LLM context
```

### Technical Implementation

**Step 1: Preprocessing (One-Time)**
```python
from openai import OpenAI

def preprocess_prospectus_sections(prospectus_id: str):
    """
    Chunk and embed all prospectus content.

    Run once after parsing completes.
    """
    prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)

    # 1. Chunk the content
    chunks = []
    for section in prospectus.sections.all():
        # Split large sections into smaller chunks (512-1024 tokens each)
        section_chunks = chunk_text(section.content, max_tokens=512)

        for i, chunk_text in enumerate(section_chunks):
            chunks.append({
                'section_id': section.id,
                'chunk_index': i,
                'text': chunk_text,
                'metadata': {
                    'title': section.title,
                    'category': section.section_type,
                    'page_numbers': section.page_numbers
                }
            })

    # 2. Generate embeddings
    client = OpenAI()
    for chunk in chunks:
        response = client.embeddings.create(
            model="text-embedding-3-small",  # 1536 dimensions
            input=chunk['text']
        )
        chunk['embedding'] = response.data[0].embedding  # Vector of 1536 floats

    # 3. Store in vector database
    for chunk in chunks:
        VectorChunk.objects.create(
            prospectus_id=prospectus_id,
            section_id=chunk['section_id'],
            chunk_index=chunk['chunk_index'],
            text=chunk['text'],
            embedding=chunk['embedding'],  # PostgreSQL vector type
            metadata=chunk['metadata']
        )
```

**Step 2: Database Schema (New Model)**
```python
from pgvector.django import VectorField

class VectorChunk(models.Model):
    """
    Stores text chunks with embeddings for semantic search.
    """
    prospectus_id = models.ForeignKey(Prospectus, on_delete=models.CASCADE)
    section_id = models.ForeignKey(ProspectusSection, on_delete=models.CASCADE)
    chunk_index = models.IntegerField()
    text = models.TextField()  # Original text
    embedding = VectorField(dimensions=1536)  # Vector embedding
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=['prospectus_id']),
            # Vector index for fast similarity search
            # CREATE INDEX ON vector_chunk USING ivfflat (embedding vector_cosine_ops);
        ]
```

**Step 3: Semantic Search Tool**
```python
from pgvector.django import CosineDistance

@tool
def semantic_search_sections(user_query: str, prospectus_id: str, top_k: int = 5) -> str:
    """
    Retrieve relevant sections using semantic similarity.

    Args:
        user_query: User's question
        prospectus_id: Prospectus to search
        top_k: Number of chunks to retrieve

    Returns:
        str: Top K relevant chunks with similarity scores
    """
    # 1. Embed the query
    client = OpenAI()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=user_query
    )
    query_embedding = response.data[0].embedding

    # 2. Vector similarity search
    results = VectorChunk.objects.filter(
        prospectus_id=prospectus_id
    ).annotate(
        similarity=CosineDistance('embedding', query_embedding)
    ).order_by('similarity')[:top_k]

    # 3. Format results
    formatted = []
    for i, chunk in enumerate(results):
        formatted.append(f"""
        Rank {i+1} (Similarity: {1 - chunk.similarity:.3f}):
        Section: {chunk.metadata['title']}
        Pages: {chunk.metadata['page_numbers']}

        {chunk.text}
        """)

    return "\n\n".join(formatted)
```

### Advantages

| Advantage | Explanation |
|-----------|-------------|
| **Semantic understanding** | Matches meaning, not just keywords |
| **Flexible retrieval** | Not limited to predefined taxonomy |
| **Handles paraphrasing** | "payment waterfall" ≈ "distribution priority" |
| **Ranked results** | Most relevant chunks ranked by similarity score |
| **Fine-grained retrieval** | Returns specific paragraphs, not entire sections |
| **Better recall** | Can find relevant content across multiple sections |
| **Cross-section search** | Finds related content regardless of categorization |

### Disadvantages

| Disadvantage | Explanation |
|--------------|-------------|
| **Complex infrastructure** | Requires pgvector, embedding model, preprocessing pipeline |
| **Higher latency** | Embedding query (~50-200ms) + vector search (~10-50ms) |
| **Preprocessing cost** | Must embed entire prospectus (100+ pages × embeddings) |
| **Storage overhead** | 1536 floats per chunk × thousands of chunks |
| **Non-deterministic** | Similarity scores can vary slightly |
| **Less interpretable** | Why was this chunk retrieved? (similarity score is opaque) |
| **Ongoing costs** | Embedding API calls for every query |
| **Cold start problem** | Must process all prospectuses upfront |

### Real-World Examples

**Handles Paraphrasing Well:**
```
Query: "How does the deal prioritize payments when cash is distributed?"
→ Embeds query
→ Finds high similarity with:
    - "Payment Priority" section (score: 0.89)
    - "Interest Distribution" section (score: 0.82)
    - "Principal Distribution" section (score: 0.78)
→ Returns top 3 chunks
→ Result: ✅ Finds relevant content even with different wording
```

**Cross-Section Discovery:**
```
Query: "What happens if borrowers default?"
→ Finds relevant passages from:
    - Risk Factors > Credit Enhancement Risk (score: 0.91)
    - Deal Summary > Credit Enhancement (score: 0.87)
    - Certificate Description > Loss Allocation (score: 0.85)
→ Result: ✅ Discovers related content across multiple sections
```

---

## Side-by-Side Comparison

| Aspect | Taxonomy-Based (Current) | Semantic Search (Alternative) |
|--------|-------------------------|-------------------------------|
| **Implementation Complexity** | Low (already implemented) | High (new infrastructure) |
| **Infrastructure Requirements** | PostgreSQL only | PostgreSQL + pgvector extension + embedding model |
| **Preprocessing Time** | ~5-10 min per prospectus (classification) | ~10-20 min per prospectus (chunking + embeddings) |
| **Query Latency** | 1-10ms (indexed DB query) | 50-200ms (embedding + vector search) |
| **Retrieval Precision** | High for exact category matches | High for semantic similarity |
| **Retrieval Recall** | Medium (limited to taxonomy) | High (semantic understanding) |
| **Cost per Query** | $0 (no API calls) | ~$0.0001 (embedding API call) |
| **Storage per Prospectus** | ~5-10 KB (section metadata) | ~10-50 MB (embeddings) |
| **Deterministic** | Yes | Mostly (minor variations) |
| **Interpretability** | High (clear category match) | Medium (similarity score) |
| **Edge Case Handling** | Poor (rigid taxonomy) | Good (flexible matching) |

---

## Hybrid Approach (Best of Both Worlds)

### Concept
Combine taxonomy-based retrieval with semantic search for optimal results.

### Implementation Strategy

```python
@tool
def hybrid_retrieve_sections(user_query: str, prospectus_id: str) -> str:
    """
    Two-stage retrieval: taxonomy + semantic search.

    Stage 1: Use taxonomy to narrow down to relevant sections (fast)
    Stage 2: Use semantic search within those sections (accurate)
    """
    # Stage 1: Taxonomy filtering (fast, broad)
    categories = analyze_query_sections(user_query, prospectus_id)

    candidate_sections = SectionMap.objects.filter(
        prospectus_id=prospectus_id,
        category__in=categories['categories']
    )

    # Stage 2: Semantic search within candidates (accurate, narrow)
    # Only embed and search chunks from candidate sections
    candidate_section_ids = [s.id for s in candidate_sections]

    results = semantic_search_sections(
        user_query=user_query,
        section_ids=candidate_section_ids,  # Limited scope
        top_k=5
    )

    return results
```

### Advantages of Hybrid
- **Fast initial filtering** - Taxonomy reduces search space by 80-90%
- **Semantic precision** - Final ranking uses similarity
- **Lower cost** - Fewer chunks to embed/search
- **Better interpretability** - Know which sections AND why chunks match

---

## Recommendation for Your Project

### For MVP (Current Phase)
**Stick with taxonomy-based retrieval**

**Reasons:**
1. CMO prospectuses have standardized structure (taxonomy maps well)
2. Already implemented and working
3. Zero additional infrastructure
4. Fast and deterministic
5. Good enough for 80-90% of queries

**When it falls short:**
- User asks questions that don't map cleanly to taxonomy
- **Solution**: Add more subcategories as needed
- **Fallback**: LLM can retrieve multiple categories if unsure

### For Production (Post-MVP)
**Implement hybrid approach**

**Migration Path:**
1. **Phase 1** (Current): Taxonomy only ✓
2. **Phase 2**: Add semantic search infrastructure
   - Install pgvector extension
   - Create VectorChunk model
   - Build preprocessing pipeline
3. **Phase 3**: Run hybrid retrieval
   - Use taxonomy for initial filtering
   - Use semantic search for ranking
4. **Phase 4**: A/B test and optimize
   - Compare retrieval quality
   - Measure latency impact
   - Optimize chunk size and top_k

### When to Switch?

**Triggers to implement semantic search:**
1. User queries frequently miss relevant sections (measured by feedback)
2. Users ask questions with varied phrasing (taxonomy struggles)
3. Cross-section queries become common (need to search across categories)
4. Prospectus structure becomes less standardized (new deal types)

**Metrics to track:**
- **Retrieval accuracy**: % of queries that retrieve relevant sections
- **User satisfaction**: Thumbs up/down on responses
- **Coverage**: % of queries that map to existing taxonomy

---

## Code Example: Extending Current Implementation

### Easy Win: Add Keyword Fallback

If taxonomy classification is uncertain, fall back to keyword search:

```python
@tool
def retrieve_sections_with_fallback(user_query: str, prospectus_id: str) -> str:
    """
    Try taxonomy first, fall back to keyword search if needed.
    """
    # Try taxonomy-based retrieval
    categories_result = analyze_query_sections(user_query, prospectus_id)

    if categories_result['confidence'] < 0.7:  # Low confidence
        # Fall back to keyword search in SectionMap
        keywords = extract_keywords(user_query)  # Simple NLP

        sections = SectionMap.objects.filter(
            prospectus_id=prospectus_id,
            keywords__overlap=keywords  # PostgreSQL array overlap
        )
    else:
        # Use taxonomy
        sections = SectionMap.objects.filter(
            prospectus_id=prospectus_id,
            category__in=categories_result['categories'],
            subcategory__in=categories_result.get('subcategories', [])
        )

    return format_sections(sections)
```

This gives you 90% of semantic search benefits with 10% of the complexity.

---

## Summary

### Current (Taxonomy-Based) ✅
- **Best for**: MVP, standardized documents, fast implementation
- **Weakness**: Rigid, limited to predefined categories
- **Status**: Already implemented, working well

### Semantic Search
- **Best for**: Production, varied queries, cross-section search
- **Weakness**: Complex, higher cost, slower
- **Status**: Future enhancement

### Hybrid (Recommended Long-Term)
- **Best for**: Production with high query volume
- **Combines**: Speed of taxonomy + accuracy of semantic search
- **Migration**: Implement after MVP proves product-market fit

**Bottom Line**: Your current approach is correct for MVP. Semantic search is a valuable enhancement for later, not a replacement.
