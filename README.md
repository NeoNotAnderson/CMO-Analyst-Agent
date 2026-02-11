# CMO Analyst Agent

An AI-powered conversational agent for analyzing Collateralized Mortgage Obligation (CMO) prospectuses. The system automates prospectus parsing, provides intelligent question-answering capabilities, and maintains context-aware conversations about deal structures.

## Overview

The CMO Analyst Agent is a full-stack application that combines document processing, semantic search, and LLM-based reasoning to help financial analysts quickly extract and understand information from complex CMO prospectuses. It features a persistent conversational agent that remembers context across sessions and intelligently retrieves relevant information.

## Key Features

### 🤖 Intelligent Conversational Agent
- **LangGraph-based ReAct architecture** with multi-step reasoning and tool orchestration
- **Persistent conversations** with PostgreSQL-backed checkpointing across sessions
- **Semantic memory system** using embedding-based similarity search for context retrieval
- **Context-aware responses** that reference previous exchanges and avoid redundant queries

### 📄 Automated Prospectus Parsing
- **Two-stage parsing pipeline**:
  1. Index extraction to understand document structure
  2. Section-based content parsing with hierarchy preservation
- **Integration with Unstructured.io** for robust PDF processing
- **GPT-4 vision model** for extracting structured data from document pages
- **Automatic section mapping** from table of contents to full text

### 💬 Advanced Query Handling
- **Intelligent query classification**: Distinguishes between general CMO questions and deal-specific queries
- **Hierarchical section retrieval**: Finds relevant sections based on actual prospectus structure
- **Multi-source responses**: Combines information from conversation history and prospectus content
- **Semantic search over 100+ page documents** with efficient chunking and vector similarity

### 🎯 User Experience
- **Real-time streaming responses** with Server-Sent Events (SSE)
- **Session management** supporting multiple concurrent prospectus analyses
- **File upload with drag-and-drop** interface
- **Live status polling** for background parsing operations
- **Prospectus sidebar** for easy document navigation

## Architecture

### Tech Stack

**Backend:**
- **Framework**: Django 5.0 with Django REST Framework
- **Agent Framework**: LangGraph (v0.2+) with LangChain
- **LLM**: GPT-4 (via OpenAI API, configured as "gpt-5-nano")
- **Database**: PostgreSQL 15 with psycopg2
- **Document Processing**: Unstructured.io, pdf2image, Pillow

**Frontend:**
- **Framework**: Next.js 16 with React 19
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS 4
- **HTTP Client**: Axios

**Infrastructure:**
- **Containerization**: Docker Compose
- **Database**: PostgreSQL with persistent volumes

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Chat Page    │  │ Prospectus   │  │ Upload Modal       │   │
│  │              │  │ Sidebar      │  │                    │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ REST API / SSE
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (Django)                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   API Layer (DRF)                         │  │
│  │  - Chat endpoints                                         │  │
│  │  - Prospectus management                                  │  │
│  │  - Session handling                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                LangGraph Agents                           │  │
│  │  ┌────────────────┐          ┌────────────────┐          │  │
│  │  │ Query Agent    │          │ Parsing Agent  │          │  │
│  │  │                │          │                │          │  │
│  │  │ - classify     │          │ - extract idx  │          │  │
│  │  │ - analyze      │          │ - parse pages  │          │  │
│  │  │ - retrieve     │          │ - save to DB   │          │  │
│  │  └────────────────┘          └────────────────┘          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Semantic Memory & Checkpointing              │  │
│  │  - Embedding-based similarity search                      │  │
│  │  - PostgresSaver for state persistence                    │  │
│  │  - Thread-based conversation management                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                           │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐   │
│  │ prospectus     │  │ conversation     │  │ chat_message │   │
│  │                │  │ _thread          │  │              │   │
│  ├────────────────┤  ├──────────────────┤  ├──────────────┤   │
│  │ - parsed_file  │  │ - thread_id      │  │ - role       │   │
│  │ - parsed_index │  │ - user_id        │  │ - content    │   │
│  │ - parse_status │  │ - prospectus_id  │  │ - created_at │   │
│  └────────────────┘  └──────────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema

### Core Models

**Prospectus**
- Stores uploaded CMO prospectus documents
- Fields: `prospectus_id`, `prospectus_name`, `prospectus_file`, `parse_status`, `parsed_file`, `parsed_index`
- Parse statuses: `pending` → `parsing_index` → `parsing_sections` → `completed`

**ConversationThread**
- Tracks conversation threads per (user, prospectus) pair
- Fields: `thread_id`, `user_id`, `prospectus_id`, `created_at`, `updated_at`
- Unique constraint: One thread per user-prospectus combination

