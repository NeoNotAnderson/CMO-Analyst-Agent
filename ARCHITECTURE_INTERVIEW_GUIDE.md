# Architecture Interview Guide: CMO Analyst Agent

## Interview Question
**"Walk me through the architecture of your CMO Analyst Agent. Why did you make the design choices you did?"**

---

## Executive Summary (30-second answer)

"The CMO Analyst Agent is a production-ready RAG system that parses complex financial documents and provides intelligent Q&A through a conversational interface. The architecture has three main layers:

1. **Document Processing Layer** - Vision-based PDF parsing with hierarchical structure extraction
2. **Hybrid Search RAG Layer** - Semantic + keyword search with reranking for precise retrieval
3. **Agentic Layer** - LangGraph-based agents with persistent conversation memory

I prioritized **accuracy over speed** for financial data, chose **PostgreSQL with pgvector** for simplicity, and implemented **hybrid search** to handle both specific facts and general questions."

---

## Detailed Architecture Walkthrough

### 1. **System Overview**

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js + TypeScript)                            │
│  - Real-time chat with SSE streaming                        │
│  - File upload with status polling                          │
└──────────────────┬──────────────────────────────────────────┘
                   │ REST API / SSE
┌──────────────────▼──────────────────────────────────────────┐
│  Backend (Django + LangGraph)                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ API Layer (Django REST Framework)                     │  │
│  │  - Session management                                 │  │
│  │  - Streaming responses                                │  │
│  └────────┬──────────────────────────────────────────────┘  │
│  ┌────────▼──────────────────────────────────────────────┐  │
│  │ Agent Layer (LangGraph)                               │  │
│  │  ┌──────────────┐        ┌─────────────────┐         │  │
│  │  │Query Agent   │        │ Parsing Agent   │         │  │
│  │  │- Classify    │        │ - Extract ToC   │         │  │
│  │  │- Hybrid      │        │ - Vision parsing│         │  │
│  │  │  Search      │        │ - Chunking      │         │  │
│  │  └──────────────┘        └─────────────────┘         │  │
│  └────────┬──────────────────────────────────────────────┘  │
│  ┌────────▼──────────────────────────────────────────────┐  │
│  │ RAG Layer                                             │  │
│  │  - Hybrid Search (Semantic + Keyword + Reranking)    │  │
│  │  - Chunking (512 tokens, 10% overlap)                │  │
│  │  - Semantic memory (conversation history)            │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────┬──────────────────────────────────────────┘
┌──────────────────▼──────────────────────────────────────────┐
│  PostgreSQL Database                                        │
│  - Prospectuses (parsed JSON)                              │
│  - Chunks (text + 1536-dim vectors via pgvector)           │
│  - Conversations (messages + checkpoints)                  │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. **Document Processing Pipeline**

#### **Why Hybrid Parsing (Unstructured.io + GPT-4 Vision)?**

**Decision**: Use Unstructured.io for most pages, GPT-4 Vision only for tables

**Rationale**:
- ✅ **Cost-effective**: Unstructured.io is free, vision only when needed
- ✅ **Fast**: Unstructured.io processes pages quickly
- ✅ **Table accuracy**: Vision model resolves footnotes and preserves structure for complex tables
- ✅ **Best of both**: Balance speed/cost (Unstructured.io) with accuracy (Vision for tables)
- ❌ **More complex**: Two parsing paths to maintain

**Alternative considered**: Vision-only parsing
- ❌ 10x higher cost ($0.01-0.03 per page × 200 pages = $2-6 per doc)
- ❌ Slower (2-3 minutes for full document)
- ✅ Would be simpler implementation

#### **Two-Stage Parsing Flow**

```
Stage 1: Index Extraction
PDF → Find ToC pages → GPT-4 Vision → Hierarchical index JSON
     └─> Identifies section titles + page numbers

Stage 2: Page-by-Page Parsing (Guided by Index)
For each page in document:
  ├─> Parse with Unstructured.io (hi_res, infer_table_structure=True)
  ├─> Check: Does page contain tables?
  │   ├─> YES → Parse with GPT-4 Vision (resolves footnotes, structures data)
  │   └─> NO → Use Unstructured.io output (text extraction)
  └─> Combine with index structure to build hierarchy
```

**Why page-by-page (not section-by-section)?**
- ✅ **Simpler**: Each page processed independently
- ✅ **Cacheable**: Can store parsed pages in DB, skip if already parsed
- ✅ **Robust**: Handles sections spanning multiple pages easily

