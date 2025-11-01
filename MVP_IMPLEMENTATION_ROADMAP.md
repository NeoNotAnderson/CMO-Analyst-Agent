# CMO Analyst Agent - MVP Implementation Roadmap

## Architecture Overview

**Two-Agent System**:
1. **Parsing Agent** - Extracts and classifies sections from PDF (runs automatically on upload)
2. **Query Agent** - Answers questions and generates TrancheSpeak scripts

**Implementation**: LangGraph's `create_react_agent` for both agents

---

## Phase 1: Foundation Setup (Days 1-2)

### Step 1.1: Django Project Initialization
**Objective**: Get Django running with PostgreSQL

**Tasks**:
- [ ] Create `backend/config/settings.py`
- [ ] Create `backend/manage.py`
- [ ] Configure PostgreSQL database
- [ ] Set up `.env` for secrets
- [ ] Create initial migrations
- [ ] Test Django admin

**Files to create**:
```
backend/
├── manage.py
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── .env
```

**Validation**: `python manage.py runserver` works

---

### Step 1.2: Database Models
**Objective**: Set up database schema

**Tasks**:
- [ ] Review `backend/core/models.py` (needs to be recreated)
- [ ] Create migrations: `python manage.py makemigrations`
- [ ] Apply migrations: `python manage.py migrate`
- [ ] Create superuser for admin access
- [ ] Test models in Django shell

**Validation**: Can create/read Prospectus and SectionMapping in admin

---

## Phase 2: Parsing Agent (Days 3-5)

### Step 2.1: Parsing Tools Implementation
**File**: `backend/agents/parsing_tools.py`

**Tools to implement** (in order of priority):

#### Priority 1 - Core Tools:
1. **`extract_pdf_text`**
   - Use Unstructured.io Python SDK
   - Handle page ranges
   - Return formatted text

2. **`save_section_to_database`**
   - Create SectionMapping instance
   - Save to PostgreSQL
   - Return confirmation

3. **`get_parsing_progress`**
   - Query existing sections
   - Compare to required types
   - Return status

#### Priority 2 - Intelligence Tools:
4. **`search_text_pattern`**
   - Regex search in text
   - Return matches with context

5. **`identify_section_boundaries`**
   - Use LLM to find section breaks
   - Return section ranges

6. **`classify_section_type`**
   - Use LLM with structured output
   - Match to SectionType enum
   - Return classification with confidence

#### Priority 3 - Advanced:
7. **`extract_table`**
   - Use Unstructured.io table detection
   - Parse table structure
   - Return as JSON/dict

**Implementation Pattern** (example):
```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from unstructured.partition.pdf import partition_pdf
from core.models import SectionMapping, Prospectus

@tool
def extract_pdf_text(file_path: str, page_start: int = None, page_end: int = None) -> str:
    """
    Extract text from PDF using Unstructured.io.

    Args:
        file_path: Path to PDF file
        page_start: Starting page (optional)
        page_end: Ending page (optional)

    Returns:
        str: Extracted text
    """
    # TODO: Implement using Unstructured.io
    # elements = partition_pdf(filename=file_path)
    # TODO: Filter by page range if provided
    # TODO: Join elements into text
    # TODO: Return formatted text
    pass

@tool
def save_section_to_database(
    prospectus_id: str,
    section_type: str,
    section_title: str,
    content: str,
    page_numbers: list,
    metadata: dict = None
) -> str:
    """Save extracted section to database."""
    # TODO: Get prospectus instance
    # TODO: Create SectionMapping
    # TODO: Save to database
    # TODO: Return success message with section_id
    pass

# ... implement other tools
```

**Validation**: Each tool works independently when called directly

---

### Step 2.2: Parsing Agent Graph
**File**: `backend/agents/parsing_agent.py`

**Tasks**:
- [ ] Import all parsing tools
- [ ] Define system prompt for parsing behavior
- [ ] Create agent using `create_react_agent`
- [ ] Test agent with sample PDF

