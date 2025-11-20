# Agents Module

This module contains two LangGraph agents for the CMO Analyst system.

## Structure

```
agents/
├── AGENT_DESIGN.md          # Comprehensive design documentation
├── parsing_agent/           # Agent 1: Parse prospectuses
│   ├── state.py            # State schema (ParsingState)
│   ├── tools.py            # Tools for parsing
│   ├── nodes.py            # LangGraph nodes
│   └── graph.py            # Graph assembly
├── query_agent/             # Agent 2: Answer queries
│   ├── state.py            # State schema (QueryState)
│   ├── tools.py            # Tools for querying
│   ├── nodes.py            # LangGraph nodes
│   └── graph.py            # Graph assembly
└── shared/                  # Shared utilities
    ├── prompts.py          # Prompt templates
    └── utils.py            # Helper functions
```

## Quick Start

### Parsing Agent
```python
from agents.parsing_agent.graph import create_parsing_graph

# Create graph
graph = create_parsing_graph()

# Run parsing
initial_state = {
    'prospectus_id': 'uuid-123',
    'prospectus_file_path': '/path/to/file.pdf',
    # ... other state fields
}
result = graph.invoke(initial_state)
```

### Query Agent
```python
from agents.query_agent.graph import create_query_graph

# Create graph
graph = create_query_graph()

# Run query
initial_state = {
    'prospectus_id': 'uuid-123',
    'user_query': 'What is the coupon rate?',
    # ... other state fields
}
result = graph.invoke(initial_state)
```

## Implementation Status

### ✅ Completed
- Data models created
- Database migrations applied
- Folder structure created
- Skeleton code generated

### ⬜ TODO (You will implement)
- Parsing agent tools
- Parsing agent nodes
- Query agent tools
- Query agent nodes
- Graph assembly
- API integration

## Documentation

See `AGENT_DESIGN.md` for:
- Detailed architecture
- Workflow diagrams
- Design decisions
- Implementation steps
- Data flow explanations

## Development Guidelines

1. **Start with skeleton code** - already created
2. **Implement one node at a time** - test each independently
3. **Use TODO comments** - mark what needs implementation
4. **Test with sample data** - use JPM03 files in parsers/
5. **Refer to AGENT_DESIGN.md** - for workflow understanding

## Testing

Each component should be testable independently:
- Tools can be tested as standalone functions
- Nodes can be tested with mock state
- Graphs can be tested end-to-end

## Next Steps

1. Review `AGENT_DESIGN.md`
2. Start with parsing_agent implementation
3. Test with one sample prospectus
4. Move to query_agent
5. Integrate with API layer
