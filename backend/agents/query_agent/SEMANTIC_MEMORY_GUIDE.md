# Semantic Conversation Memory Guide

## Overview

This system implements **intelligent conversation memory** using semantic search with embeddings. It solves the problem of growing context windows in long conversations while maintaining context awareness.

## Key Concept

**Storage ≠ Retrieval**

- **Storage**: Complete conversation history saved in `ChatMessage` table (never deleted)
- **Retrieval**: Only semantically relevant past messages loaded into agent context

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  User sends message: "What was the A1 tranche coupon?"  │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  1. search_relevant_conversation_history()              │
│     - Embed current query                               │
│     - Embed all past user messages                      │
│     - Calculate cosine similarity                       │
│     - Retrieve top-k most similar exchanges             │
│     - Always include recent-k messages                  │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  2. format_conversation_context()                       │
│     - Format retrieved messages as context string       │
│     - Add instructions for agent                        │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  3. Build agent messages                                │
│     SystemMessage:                                      │
│       - Base system prompt                              │
│       + "=== RELEVANT PAST CONVERSATION ==="            │
│       + Retrieved exchanges                             │
│     HumanMessage:                                       │
│       - Current user query                              │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  4. Agent processes with selective memory               │
│     - Sees relevant past context                        │
│     - Decides: reference memory OR retrieve new data    │
│     - Formulates response                               │
└─────────────────────────────────────────────────────────┘
```

### Example Workflow

**Conversation in Database** (30 messages total):
```
1. User: "What tranches are in this deal?"
2. Agent: "This deal has A1, A2, B, and Z tranches. A1 coupon is 5.2%..."
3. User: "Tell me about prepayment risk"
4. Agent: "Prepayment risk occurs when..."
5. User: "What's the deal structure?"
6. Agent: "The deal is structured as..."
...
27. User: "Summarize the risk factors"
28. Agent: "The main risks are..."
29. User: "What were those tranche coupons again?" ← NEW MESSAGE
```

**What Agent Receives** (not all 28 messages):
```
SystemMessage:
  [Base prompt]

  === RELEVANT PAST CONVERSATION ===
  (Messages retrieved via semantic search)

  [USER] (similarity: 0.87)
  What tranches are in this deal?

  [ASSISTANT] (similarity: 0.87)
  This deal has A1, A2, B, and Z tranches. A1 coupon is 5.2%...

  [USER] (recent)
  Summarize the risk factors

  [ASSISTANT] (recent)
  The main risks are...

  === END PAST CONVERSATION ===

HumanMessage:
  What were those tranche coupons again?
```

**Agent's Decision**:
- Sees message #2 in context (about tranches and coupons)
- Recognizes answer is already in conversation history
- Responds: "As I mentioned earlier, the A1 tranche has a coupon of 5.2%..."
- **No tool calls needed** - avoids redundant retrieval

## Configuration Parameters

### In `run_agent()`:

```python
relevant_history = search_relevant_conversation_history(
    thread_id=thread_id,
    current_query=user_query,
    top_k=3,      # Number of semantically similar exchanges to retrieve
    recent_k=4    # Number of most recent messages to always include
)
```

### Parameter Tuning:

**top_k** (Semantic Matches):
- **Small (1-2)**: Very selective, only highly similar past exchanges
- **Medium (3-5)**: Balanced, includes moderately related topics
- **Large (7-10)**: More context, but increases token usage

**recent_k** (Recent Context):
- **Small (2-4)**: Only immediate context
- **Medium (4-6)**: Standard conversational flow
- **Large (8-10)**: More recent history, better for complex multi-turn discussions

**Recommended Defaults**:
- `top_k=3`: Good balance for most conversations
- `recent_k=4`: Captures last 2 user-assistant exchanges

## Retrieval Strategy

### Always Included:
1. **Recent messages** (last `recent_k` messages)
   - Provides immediate conversational context
   - Scored as similarity = 1.0

### Selectively Included:
2. **Semantically similar exchanges** (top `top_k` from older messages)
   - User message + following assistant response
   - Ranked by cosine similarity to current query
   - Only from messages older than the recent window

### Deduplication:
- If a message appears in both recent and semantic matches, only included once
- Prevents redundant context

## Embedding Model

**Current**: `text-embedding-3-small`
- **Dimensions**: 1536
- **Cost**: $0.02 / 1M tokens
- **Performance**: Fast, good quality for conversation matching

**Alternative**: `text-embedding-3-large`
- **Dimensions**: 3072
- **Cost**: $0.13 / 1M tokens
- **Performance**: Higher quality, slower

## Agent Decision Making

The system prompt guides the agent through 3 steps:

### Step 1: Check Past Conversation
```
Review "RELEVANT PAST CONVERSATION" section
If question already answered → prepare to reference it
```

### Step 2: Decide on Retrieval
```
IF answer in past conversation:
    → Reference past answer, NO tool calls

IF need NEW information:
    → Use analyze_query_sections + retrieve_sections