**Implementation**:
```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from .parsing_tools import (
    extract_pdf_text,
    search_text_pattern,
    extract_table,
    identify_section_boundaries,
    classify_section_type,
    save_section_to_database,
    get_parsing_progress
)

PARSING_SYSTEM_PROMPT = """You are a CMO prospectus parsing specialist.

Your task is to extract and classify sections from CMO prospectus PDFs.

Required sections to extract:
1. Deal Summary
2. Deal Structure
3. Tranche List
4. Tranche Details
5. Collateral Detail
6. Payment Priority
7. Interest Distribution
8. Principal Distribution
9. Default Loss Distribution
10. Prepayment Penalty
11. Risk Factors

Strategy:
1. Start by extracting full text or finding table of contents
2. Identify section boundaries
3. Extract each section
4. Classify each section type
5. Save to database
6. Check progress and continue until all sections found

Use your tools intelligently - adapt to the document structure!
"""

def create_parsing_agent():
    """
    Create parsing agent using LangGraph.

    Returns:
        Compiled agent graph
    """
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4o",  # TODO: Change to gpt-5-nano when available
        temperature=0
    )

    # Define tools
    tools = [
        extract_pdf_text,
        search_text_pattern,
        extract_table,
        identify_section_boundaries,
        classify_section_type,
        save_section_to_database,
        get_parsing_progress
    ]

    # Create agent
    agent = create_react_agent(
        llm,
        tools,
        state_modifier=SystemMessage(content=PARSING_SYSTEM_PROMPT)
    )

    return agent


def parse_prospectus(prospectus_id: str, file_path: str) -> dict:
    """
    Parse a prospectus using the parsing agent.

    Args:
        prospectus_id: UUID of prospectus in database
        file_path: Path to PDF file

    Returns:
        dict: Parsing results with sections extracted
    """
    agent = create_parsing_agent()

    # Invoke agent
    result = agent.invoke({
        "messages": [
            f"Parse this prospectus at {file_path} for prospectus_id {prospectus_id}. "
            f"Extract all required sections and save them to the database."
        ]
    })

    # TODO: Process result
    # TODO: Update Prospectus status to PARSED
    # TODO: Return summary
    pass
```

**Validation**: Agent can parse sample PDF and save sections

---

## Phase 3: Query Agent (Days 6-8)

### Step 3.1: Query Tools Implementation
**File**: `backend/agents/query_tools.py`

**Tools to implement**:

1. **`search_sections`**
   - Query SectionMapping by type/content
   - Return relevant sections

2. **`get_tranche_list`**
   - Get tranche_list section
   - Parse and format

3. **`get_tranche_details`**
   - Search for specific tranche
   - Return details

4. **`get_payment_priority`**
   - Get payment_priority section
   - Return waterfall structure

5. **`get_collateral_details`**
   - Get collateral_detail section
   - Return formatted info

6. **`generate_tranche_script`** (Phase 4)
   - Use structured output
   - Generate TrancheSpeak

**Example**:
```python
from langchain_core.tools import tool
from core.models import SectionMapping, Prospectus

@tool
def search_sections(
    prospectus_id: str,
    section_type: str = None,
    query: str = None
) -> str:
    """
    Search for sections in the prospectus.

    Args:
        prospectus_id: UUID of prospectus
        section_type: Filter by section type
        query: Text search query

    Returns:
        str: Matching sections with content
    """
    # TODO: Query SectionMapping
    # TODO: Filter by section_type if provided
    # TODO: Search content if query provided
    # TODO: Format and return results
    pass

@tool
def get_tranche_list(prospectus_id: str) -> str:
    """Get complete list of all tranches."""
    # TODO: Query for tranche_list and tranche_details sections
    # TODO: Parse tranche information
    # TODO: Return formatted list
    pass

# ... implement other tools
```

---

### Step 3.2: Query Agent Graph
**File**: `backend/agents/query_agent.py`