**Data Structure**:
```json
{
  "sections": [
    {
      "title": "RISK FACTORS",
      "level": 1,
      "page_num": 12,
      "text": "Full text content...",
      "table": {"summary": "...", "data": [...]},
      "sections": [
        {"title": "Prepayment Risk", "level": 2, ...}
      ]
    }
  ]
}
```

---

### 3. **Hybrid Search RAG System** (Recent Implementation)

#### **Problem with Original ToC-Based Approach**

**Original**: LLM selects 3 sections from table of contents
- ❌ Generic section titles ("General") → missed key info
- ❌ Specific facts buried in text → not found
- ❌ Query: "What is coupon rate of Tranche A-1?" → might miss table

#### **Solution: Chunking + Hybrid Search**

**Step 1: Chunking Strategy**

```python
# Design decisions
MAX_TOKENS = 512          # Optimal for context vs. granularity
OVERLAP = 10%             # Prevents context loss at boundaries
SPLIT_ON = Paragraphs     # Never split mid-paragraph
PREPEND = Section_title   # Each chunk includes heading
```

**Why 512 tokens?**
- ✅ Fits specific facts (e.g., table with tranche details)
- ✅ Small enough for precise retrieval
- ✅ Large enough for context
- ⚖️ Balance between too small (no context) and too large (noise)

**Why paragraph boundaries?**
- ✅ Preserves semantic coherence
- ✅ Sentences within paragraph are related
- ❌ Alternative (sentence-level): Too fragmented

**Table Handling**:
```python
# Separate chunk for each table
chunk = {
    'text': f"{section_title}\n\n{natural_language_description}\n\nTable data:\n{structured_data}",
    'metadata': {'has_table': True, ...}
}
```

**Why separate table chunks?**
- ✅ Can filter to tables only for data queries
- ✅ Natural language description → semantic search works
- ✅ Structured data preserved → keyword search finds exact values

**Step 2: Hybrid Search Pipeline**

```
Query: "What is the coupon rate of Tranche A-1?"
  │
  ├─> Semantic Search (pgvector)
  │     └─> Embedding similarity → ["certificate details", "tranche info", ...]
  │
  ├─> Keyword Search (BM25)
  │     └─> Term matching → ["Tranche A-1", "coupon rate 3.50%", ...]
  │     └─> How BM25 works: Tokenizes ENTIRE query ("what", "is", "the", "coupon", "rate", "of", "tranche", "a-1")
  │         • Rare terms ("tranche", "a-1") get high weights (high IDF)
  │         • Common terms ("what", "is", "the") get low weights (low IDF)
  │         • No keyword extraction needed - uses ALL query words automatically
  │
  ├─> Reciprocal Rank Fusion (RRF)
  │     └─> Merge: chunk with both "Tranche A-1" AND tranche concept → Top rank
  │
  └─> Cross-Encoder Reranking
        └─> Score (query, chunk) pairs → Return top 15
```

**Why hybrid (not just semantic)?**

| Approach | Specific Facts | Conceptual Understanding |
|----------|----------------|--------------------------|
| Semantic only | ❌ Misses exact terms | ✅ Good |
| Keyword only | ✅ Good | ❌ Misses synonyms |
| **Hybrid** | **✅ Excellent** | **✅ Excellent** |

**Why RRF (not simple score averaging)?**
- ✅ **Scale-agnostic**: Cosine similarity (0-1) vs BM25 (0-15) → incompatible scales
- ✅ **Rank-based**: RRF = 1/(k + rank_semantic) + 1/(k + rank_keyword)
- ✅ **Robust**: Less sensitive to outlier scores

**Why reranking?**
- ✅ **Cross-encoder** sees query + chunk together (more accurate than bi-encoder)
- ✅ **Final precision**: 40 candidates → rerank → 15 best
- ❌ **Slower**: Can't use for initial retrieval (too slow for 500+ chunks)

**Step 3: Metadata Filtering** (Optional)

```python
if query_has_specific_entity("Tranche A-1"):
    filter = {'has_table': True}  # Only search table chunks
```

**Result**: 10x faster (search 50 table chunks instead of 500 total)

**Step 4: Handling Insufficient Retrieval Results**

**Q: What if the first retrieval doesn't answer the question?**

The agent uses **multi-turn iterative retrieval** via the ReAct pattern:

```
User: "Compare the credit enhancement for A-1 and B-1 tranches"

Turn 1: Agent calls retrieve_relevant_chunks("credit enhancement mechanisms")
        → Gets general credit enhancement explanation

Turn 2: Agent evaluates: "I have general info, but need A-1 specifics"
        Agent calls retrieve_relevant_chunks("Tranche A-1 subordination overcollateralization")
        → Gets A-1 specific credit enhancement details

Turn 3: Agent evaluates: "Now need B-1 details"
        Agent calls retrieve_relevant_chunks("Tranche B-1 subordination credit support")
        → Gets B-1 specific details

Turn 4: Agent synthesizes all 3 retrievals
        → Provides comprehensive comparison with citations
```

**How it works:**
1. ✅ **Agent autonomously decides** when retrieval is sufficient (via ReAct reasoning)
2. ✅ **Query reformulation**: Agent refines queries based on what's missing
3. ✅ **Multi-hop reasoning**: Can chain multiple retrievals for complex questions
4. ✅ **Graceful failure**: After 2-3 attempts, agent asks user for clarification

**Why this approach?**
- **Flexible**: Agent stops when it has enough information (not fixed iterations)
- **Efficient**: Only retrieves what's needed (no redundant searches)
- **Transparent**: User sees the reasoning process in agent's responses

**Alternative not implemented**: Explicit iterative refinement loop
- Would be redundant with LangGraph's ReAct pattern
- Agent already has this capability built-in
- Adding another loop increases complexity without benefit

---

### 4. **Agent Architecture** (LangGraph ReAct Pattern)

#### **Why LangGraph over LangChain?**

**Decision**: Use LangGraph for agent orchestration

| Feature | LangChain | LangGraph |
|---------|-----------|-----------|
| Control flow | Sequential | Graph-based |
| State management | Per-call | Persistent |
| Debugging | Hard | Visualizable |
| Checkpointing | Manual | Built-in |

**Key benefit**: **Persistent state** via PostgresSaver

#### **Query Agent Architecture**

```
START
  │
  ▼
┌─────────────────┐
│  Agent Node     │ ← LLM reasons about what to do
│  (GPT-4)        │
└────────┬────────┘
         │
    [Has tool calls?]
         │
    ┌────┴────┐
    │         │
   YES       NO (final answer)
    │         │
    ▼         ▼
┌─────────┐  END
│Tool Node│
│- retrieve│
│- classify│
└────┬────┘
     │
     └─> Loop back to Agent
```

**Why ReAct (not Chain-of-Thought)?**
- ✅ **Tool use**: Can call retrieval tools
- ✅ **Flexible**: Decides when to search vs. use memory
- ✅ **Observable**: Can trace reasoning + actions

#### **Conversation Memory System**

**Design**: Hybrid retrieval for chat history

```python
# Retrieve relevant past messages
def search_relevant_conversation_history(thread_id, current_query):
    # 1. Semantic search
    similar_messages = embed_and_search(current_query, top_k=3)

    # 2. Recency bias
    recent_messages = get_last_n_messages(n=4)

    # 3. Merge and deduplicate
    return merge(similar_messages, recent_messages)
```

**Why semantic search over full history?**
- ✅ **Scalability**: 100-message conversation → only load 5-7 relevant
- ✅ **Context efficiency**: LLM sees only relevant past exchanges
- ✅ **User experience**: "What did you say about risks earlier?" → finds it

**Example**:
```
Turn 1: "What tranches are in this deal?"
        → Agent retrieves sections, answers

Turn 15: "What were those tranche names again?"
         → Semantic search finds Turn 1 (similarity: 0.89)
         → Agent: "As I mentioned earlier, this deal has..."
         → NO tool calls needed! Uses memory.
```

**Why PostgreSQL checkpointing?**
- ✅ **Persistence**: Conversation survives server restart
- ✅ **Multi-session**: User can leave and return
- ✅ **Thread-based**: One thread per (user, prospectus) pair
- ❌ **Slower than Redis**: Acceptable for our use case

---

### 5. **Database Design**

#### **Why PostgreSQL with pgvector?**

**Decision**: Single PostgreSQL database (not separate vector DB)

| Approach | Pros | Cons |
|----------|------|------|
| Separate vector DB (Pinecone) | ✅ Optimized for vectors | ❌ Data sync issues<br>❌ Extra cost<br>❌ Complex setup |
| **PostgreSQL + pgvector** | **✅ ACID transactions<br>✅ One database<br>✅ SQL joins<br>✅ Metadata filtering** | **❌ Not as fast (acceptable)** |

