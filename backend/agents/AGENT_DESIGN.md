# CMO Analyst Agent - Design & Workflow

## Overview

This project implements two specialized LangGraph agents to parse CMO prospectuses and answer user queries.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CMO Analyst System                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  Parsing Agent   │         │   Query Agent    │          │
│  │                  │         │                  │          │
│  │  • Parse PDF     │         │  • Analyze Query │          │
│  │  • Classify      │         │  • Retrieve Data │          │
│  │  • Build Tree    │         │  • Generate      │          │
│  │  • Store DB      │         │    Response      │          │
│  └────────┬─────────┘         └────────┬─────────┘          │
│           │                            │                     │
│           └────────────┬───────────────┘                     │
│                        │                                     │
│                   ┌────▼────┐                                │
│                   │   DB    │                                │
│                   │ Models  │                                │
│                   └─────────┘                                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent 1: Parsing Agent

### Purpose
Convert uploaded CMO prospectus PDFs into structured, queryable data stored in PostgreSQL.

### Design Choices

**Why LangGraph?**
- Complex multi-step workflow with conditional branching
- Built-in state management across parsing steps
- Easy error handling and retry logic
- Can pause/resume parsing for long documents

**Why Separate Parsing Agent?**
- Single responsibility: only handles document processing
- Can run asynchronously (user doesn't wait for parsing)
- Easier to test and debug parsing logic independently
- Scalable: can process multiple prospectuses in parallel

### Workflow

```
START
  │
  ▼
┌─────────────────────┐
│ 1. Parse Prospectus │  Use Unstructured.io to extract text,
│    (parse_pdf)      │  tables, and structure from PDF
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Classify         │  LLM identifies section types:
│    Sections         │  - Deal Summary
│    (classify)       │  - Tranche List
└──────────┬──────────┘  - Payment Priority, etc.
           │
           ▼
┌─────────────────────┐
│ 3. Build Hierarchy  │  Create parent-child relationships
│    (build_tree)     │  for sections/subsections
└──────────┬──────────┘  Set level and order
           │
           ▼
┌─────────────────────┐
│ 4. Store in DB      │  Save to ProspectusSection table
│    (store)          │  with hierarchical structure
└──────────┬──────────┘
           │
           ▼
          END
     (Success)

  (At any step, if error → error_handler_node)
```

### State Flow

```python
ParsingState = {
    'prospectus_id': 'uuid-123',
    'prospectus_file_path': '/path/to/file.pdf',
    'parsed_pages': [...],           # Output of step 1
    'section_map': {...},             # Output of step 2
    'sections': [...],                # Output of step 3
    'current_step': 'storing',        # Progress tracker
    'errors': [],
    'metadata': {}
}
```

### Key Design Decisions

1. **Hierarchical Storage**: Use self-referencing `parent` field in ProspectusSection
   - Handles arbitrary nesting depth
   - Different prospectus formats have different structures
   - Easy to query: `section.subsections.all()`

2. **Flexible JSON Fields**: `structured_data` stores parsed content
   - Each agency uses different formats
   - Don't force normalization at storage time
   - LLM normalizes during script generation

3. **Async Processing**: Parsing happens in background
   - Update Prospectus.processing_status as it progresses
   - User can see real-time status updates
   - Doesn't block the UI

---

## Agent 2: Query Agent

### Purpose
Answer user questions about CMO deals and generate TrancheSpeak scripts.

### Design Choices

**Why LangGraph?**
- Conditional routing based on query type
- Tool calling for database retrieval
- Multi-step reasoning for complex queries
- State management for conversation context

**Why Separate Query Agent?**
- Different concerns: retrieval + generation vs parsing
- Can optimize for low-latency responses
- Easier to add features (web search, calculations)
- Can maintain conversation history

### Workflow

```
START (User asks question)
  │
  ▼
┌─────────────────────┐
│ 1. Analyze Query    │  Classify query type:
│    (analyze)        │  - Generic CMO question
└──────────┬──────────┘  - Deal-specific question
           │              - Script generation request
           │
           ▼
      ┌────┴────┐
      │ Router  │  Conditional routing
      └────┬────┘
           │
     ┌─────┼─────┐
     │     │     │
     ▼     ▼     ▼
   Generic Deal  Script
   Answer  Query Generate
     │     │     │
     └─────┼─────┘
           │
           ▼
┌─────────────────────┐
│ 2. Retrieve Context │  Query database for
│    (retrieve)       │  relevant sections
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Generate         │  LLM generates response
│    Response         │  or TrancheSpeak script
│    (generate)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. Format Output    │  Format for user display
│    (format)         │  Add sources/citations
└──────────┬──────────┘
           │
           ▼
          END
     (Return to user)
```

### State Flow

```python
QueryState = {
    'prospectus_id': 'uuid-123',       # Optional
    'user_query': 'What is the coupon rate for Class A?',
    'query_type': 'deal_specific',     # Output of step 1
    'retrieved_context': [...],        # Output of step 2
    'analysis': '...',                 # LLM reasoning
    'response': '...',                 # Final answer
    'should_generate_script': False,
    'script_content': None,
    'errors': [],
    'metadata': {
        'confidence': 0.95,
        'sources': ['section_uuid_1', 'section_uuid_2']
    }
}
```

### Query Types & Routing

**1. Generic CMO Questions**
```
User: "What is credit enhancement?"
→ No prospectus_id needed
→ Use general CMO knowledge
→ Quick response
```

**2. Deal-Specific Questions**
```
User: "What is the payment priority for this deal?"
→ Requires prospectus_id
→ Retrieve relevant sections from DB
→ Extract and summarize info
```

**3. Script Generation**
```
User: "Generate TrancheSpeak script"
→ Requires prospectus_id
→ Retrieve all deal structure sections
→ Use structured output to generate script
→ Validate syntax
→ Store in DealScript table
```

### Key Design Decisions

1. **Context Retrieval**: Query database, not vector store (for MVP)
   - Use section_type to filter relevant sections
   - Can add semantic search later
   - Fast exact matching on structured data

2. **Conditional Routing**: Different paths for different query types
   - Optimizes for each use case
   - Generic queries don't hit database
   - Script generation uses specialized prompts

3. **Structured Output**: Use Pydantic models for script generation
   - Ensures valid TrancheSpeak syntax
   - Type-safe field extraction
   - Easy to validate and store

---

## Data Flow Between Agents

```
User uploads PDF
      │
      ▼
┌─────────────────┐
│ Parsing Agent   │  Async processing
│ (Background)    │
└────────┬────────┘
         │
         ▼  Stores data
    ┌────────┐
    │   DB   │
    └────┬───┘
         │
         ▼  Reads data
┌─────────────────┐
│ Query Agent     │  Real-time responses
│ (Interactive)   │
└─────────────────┘
      │
      ▼
   User gets answer
```

**Key Points:**
- Agents are **decoupled**: don't call each other directly
- Database is the **single source of truth**
- Parsing Agent **writes** data
- Query Agent **reads** data
- Both can run **independently**

---

## Technology Stack

### LangGraph
- **State Management**: Persistent state across nodes
- **Conditional Edges**: Route based on state values
- **Tool Calling**: Integrate with external APIs
- **Error Recovery**: Retry logic and fallbacks

### GPT-5-NANO (or GPT-4)
- **Classification**: Identify section types
- **Extraction**: Pull structured data from text
- **Generation**: Create TrancheSpeak scripts
- **Reasoning**: Answer complex questions

### Unstructured.io
- **PDF Parsing**: Extract text, tables, layout
- **Element Detection**: Identify titles, paragraphs, lists
- **Metadata**: Page numbers, confidence scores

### PostgreSQL + Django ORM
- **Hierarchical Data**: Self-referencing foreign keys
- **JSON Storage**: Flexible structured_data fields
- **Relationships**: Foreign keys between tables
- **Queries**: Django ORM for retrieval

---

## File Structure

```
backend/
├── agents/
│   ├── parsing_agent/
│   │   ├── __init__.py
│   │   ├── state.py          # ParsingState definition
│   │   ├── tools.py          # Parsing tools (@tool decorated)
│   │   ├── nodes.py          # LangGraph nodes (functions)
│   │   └── graph.py          # Graph assembly and compilation
│   │
│   ├── query_agent/
│   │   ├── __init__.py
│   │   ├── state.py          # QueryState definition
│   │   ├── tools.py          # Query/retrieval tools
│   │   ├── nodes.py          # LangGraph nodes
│   │   └── graph.py          # Graph assembly
│   │
│   └── shared/
│       ├── __init__.py
│       ├── prompts.py        # Shared prompt templates
│       └── utils.py          # Shared utility functions
│
├── core/
│   └── models.py             # Django models (database schema)
│
└── api/
    ├── views.py              # API endpoints
    └── serializers.py        # DRF serializers
```

---

## Implementation Steps (MVP)

### Phase 1: Parsing Agent
1. ✅ Define data models (completed)
2. ✅ Create database tables (completed)
3. ⬜ Implement `parse_pdf_with_unstructured` tool
4. ⬜ Implement `classify_sections` node with LLM
5. ⬜ Implement `build_section_hierarchy` logic
6. ⬜ Implement `store_sections_in_db` with Django ORM
7. ⬜ Assemble LangGraph workflow
8. ⬜ Test with sample prospectus

### Phase 2: Query Agent
1. ⬜ Implement `analyze_query_type` classifier
2. ⬜ Implement `retrieve_relevant_sections` from DB
3. ⬜ Implement basic Q&A node
4. ⬜ Implement script generation node
5. ⬜ Assemble LangGraph workflow with routing
6. ⬜ Test with sample queries

### Phase 3: Integration
1. ⬜ Create API endpoints for agents
2. ⬜ Build frontend upload interface
3. ⬜ Build chat interface
4. ⬜ Add conversation history
5. ⬜ Deploy and test end-to-end

---

## Benefits of This Design

### Modularity
- Each agent has clear, single responsibility
- Easy to test components independently
- Can replace/upgrade agents without affecting the other

### Scalability
- Parsing agent can process multiple files in parallel
- Query agent can handle multiple users concurrently
- Database is optimized for read-heavy workload

### Flexibility
- Easy to add new query types (conditional routing)
- Easy to support new prospectus formats (flexible JSON)
- Easy to add new tools (LangGraph tool integration)

### Maintainability
- Clear separation of concerns
- Well-defined state schemas
- Type hints throughout
- Comprehensive docstrings

---

## Next Steps

1. **Start with Parsing Agent**: Get data into database first
2. **Test with one prospectus**: Use JPM03 sample files
3. **Validate database storage**: Check admin interface
4. **Build Query Agent**: Once data is available
5. **Iterate**: Add features based on testing

---

## Questions to Consider

1. **Error Handling**: What happens if PDF parsing fails halfway?
2. **Performance**: How long should parsing take? Set timeouts?
3. **Validation**: Should we validate prospectus format before parsing?
4. **Updates**: If user uploads new version, how to handle?
5. **Caching**: Should we cache LLM responses for common queries?

---

**Remember**: Start with MVP - skeleton code first, implement incrementally, test frequently!