**Tasks**:
- [ ] Import query tools
- [ ] Define system prompt
- [ ] Create agent with `create_react_agent`
- [ ] Test with sample questions

**Implementation**:
```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from .query_tools import (
    search_sections,
    get_tranche_list,
    get_tranche_details,
    get_payment_priority,
    get_collateral_details,
    generate_tranche_script
)

QUERY_SYSTEM_PROMPT = """You are a CMO analyst assistant.

Your role is to help users understand CMO prospectus documents and generate TrancheSpeak scripts.

Guidelines:
1. Always use tools to get information - don't make things up
2. For complex questions, break them down and use multiple tools
3. Explain technical CMO terms clearly
4. Cite which sections you're using
5. When generating scripts, ensure all fields are accurate

Available information from the prospectus database:
- Deal summary and structure
- Tranche details (interest rates, types, etc.)
- Payment priority (waterfall)
- Collateral information
- Risk factors

Be helpful, accurate, and thorough!
"""

def create_query_agent():
    """Create query agent using LangGraph."""
    llm = ChatOpenAI(
        model="gpt-4o",  # TODO: Change to gpt-5-nano
        temperature=0
    )

    tools = [
        search_sections,
        get_tranche_list,
        get_tranche_details,
        get_payment_priority,
        get_collateral_details,
        generate_tranche_script
    ]

    agent = create_react_agent(
        llm,
        tools,
        state_modifier=SystemMessage(content=QUERY_SYSTEM_PROMPT)
    )

    return agent


def query_prospectus(prospectus_id: str, user_message: str, conversation_history: list = None) -> dict:
    """
    Query the prospectus using the agent.

    Args:
        prospectus_id: UUID of prospectus
        user_message: User's question
        conversation_history: Previous messages (optional)

    Returns:
        dict: Agent response with answer
    """
    agent = create_query_agent()

    # Build messages
    messages = conversation_history or []
    messages.append({
        "role": "user",
        "content": f"[Prospectus ID: {prospectus_id}] {user_message}"
    })

    # Invoke agent
    result = agent.invoke({"messages": messages})

    # TODO: Extract response
    # TODO: Return formatted answer
    pass
```

---

## Phase 4: API Integration (Days 9-10)

### Step 4.1: Prospectus Upload Endpoint
**File**: `backend/api/views.py` - Update `ProspectusViewSet.create()`

**Tasks**:
- [ ] Handle file upload
- [ ] Save to storage
- [ ] Create Prospectus record
- [ ] Trigger Parsing Agent asynchronously
- [ ] Return prospectus info

**Implementation**:
```python
from rest_framework import viewsets, status
from rest_framework.response import Response
from core.models import Prospectus
from agents.parsing_agent import parse_prospectus
import threading

class ProspectusViewSet(viewsets.ModelViewSet):
    queryset = Prospectus.objects.all()
    serializer_class = ProspectusSerializer

    def create(self, request, *args, **kwargs):
        """
        Upload and parse prospectus.

        Flow:
        1. Save uploaded PDF
        2. Create Prospectus record
        3. Trigger parsing agent async
        4. Return prospectus info
        """
        # TODO: Validate file upload
        uploaded_file = request.FILES.get('file')

        # TODO: Save file to storage
        # prospectus = Prospectus.objects.create(...)

        # TODO: Trigger parsing agent in background
        # thread = threading.Thread(
        #     target=parse_prospectus,
        #     args=(str(prospectus.id), file_path)
        # )
        # thread.start()

        # TODO: Return response
        # return Response(serializer.data, status=201)
        pass
```

---

### Step 4.2: Chat Endpoint
**File**: `backend/api/views.py` - Update `ConversationViewSet.chat()`

**Tasks**:
- [ ] Get conversation and prospectus
- [ ] Validate prospectus is parsed
- [ ] Get conversation history
- [ ] Invoke Query Agent
- [ ] Save messages
- [ ] Return response