**Key Schema Decisions**:

```sql
-- ProspectusChunk
CREATE TABLE prospectus_chunk (
    chunk_id UUID PRIMARY KEY,
    prospectus_id UUID REFERENCES prospectus(prospectus_id),
    chunk_text TEXT,                -- The actual content
    chunk_index INTEGER,             -- Position in document
    embedding VECTOR(1536),          -- pgvector type
    metadata JSONB,                  -- Flexible metadata
    UNIQUE (prospectus_id, chunk_index)
);

CREATE INDEX ON prospectus_chunk USING hnsw (embedding vector_cosine_ops);
```

**Why JSONB metadata (not separate columns)?**
- ✅ **Flexibility**: Can add fields without migration
- ✅ **Querying**: PostgreSQL JSONB supports indexing
- Example: `WHERE metadata->>'has_table' = 'true'`

**Why HNSW index?**
- ✅ **Fast**: ~95% recall with 10x speedup
- ✅ **Good for <1M vectors**: Our case (500-1000 chunks/prospectus)
- ❌ **Alternative (IVFFlat)**: Better for >10M vectors (overkill for us)

---

### 6. **Key Design Trade-offs**

#### **Accuracy vs. Speed**

**Choice**: Optimize for accuracy

| Component | Fast Option | Balanced Option (Chosen) | Rationale |
|-----------|-------------|--------------------------|-----------|
| Parsing | OCR only | Unstructured.io + Vision for tables | 80% cost savings, same accuracy |
| Retrieval | Vector-only | Hybrid + reranking | Can't miss specific values |
| Chunking | Fixed sentences | Paragraph-aware | Preserves context |

**Acceptable latencies**:
- Parsing: 1-2 minutes (async, one-time)
- Query: ~1-2 seconds (hybrid search + reranking)

#### **Simplicity vs. Features**

**Recent simplification**: Removed query sub-classification

**Original**:
```
Query → Classify as general/specific
      → Sub-classify as specific_fact/general_overview/comparison
      → Set parameters
```

**Simplified**:
```
Query → Classify as general/specific
      → Use balanced hybrid search (works for both!)
```

**Why?**
- ✅ **Simpler**: One less LLM call
- ✅ **Faster**: 30% faster (700ms vs 1000ms)
- ✅ **Same quality**: Hybrid search adapts automatically
- ✅ **Easier to maintain**: Fewer edge cases

#### **Monolith vs. Microservices**

**Choice**: Django monolith (for now)

**Rationale**:
- ✅ **Simpler deployment**: One backend server
- ✅ **Easier development**: Shared Django ORM
- ✅ **Sufficient scale**: Can handle 100s of users
- 🔮 **Future**: Can split parsing agent to separate service if needed

---

### 7. **Frontend Architecture**

**Stack**: Next.js 15 + TypeScript + Tailwind

**Key Features**:
- **Server-Sent Events (SSE)** for streaming responses
- **Status polling** for background parsing progress
- **Session management** via custom header

**Why SSE (not WebSockets)?**
- ✅ **Simpler**: HTTP-based, works with Django easily
- ✅ **One-directional**: We only stream backend → frontend
- ✅ **Auto-reconnect**: Browser handles reconnection
- ❌ **WebSockets**: Overkill for our use case

---

## Design Principles

### 1. **Domain-Driven Design**

```
Financial documents have unique requirements:
- Tables with precise numbers → Hybrid search with keyword matching
- Complex structure → Vision-based parsing
- Compliance/audit → All data versioned in PostgreSQL
```

### 2. **Progressive Enhancement**

```
V1: ToC-based retrieval (simple, works)
V2: Added chunking + hybrid search (better accuracy)
V3: Added reranking (precision boost)
Next: Fine-tuned embeddings on CMO docs
```

### 3. **Separation of Concerns**

```
Layer 1: API (session, auth, endpoints)
Layer 2: Agents (reasoning, tool orchestration)
Layer 3: RAG (retrieval, chunking, search)
Layer 4: Storage (PostgreSQL, pgvector)
```

Each layer can be tested, swapped, or scaled independently.

---

## Metrics & Results

### Performance
- **Parsing**: 1-2 min for 200-page prospectus (Unstructured.io + Vision for tables only)
- **Query latency**: ~1s (hybrid search + reranking)
- **Accuracy**: 85%+ on specific fact queries (tested manually)

