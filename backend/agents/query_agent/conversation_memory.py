"""
Conversation Memory Management with Semantic Search

This module provides intelligent retrieval of relevant past conversation context
using embeddings and semantic similarity search.

IMPORTANT: This works ALONGSIDE the RAG retrieval system, not replacing it.

Workflow:
1. User asks question → Agent sees relevant past conversation (via this module)
2. Agent decides if it needs to retrieve sections from prospectus:
   - If already answered in past conversation → references past response
   - If needs new/additional info → calls analyze_query_sections + retrieve_sections
3. Agent formulates response using both past conversation AND new retrieval

Benefits:
- Avoids redundant section retrievals when info already discussed
- Maintains conversational flow with context awareness
- Still retrieves from prospectus when needed
- Agent makes intelligent decision: use memory OR fetch new data

The complete conversation history is always stored in the database.
This module only controls WHAT gets loaded into the agent's context window.
"""

from typing import List, Dict, Tuple
import numpy as np
from openai import OpenAI
from django.conf import settings
from core.models import ConversationThread, ChatMessage
import os


# Initialize OpenAI client for embeddings
# Use os.getenv to avoid dependency on Django settings being fully loaded
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    Generate embedding for a text using OpenAI's embedding model.

    Args:
        text: Text to embed
        model: Embedding model to use (default: text-embedding-3-small)

    Returns:
        List of floats representing the embedding vector
    """
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Similarity score between -1 and 1 (higher = more similar)
    """
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)

    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def search_relevant_conversation_history(
    thread_id: str,
    current_query: str,
    top_k: int = 3,
    recent_k: int = 4
) -> List[Dict]:
    """
    Search conversation history for relevant past exchanges using semantic similarity.

    Strategy:
    1. Always include the most recent `recent_k` messages (for immediate context)
    2. Search older messages for top `top_k` semantically similar exchanges
    3. Return combined list sorted by timestamp

    Args:
        thread_id: UUID of the conversation thread
        current_query: The user's current message
        top_k: Number of semantically similar past exchanges to retrieve (default: 3)
        recent_k: Number of most recent messages to always include (default: 4)

    Returns:
        List of message dicts with 'role', 'content', 'timestamp', 'similarity_score'

    Example:
        If conversation has 30 messages and we call with top_k=3, recent_k=4:
        - Messages 27-30: Included (recent context)
        - Messages 1-26: Searched via embeddings, top 3 most similar included
        - Total returned: ~7 messages (4 recent + 3 semantic matches)
    """
    try:
        # Get the conversation thread
        thread = ConversationThread.objects.get(thread_id=thread_id)

        # Get all user and assistant messages, ordered by time.
        # Exclude any trailing user message that has no assistant reply
        # (left behind by a failed query) — it has no useful content to surface.
        all_messages = ChatMessage.objects.filter(
            thread=thread,
            role__in=['user', 'assistant']
        ).order_by('created_at')

        if not all_messages.exists():
            return []

        # Convert to list and strip any trailing user message that has no assistant reply.
        # This happens when a previous query failed — the user message was saved but
        # the agent never produced a response. Including it gives the LLM a dangling
        # half-exchange with no answer, which is misleading.
        message_list = list(all_messages)
        if message_list and message_list[-1].role == 'user':
            message_list = message_list[:-1]

        if not message_list:
            return []
        total_messages = len(message_list)

        # If conversation is short, return all messages
        if total_messages <= recent_k:
            return [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.created_at.isoformat(),
                    'similarity_score': 1.0  # Recent messages get max score
                }
                for msg in message_list
            ]

        # Split into recent and older messages
        recent_messages = message_list[-recent_k:]
        older_messages = message_list[:-recent_k]

        # Get embedding for current query
        query_embedding = get_embedding(current_query)

        # Calculate similarity scores for older messages
        scored_messages = []
        for msg in older_messages:
            # Only search user messages for semantic similarity
            # (user questions are better for matching than assistant responses)
            if msg.role == 'user':
                msg_embedding = get_embedding(msg.content)
                similarity = cosine_similarity(query_embedding, msg_embedding)

                scored_messages.append({
                    'message': msg,
                    'similarity': similarity
                })

        # Sort by similarity and take top_k
        scored_messages.sort(key=lambda x: x['similarity'], reverse=True)
        top_relevant = scored_messages[:top_k]

        # For each relevant user message, include the assistant response that follows
        relevant_exchanges = []
        for item in top_relevant:
            user_msg = item['message']
            similarity = item['similarity']

            # Add user message
            relevant_exchanges.append({
                'role': user_msg.role,
                'content': user_msg.content,
                'timestamp': user_msg.created_at.isoformat(),
                'similarity_score': similarity
            })

            # Find the assistant reply: must be the very next message AND role='assistant'
            # If the next message is another user message (e.g. a failed query left no reply),
            # skip it — an incomplete exchange is worse than no context at all.
            user_msg_index = message_list.index(user_msg)
            next_index = user_msg_index + 1
            if next_index < len(message_list):
                next_msg = message_list[next_index]
                if next_msg.role == 'assistant':
                    relevant_exchanges.append({
                        'role': next_msg.role,
                        'content': next_msg.content,
                        'timestamp': next_msg.created_at.isoformat(),
                        'similarity_score': similarity
                    })

        # Add recent messages
        recent_exchanges = [
            {
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.created_at.isoformat(),
                'similarity_score': 1.0  # Recent messages always relevant
            }
            for msg in recent_messages
        ]

        # Combine and sort by timestamp to maintain conversation flow
        all_relevant = relevant_exchanges + recent_exchanges
        all_relevant.sort(key=lambda x: x['timestamp'])

        # Remove duplicates (in case a message appears in both relevant and recent)
        seen_contents = set()
        unique_messages = []
        for msg in all_relevant:
            key = (msg['role'], msg['content'], msg['timestamp'])
            if key not in seen_contents:
                seen_contents.add(key)
                unique_messages.append(msg)

        return unique_messages

    except ConversationThread.DoesNotExist:
        print(f"[CONVERSATION_MEMORY] Thread {thread_id} not found")
        return []
    except Exception as e:
        print(f"[CONVERSATION_MEMORY] Error searching history: {e}")
        import traceback
        traceback.print_exc()
        return []


def format_conversation_context(relevant_messages: List[Dict]) -> str:
    """
    Format retrieved conversation history into a readable context string.

    Args:
        relevant_messages: List of message dicts from search_relevant_conversation_history

    Returns:
        Formatted string showing relevant past conversation exchanges
    """
    if not relevant_messages:
        return ""

    context_lines = [
        "=== RELEVANT PAST CONVERSATION ===",
        "(You may have already answered similar questions. Check if the answer is here before using tools.)",
        ""
    ]

    for msg in relevant_messages:
        role = msg['role'].upper()
        content = msg['content']
        similarity = msg.get('similarity_score', 0.0)

        if similarity < 1.0:  # Only show score for semantically retrieved messages
            context_lines.append(f"[{role}] (similarity: {similarity:.2f})")
        else:
            context_lines.append(f"[{role}] (recent)")

        context_lines.append(content)
        context_lines.append("")

    context_lines.append("=== END PAST CONVERSATION ===")
    context_lines.append("")
    context_lines.append("IMPORTANT: Review the above conversation before deciding to call tools.")
    context_lines.append("If the user's question is already answered above, reference that answer.")
    context_lines.append("If you need NEW information not in the conversation, use your tools.")
    context_lines.append("")

    return "\n".join(context_lines)