**Implementation**:
```python
@action(detail=True, methods=['post'])
def chat(self, request, pk=None):
    """
    Send message to agent and get response.

    Flow:
    1. Get conversation and validate
    2. Save user message
    3. Get conversation history
    4. Invoke query agent
    5. Save agent response
    6. Return to user
    """
    # TODO: Get conversation
    # conversation = self.get_object()

    # TODO: Validate prospectus is parsed
    # if conversation.prospectus.processing_status != 'parsed':
    #     return Response({"error": "Prospectus not parsed yet"}, status=400)

    # TODO: Save user message
    # user_message = Message.objects.create(...)

    # TODO: Get conversation history
    # history = conversation.messages.all()

    # TODO: Invoke agent
    # from agents.query_agent import query_prospectus
    # result = query_prospectus(
    #     prospectus_id=str(conversation.prospectus.id),
    #     user_message=request.data['message'],
    #     conversation_history=history
    # )

    # TODO: Save assistant message
    # assistant_message = Message.objects.create(...)

    # TODO: Return response
    pass
```

---

## Phase 5: TrancheSpeak Generation (Days 11-13)

### Step 5.1: Structured Output Schema
**File**: `backend/agents/schemas.py`

**Tasks**:
- [ ] Define Pydantic models for TrancheSpeak structure
- [ ] Match TrancheSpeak sample format
- [ ] Add validation rules

**Example**:
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class TrancheInfo(BaseModel):
    """Individual tranche information."""
    name: str = Field(description="Tranche name (e.g., A9A, A6X)")
    pct: float = Field(description="Percentage of deal")
    amt: float = Field(description="Tranche amount")
    desc: str = Field(description="Description (SRSPT, SUPRSR, etc.)")
    prin_type: str = Field(description="Principal type: REG, NTL")
    cpn_type: str = Field(description="Coupon type: VAR, FLT, INV, FIX")
    cpn: float = Field(description="Coupon rate")
    delay: int = Field(description="Payment delay in days")
    group_name: Optional[str] = None
    # Add more fields as needed

class TrancheScriptStructure(BaseModel):
    """Complete TrancheSpeak script structure."""
    # Options
    tranche_speak_mode: str = "SRJR"
    collateral_mode: str = "ENHANCED"
    source: str
    country: str = "USA"

    # Deal info
    dated_date: str = Field(description="YYYYMMDD format")
    first_paydate: str
    settle_date: str
    delay: int
    freq: int = 12
    deal_type: str = "CMO"
    currency: str = "USD"

    # Tranches
    tranches: List[TrancheInfo]

    def to_tranchespeak(self) -> str:
        """Convert to TrancheSpeak format."""
        # TODO: Format as TrancheSpeak text
        pass
```

---

### Step 5.2: Implement `generate_tranche_script` Tool
**File**: `backend/agents/query_tools.py`

**Tasks**:
- [ ] Get all required sections
- [ ] Use LLM with structured output
- [ ] Convert to TrancheSpeak format
- [ ] Validate syntax
- [ ] Save to database

**Implementation**:
```python
from langchain_openai import ChatOpenAI
from .schemas import TrancheScriptStructure

@tool
def generate_tranche_script(prospectus_id: str) -> str:
    """
    Generate TrancheSpeak script from prospectus.

    This is a complex operation that:
    1. Retrieves all necessary sections
    2. Uses LLM with structured output to extract data
    3. Formats as TrancheSpeak
    4. Validates and saves
    """
    # TODO: Get all sections needed
    # sections = SectionMapping.objects.filter(prospectus_id=prospectus_id)

    # TODO: Build context from sections
    # context = "\n\n".join([f"## {s.section_type}\n{s.content}" for s in sections])

    # TODO: Use LLM with structured output
    # llm = ChatOpenAI(model="gpt-4o")
    # structured_llm = llm.with_structured_output(TrancheScriptStructure)
    # result = structured_llm.invoke(
    #     f"Extract TrancheSpeak information from:\n{context}"
    # )

    # TODO: Convert to TrancheSpeak format
    # script_text = result.to_tranchespeak()

    # TODO: Save to database
    # TrancheScript.objects.create(
    #     prospectus_id=prospectus_id,
    #     script_content=script_text,
    #     generation_status='completed'
    # )

    # TODO: Return script
    pass