**ChatMessage**
- Stores individual messages within conversation threads
- Fields: `message_id`, `thread_id`, `role`, `content`, `created_at`
- Roles: `user`, `assistant`, `system`, `tool`

**AgentCheckpoint**
- Stores LangGraph checkpoints for state persistence
- Fields: `checkpoint_id`, `thread_id`, `checkpoint`, `metadata`, `parent_checkpoint_id`
- Used by LangGraph's PostgresSaver for conversation continuity

## How It Works

### Parsing Flow

1. **Upload**: User uploads a CMO prospectus PDF
2. **Index Extraction**: Parsing agent identifies table of contents pages
3. **Index Parsing**: GPT-4 vision model extracts section titles and page numbers
4. **Section Parsing**: Agent parses each section based on index mapping
5. **Storage**: Structured data saved to `prospectus.parsed_file` in JSON format

```json
{
  "sections": [
    {
      "title": "SUMMARY",
      "level": 1,
      "page_num": 5,
      "text": "This prospectus relates to...",
      "sample_text": "This prospectus relates to...",
      "sections": [
        {
          "title": "The Certificates",
          "level": 2,
          "page_num": 6,
          "text": "The following certificates...",
          "table": {...}
        }
      ]
    }
  ]
}
```

### Query Flow

1. **User Query**: User asks a question in the chat interface
2. **Thread Management**: System retrieves or creates conversation thread
3. **Semantic Search**: Finds relevant past messages using embedding similarity
4. **Agent Reasoning**:
   - Classifies query (general CMO vs. deal-specific)
   - Checks conversation memory for existing answers
   - Analyzes which prospectus sections are relevant
   - Retrieves section content if needed
5. **Response Generation**: Combines memory and prospectus data
6. **Persistence**: Saves user message and assistant response to database

### Semantic Memory System

**Hybrid Retrieval Strategy:**
- **Top-K Semantic**: Retrieves 3 most similar past exchanges using cosine similarity
- **Recent-K**: Always includes 4 most recent messages for context
- **Embedding Model**: OpenAI `text-embedding-ada-002`
- **Similarity Threshold**: 0.7 (configurable)

**Example:**
```
User (Turn 1): "What tranches are in this deal?"
Agent: Retrieves sections, responds with A1, A2, B, Z tranches

User (Turn 10): "What were those tranche names again?"
Semantic Search: Finds Turn 1 (similarity: 0.89)
Agent: "As I mentioned earlier, this deal has A1, A2, B, and Z tranches..."
       (No tool calls needed - uses memory)
```

## Installation

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ and npm
- Python 3.10+
- OpenAI API key

### Quick Start

1. **Clone the repository**
```bash
git clone <repository-url>
cd CMO-Analyst-Agent
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key and other configuration
```

3. **Start PostgreSQL**
```bash
docker-compose up -d
```

4. **Set up backend**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start backend server
python manage.py runserver
```

5. **Set up frontend**
```bash
cd frontend
npm install
npm run dev
```

6. **Access the application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Django Admin: http://localhost:8000/admin

## Configuration

### Environment Variables

**.env (Backend)**
```bash
# Database
DB_NAME=cmo_analyst_db
DB_USER=cmo_user
DB_PASSWORD=cmo_password
DB_HOST=localhost
DB_PORT=5432

# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# OpenAI API
OPENAI_API_KEY=your-openai-api-key

# Unstructured.io (Optional)
UNSTRUCTURED_API_KEY=your-unstructured-api-key
UNSTRUCTURED_API_URL=https://api.unstructured.io

# File Upload
MAX_UPLOAD_SIZE=52428800  # 50MB
MEDIA_ROOT=/var/media
```

### LangGraph Configuration

**Query Agent Tools:**
- `classify_query`: Determines query type (general vs. deal-specific)
- `get_prospectus_status`: Checks parsing status
- `trigger_parsing_agent`: Initiates background parsing
- `analyze_query_sections`: Identifies relevant sections
- `retrieve_sections`: Fetches section content

**Parsing Agent Tools:**
- `check_parse_status`: Verifies current parsing state
- `determine_doc_type`: Identifies prospectus format
- `find_index_pages`: Locates table of contents
- `convert_pages_to_images`: Converts PDF pages to images
- `parse_index_with_openai`: Extracts index structure
- `parse_prospectus_with_parsed_index`: Parses all sections

## API Reference

### Authentication

**Initialize Session**
```http
POST /api/session/init/
Content-Type: application/json

{
  "username": "test_user"
}