### Scale
- **Documents**: Tested with 10 prospectuses (100-250 pages each)
- **Chunks per doc**: 300-800
- **Total chunks**: ~5,000 (well within pgvector limits)
- **Conversations**: 100+ user sessions tested

### Costs (per document)
- **Parsing**: $0.30-0.80 (vision API for ~20-30% of pages with tables)
- **Embeddings**: $0.002 (one-time)
- **Queries**: $0.01-0.02 per query (LLM + embeddings)

---

## Lessons Learned

### What Worked Well
1. ✅ **Hybrid parsing** - Best of both worlds (cost + accuracy)
2. ✅ **Hybrid search** - Handles both specific and general queries
3. ✅ **pgvector** - Simpler than separate vector DB
4. ✅ **LangGraph** - Persistent state is game-changer
5. ✅ **Semantic memory** - Users love contextual responses

### What I'd Change
1. ⚠️ **Chunking strategy**: Consider hierarchical chunking (multiple granularities)
2. ⚠️ **Caching**: Add Redis for frequent queries
3. ⚠️ **Async parsing**: Use Celery for better job management
4. ⚠️ **Eval framework**: Need automated accuracy metrics (not just manual)

---

## Follow-up Questions You Might Get

### "How would you scale this to 1000 users?"

1. **Horizontal scaling**: Backend is stateless (checkpoints in DB)
2. **Caching**: Redis for session data, frequent query results
3. **CDN**: Static frontend assets
4. **Database**: Connection pooling, read replicas for heavy reads
5. **Async parsing**: Celery workers for document processing

### "How do you ensure accuracy for financial data?"

1. **Hybrid search**: Keyword matching ensures exact terms found
2. **Citation**: Agent always cites page numbers
3. **Grounding**: Instruction to say "I don't know" if not in chunks
4. **Verification**: Show retrieved chunks to user (optional UI feature)
5. **Audit trail**: All messages logged in database

### "Why not use RAG frameworks like LlamaIndex?"

- ✅ **Control**: Custom chunking (paragraph-aware, table handling)
- ✅ **Flexibility**: Hybrid search algorithm (RRF weights tunable)
- ✅ **Integration**: Works seamlessly with LangGraph agents
- ❌ **LlamaIndex**: More opinionated, harder to customize for our domain

### "How does keyword search work if the user query is a full sentence?"

"BM25 tokenizes the **entire query** - no keyword extraction needed. For example:
- Query: 'What is the coupon rate of Tranche A-1?'
- Tokenized: ['what', 'is', 'the', 'coupon', 'rate', 'of', 'tranche', 'a-1']
- BM25 automatically:
  - Weights rare terms like 'tranche' and 'a-1' **higher** (high IDF score)
  - Weights common words like 'what', 'is', 'the' **lower** (low IDF score)
- This is built into the BM25 algorithm using TF-IDF principles - no preprocessing required."

### "What if the first retrieval doesn't answer the question?"

"The agent uses **multi-turn iterative retrieval** via the ReAct pattern:
1. Agent calls `retrieve_relevant_chunks()` with initial query
2. Evaluates if results are sufficient to answer the question
3. If insufficient: reformulates query and calls again
4. Repeats until answer found or asks user for clarification

**Example:**
- User: 'Compare credit enhancement for A-1 and B-1'
- Turn 1: retrieve_relevant_chunks('credit enhancement') → general info
- Turn 2: retrieve_relevant_chunks('Tranche A-1 subordination') → A-1 specifics
- Turn 3: retrieve_relevant_chunks('Tranche B-1 subordination') → B-1 specifics
- Turn 4: Agent synthesizes all 3 retrievals into comprehensive answer

This happens naturally in the LangGraph ReAct loop - no explicit iteration mechanism needed."

---

## Summary (Elevator Pitch)

"I built a production RAG system for financial document analysis with three key innovations:

1. **Hybrid parsing** (Unstructured.io + GPT-4 Vision) that balances cost with accuracy - Vision only for table-heavy pages
2. **Hybrid search** (semantic + keyword + reranking) for both precision and recall
3. **Semantic memory** that makes conversations feel continuous

The system is built on Django + LangGraph + PostgreSQL with pgvector, prioritizing **accuracy over speed** for financial use cases. It's currently processing 100-200 page prospectuses with 85%+ accuracy on fact retrieval and sub-2-second query latency."

**Key differentiator**: The hybrid search with reranking handles the unique challenge of CMO documents - users ask both specific questions ("what is the coupon rate?") and general ones ("explain the structure") - and our system adapts automatically.