```

---

## Phase 6: Testing & Validation (Days 14-15)

### Step 6.1: Test Parsing Agent
**Test**: `backend/tests/test_parsing_agent.py`

**Scenarios**:
- [ ] Parse sample prospectus (Prospectus_JPM03.A1.pdf)
- [ ] Verify all sections extracted
- [ ] Check classifications are correct
- [ ] Validate database records

---

### Step 6.2: Test Query Agent
**Test**: `backend/tests/test_query_agent.py`

**Scenarios**:
- [ ] Ask about tranche details
- [ ] Ask about payment priority
- [ ] Request script generation
- [ ] Verify agent uses correct tools

---

### Step 6.3: End-to-End Test
**Test**: Full user workflow

1. Upload prospectus via API
2. Wait for parsing to complete
3. Create conversation
4. Ask various questions
5. Request TrancheSpeak script
6. Verify script matches expected format

---

## MVP Success Criteria

### Must Work:
- ✅ Upload PDF prospectus
- ✅ Parsing agent extracts key sections automatically
- ✅ Sections saved to database with correct classification
- ✅ User can ask questions about the deal
- ✅ Agent retrieves and uses correct information
- ✅ Agent can generate basic TrancheSpeak script
- ✅ Script has correct structure (BEGIN/END blocks, key fields)

### Can Defer Post-MVP:
- Streaming responses
- Advanced script validation
- Script editing interface
- User authentication
- Multiple file formats
- Frontend UI (can use API directly for MVP)

---

## File Checklist

### Core Setup:
- [ ] `backend/requirements.txt` ✅
- [ ] `backend/manage.py`
- [ ] `backend/config/settings.py`
- [ ] `backend/config/urls.py`
- [ ] `backend/.env`

### Models & API:
- [ ] `backend/core/models.py` (recreate)
- [ ] `backend/api/serializers.py` (recreate)
- [ ] `backend/api/views.py` (recreate)
- [ ] `backend/api/urls.py` ✅

### Agents:
- [ ] `backend/agents/__init__.py`
- [ ] `backend/agents/parsing_tools.py`
- [ ] `backend/agents/parsing_agent.py`
- [ ] `backend/agents/query_tools.py`
- [ ] `backend/agents/query_agent.py`
- [ ] `backend/agents/schemas.py`

### Tests:
- [ ] `backend/tests/test_parsing_agent.py`
- [ ] `backend/tests/test_query_agent.py`

---

## Daily Progress Tracker

### Day 1-2: Foundation
- [ ] Django setup complete
- [ ] Database running
- [ ] Models migrated
- [ ] Admin working

### Day 3-5: Parsing Agent
- [ ] 7 parsing tools implemented
- [ ] Parsing agent created
- [ ] Sample PDF parsed successfully
- [ ] Sections in database

### Day 6-8: Query Agent
- [ ] 6 query tools implemented
- [ ] Query agent created
- [ ] Can answer questions
- [ ] Agent uses tools correctly

### Day 9-10: API
- [ ] Upload endpoint works
- [ ] Parsing triggered automatically
- [ ] Chat endpoint works
- [ ] Messages saved

### Day 11-13: Scripts
- [ ] Schema defined
- [ ] Script generation works
- [ ] Basic validation
- [ ] Matches TrancheSpeak format

### Day 14-15: Testing
- [ ] All tests pass
- [ ] E2E workflow works
- [ ] MVP complete! 🎉

---

## Next Step

Ready to start **Day 1: Django Setup**?

I'll create the skeleton code for:
1. `manage.py`
2. `config/settings.py`
3. Database configuration
4. Initial project structure

Should I proceed?