Response:
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Session initialized",
  "prospectuses": []
}
```

### Prospectus Management

**Upload Prospectus**
```http
POST /api/prospectus/upload/
Content-Type: multipart/form-data
X-Session-Id: <session_id>

file: <prospectus.pdf>

Response:
{
  "prospectus_id": "660e8400-e29b-41d4-a716-446655440000",
  "prospectus_name": "GSMS_2024-1",
  "status": "pending",
  "message": "Prospectus uploaded successfully"
}
```

**List Prospectuses**
```http
GET /api/prospectus/list/
X-Session-Id: <session_id>

Response:
{
  "prospectuses": [
    {
      "prospectus_id": "660e8400-e29b-41d4-a716-446655440000",
      "prospectus_name": "GSMS_2024-1",
      "parse_status": "completed",
      "upload_date": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Set Active Prospectus**
```http
POST /api/prospectus/select/
Content-Type: application/json
X-Session-Id: <session_id>

{
  "prospectus_id": "660e8400-e29b-41d4-a716-446655440000"
}

Response:
{
  "message": "Active prospectus set",
  "prospectus_id": "660e8400-e29b-41d4-a716-446655440000",
  "prospectus_name": "GSMS_2024-1"
}
```

### Chat Operations

**Send Chat Message (Streaming)**
```http
POST /api/chat/send/
Content-Type: application/json
X-Session-Id: <session_id>

{
  "message": "What tranches are in this deal?"
}

Response (Server-Sent Events):
data: {"type": "token", "content": "This"}
data: {"type": "token", "content": " deal"}
data: {"type": "token", "content": " contains"}
...
data: {"type": "done", "content": "Full response text"}
```

**Get Chat History**
```http
GET /api/chat/history/<prospectus_id>/
X-Session-Id: <session_id>

Response:
{
  "messages": [
    {
      "id": "msg-1",
      "role": "user",
      "content": "What tranches are in this deal?",
      "timestamp": "2024-01-15T10:35:00Z"
    },
    {
      "id": "msg-2",
      "role": "assistant",
      "content": "This deal contains the following tranches...",
      "timestamp": "2024-01-15T10:35:05Z"
    }
  ]
}
```

**Clear Chat History**
```http
DELETE /api/chat/history/<prospectus_id>/clear/
X-Session-Id: <session_id>

Response:
{
  "message": "Chat history cleared successfully"
}
```

## Testing

### Backend Tests
```bash
cd backend
pytest
```

### Manual Testing Scenarios

**Test Case 1: Conversation Continuity**
1. Select a prospectus
2. Ask: "What tranches are in this deal?"
3. Ask: "Tell me more about the A1 tranche"
4. Expected: Agent references previous response without re-retrieving

**Test Case 2: Semantic Memory**
1. Ask several questions about different topics
2. Ask: "What did you say about prepayment risk earlier?"
3. Expected: Agent finds and references relevant earlier exchange

**Test Case 3: Multi-Prospectus Sessions**
1. Select Prospectus A, ask questions
2. Select Prospectus B, ask questions
3. Switch back to Prospectus A
4. Expected: Each prospectus maintains separate conversation history

**Test Case 4: Parsing Status Polling**
1. Upload a new prospectus
2. Watch sidebar during parsing
3. Expected: Status updates automatically (pending → parsing_index → parsing_sections → completed)

## Project Structure

```
CMO-Analyst-Agent/
├── backend/
│   ├── agents/
│   │   ├── parsing_agent/       # Prospectus parsing agent
│   │   │   ├── graph.py         # LangGraph definition
│   │   │   ├── nodes.py         # Agent nodes
│   │   │   ├── state.py         # State schema
│   │   │   └── tools.py         # Parsing tools
│   │   └── query_agent/         # Query answering agent
│   │       ├── checkpoint.py    # PostgresSaver config
│   │       ├── conversation_memory.py  # Semantic search
│   │       ├── graph.py         # LangGraph definition
│   │       ├── nodes.py         # Agent nodes
│   │       ├── prompts.py       # System prompts
│   │       ├── state.py         # State schema
│   │       └── tools.py         # Query tools
│   ├── api/
│   │   ├── serializers.py       # DRF serializers
│   │   ├── urls.py              # API routes
│   │   └── views.py             # API endpoints
│   ├── config/
│   │   ├── settings.py          # Django settings
│   │   └── urls.py              # Root URL config
│   ├── core/
│   │   ├── models.py            # Database models
│   │   └── migrations/          # Database migrations
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── chat/
│   │   │   └── page.tsx         # Main chat page
│   │   ├── layout.tsx           # Root layout
│   │   └── page.tsx             # Landing page
│   ├── components/
│   │   ├── ChatInterface.tsx    # Chat UI component
│   │   ├── ProspectusSidebar.tsx # Prospectus list
│   │   ├── MessageInput.tsx     # Input field
│   │   ├── MessageList.tsx      # Message display
│   │   ├── UploadModal.tsx      # Upload dialog
│   │   └── Header.tsx           # App header
│   ├── hooks/
│   │   └── useProspectusStatusPolling.ts  # Status polling
│   ├── types/
│   │   └── index.ts             # TypeScript types
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## Key Implementation Details

### LangGraph Agent Pattern

Both agents use the **ReAct (Reasoning + Acting)** pattern:

```
START → Agent Node → [Should Continue?]
                          ├─→ Tools → Agent Node (loop)
                          └─→ END
```

**Agent Node**: LLM reasons about state and decides which tools to call
**Tool Node**: Executes tool calls and returns results
**Conditional Edge**: Checks if agent made tool calls (continue) or has final response (end)

### Checkpointing System

**PostgresSaver** from `langgraph-checkpoint-postgres`:
- Saves agent state after each step
- Keyed by `thread_id` (unique per user-prospectus pair)
- Enables conversation continuity across requests
- Supports state branching and rollback

### Semantic Memory Implementation

**Core Function: `search_relevant_conversation_history()`**

```python
def search_relevant_conversation_history(
    thread_id: str,
    current_query: str,
    top_k: int = 3,
    recent_k: int = 4,
    similarity_threshold: float = 0.7
) -> List[Dict]:
    """
    Retrieve semantically relevant past messages.

    Returns:
        List of message dicts with:
        - role, content, timestamp
        - similarity_score (for semantic matches)
        - is_recent (for recent matches)
    """
```

**Workflow:**
1. Embed current query using OpenAI embeddings
2. Embed all past user messages
3. Calculate cosine similarity scores
4. Take top-K similar messages above threshold
5. Always include recent-K latest messages
6. Deduplicate and return combined results

## Troubleshooting

### Common Issues

**Issue: "Prospectus parsing stuck at 'parsing_index'"**
- Check backend logs for OpenAI API errors
- Verify OPENAI_API_KEY is set correctly
- Ensure index pages were correctly identified

**Issue: "Agent not using conversation history"**
- Verify ConversationThread exists for (user, prospectus)
- Check that thread_id is being passed to checkpointer
- Review logs for semantic search results

**Issue: "Database connection errors"**
- Ensure PostgreSQL container is running: `docker-compose ps`
- Check database credentials in .env
- Verify migrations are applied: `python manage.py migrate`

**Issue: "Frontend not receiving SSE stream"**
- Check CORS settings in Django settings
- Verify X-Session-Id header is being sent
- Check browser console for errors

### Debug Logging

Enable verbose logging in [backend/agents/query_agent/graph.py](backend/agents/query_agent/graph.py):

```python
print(f"[CONVERSATION_MEMORY] Retrieved {len(relevant_history)} relevant messages")
print(f"[CONVERSATION_MEMORY] Similarity scores: {[m['similarity_score'] for m in relevant_history]}")
```

## Performance Optimization

### Recommendations

1. **Database Indexes**: Already configured on frequently queried fields
2. **Checkpoint Cleanup**: Implement periodic deletion of old checkpoints
3. **Embedding Cache**: Consider caching embeddings for frequently asked questions
4. **Pagination**: Add pagination for large chat histories
5. **Rate Limiting**: Implement rate limiting on chat endpoints

### Scaling Considerations

- **Horizontal Scaling**: Backend is stateless (except checkpoints in DB)
- **Caching Layer**: Add Redis for session storage
- **Background Tasks**: Use Celery for long-running parsing jobs
- **CDN**: Serve static frontend assets via CDN

## Future Enhancements

- [ ] **TrancheSpeak Script Generation**: Convert parsed data to TrancheSpeak format
- [ ] **Multi-document Comparison**: Compare tranches across multiple prospectuses
- [ ] **Export Functionality**: Export chat history and analysis to PDF/Excel
- [ ] **Advanced Search**: Full-text search across all prospectuses
- [ ] **User Authentication**: JWT-based authentication system
- [ ] **Real-time Collaboration**: Multiple users analyzing same prospectus
- [ ] **Custom Taxonomy**: User-defined section categories

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -m "Add feature"`
4. Push to branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is for educational and research purposes.

## Acknowledgments

- **LangGraph** for agent orchestration framework
- **Unstructured.io** for document processing capabilities
- **OpenAI** for GPT-4 and embedding models
- **Django** and **Next.js** communities for excellent documentation