```

### Step 3: Formulate Response
```
Combine:
- Past conversation context
- Newly retrieved sections (if any)
- Conversational acknowledgment
```

## Interaction with RAG System

**This does NOT replace RAG** - it works alongside it:

| Scenario | Conversation Memory | RAG Tools | Result |
|----------|-------------------|-----------|--------|
| First question about tranches | Empty | ✅ retrieve_sections | New retrieval |
| Follow-up: "A1 coupon again?" | ✅ Shows past answer | ❌ Skip | Use memory |
| New topic: "Prepayment penalties" | Shows unrelated history | ✅ retrieve_sections | New retrieval |
| Complex: "Compare A1 to prepayment" | ✅ Shows past tranche info | ✅ Retrieve prepayment | Combine both |

## Benefits

### 1. Controlled Context Window
- Doesn't grow infinitely with conversation length
- Only relevant past exchanges loaded
- Recent context always included

### 2. Cost Efficiency
- Fewer tokens sent to LLM per turn
- Avoids redundant prospectus retrievals
- Smart caching via conversation memory

### 3. Better User Experience
- Agent references earlier conversation naturally
- No repetitive answers
- Conversational continuity maintained

### 4. Full Audit Trail
- Complete history in database
- Can review entire conversation
- Nothing lost, just selective loading

## Performance Characteristics

### Time Complexity:
- **Embedding current query**: O(1) - single API call
- **Embedding past messages**: O(n) where n = number of past messages
  - Cached in future version (store embeddings in DB)
- **Similarity calculation**: O(n) - cosine similarity for each message
- **Sorting**: O(n log n)

### Space Complexity:
- **Database storage**: O(m) where m = total messages (complete history)
- **Agent context**: O(top_k + recent_k) - constant, controlled size

### Optimization Opportunities:

1. **Cache embeddings in database**:
   ```python
   # Add embedding field to ChatMessage model
   embedding = models.JSONField(null=True, blank=True)
   ```
   - Generate embedding once when message created
   - Skip re-embedding on every retrieval

2. **Batch embedding API calls**:
   ```python
   # Instead of: embed each message individually
   # Do: client.embeddings.create(input=[msg1, msg2, ...])
   ```

3. **Vector database for large conversations**:
   - For 1000+ message conversations
   - Use Pinecone, Weaviate, or pgvector
   - Sub-linear search time

## Testing Scenarios

### Test 1: Memory Avoids Redundant Retrieval
```
User: "What tranches are in this deal?"
Agent: [Uses tools, retrieves sections, answers]

User: "What was the first tranche you mentioned?"
Agent: [Sees past answer in memory, NO tools, references it]

Expected: No retrieve_sections call on second question
```

### Test 2: New Topic Triggers Retrieval
```
User: "What tranches are in this deal?"
Agent: [Retrieves and answers]

User: "Now tell me about prepayment penalties"
Agent: [New topic, uses tools to retrieve prepayment sections]

Expected: retrieve_sections called for new topic
```

### Test 3: Long Conversation Context Control
```
# Have 50-message conversation
User (turn 51): "What was that thing you said about Z-tranches way back?"
Agent: [Semantic search finds message 10, references it]

Expected:
- Agent doesn't receive all 50 messages
- Sees ~7 messages (3 semantic + 4 recent)
- Successfully references message from turn 10
```

### Test 4: Similarity Scoring Works
```
User (turn 1): "What's the A1 tranche coupon?"
Agent: "5.2%"

User (turn 10): "Tell me about prepayment"
Agent: [Answers about prepayment]

User (turn 11): "What's the coupon for A1?"
Agent: [Should retrieve turn 1, not turn 10, due to semantic similarity]

Expected: Turn 1 has higher similarity score than turn 10
```

## Configuration File

To adjust parameters, modify [`graph.py`](./graph.py):

```python
# Line ~140
relevant_history = search_relevant_conversation_history(
    thread_id=thread_id,
    current_query=user_query,
    top_k=3,      # ← ADJUST THIS
    recent_k=4    # ← ADJUST THIS
)
```

## Monitoring and Debugging

### Enable Detailed Logging:

The system already logs:
```
[CONVERSATION_MEMORY] Retrieved X relevant messages
[CONVERSATION_MEMORY] Similarity scores: [0.92, 0.87, 0.71, 1.0, 1.0]
```

### Analyze Retrieval Quality:
- Check similarity scores in logs
- Scores > 0.8: Very relevant
- Scores 0.6-0.8: Moderately relevant
- Scores < 0.6: Weak relevance (might want to increase threshold)

### Adjust if Needed:
```python
# In search_relevant_conversation_history()
# Add similarity threshold filter:

top_relevant = [
    item for item in scored_messages[:top_k]
    if item['similarity'] > 0.6  # ← Similarity threshold
]
```

## Future Enhancements

1. **Embedding Caching** (High Priority)
   - Store embeddings in `ChatMessage.embedding` field
   - Reduce API calls by 90%+

2. **Adaptive top_k**
   - Adjust based on conversation length
   - Short conversations: include more
   - Long conversations: be more selective

3. **Topic Clustering**
   - Group messages by topic
   - Retrieve entire topic threads

4. **Conversation Summarization**
   - Summarize very old messages
   - Replace with summary after N turns

5. **User Feedback Loop**
   - Track when agent references memory successfully
   - Tune parameters based on feedback

## Troubleshooting

### Issue: Agent always retrieves, never uses memory
**Cause**: Similarity scores too low
**Fix**: Lower top_k or increase recent_k

### Issue: Agent uses stale information
**Cause**: Old messages ranked higher than recent updates
**Fix**: Increase recent_k to ensure latest info always included

### Issue: Too many tokens / high cost
**Cause**: Retrieving too many messages
**Fix**: Decrease top_k and recent_k

### Issue: Agent forgets recent context
**Cause**: recent_k too small
**Fix**: Increase recent_k to at least 4

## Summary

This semantic memory system provides:
- ✅ Complete conversation history in database
- ✅ Selective retrieval using embeddings
- ✅ Controlled context window size
- ✅ Natural conversation flow
- ✅ Cost-efficient operation
- ✅ Works alongside RAG system

The agent can intelligently decide:
- Reference past conversation when appropriate
- Retrieve new prospectus sections when needed
- Combine both for comprehensive answers
