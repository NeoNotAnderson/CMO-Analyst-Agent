"""
Query analysis module for classifying user queries and determining retrieval strategy.

This module analyzes user queries to determine:
- Query type (specific fact vs. general overview)
- Named entities (tranches, dates, rates)
- Optimal search strategy (hybrid, semantic-heavy, keyword-heavy)
- Recommended number of chunks to retrieve
"""

from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM for query analysis
llm = ChatOpenAI(
    model='gpt-4o-mini',
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0
)


class QueryAnalysis(BaseModel):
    """Structured output schema for query analysis."""
    query_type: str = Field(
        description="Type of query: 'specific_fact', 'general_overview', or 'comparison'"
    )
    entities: List[str] = Field(
        description="List of named entities mentioned (tranche names, specific dates, rates, etc.)",
        default_factory=list
    )
    topics: List[str] = Field(
        description="List of semantic topics (e.g., 'risk factors', 'payment priority', 'tranches')",
        default_factory=list
    )
    requires_structured_data: bool = Field(
        description="True if query asks for exact values (dates, rates, amounts)"
    )
    recommended_k: int = Field(
        description="Recommended number of chunks to retrieve (5-10 for specific, 20-30 for general)"
    )
    search_strategy: str = Field(
        description="Recommended search strategy: 'hybrid', 'semantic_heavy', or 'keyword_heavy'"
    )
    reasoning: str = Field(
        description="Brief explanation of the analysis"
    )


QUERY_ANALYSIS_PROMPT = """
Analyze the following user query about a CMO prospectus and determine the optimal retrieval strategy.

User Query: {query}

Classify the query and provide retrieval recommendations:

1. **Query Type**:
   - "specific_fact": Asking for exact values (dates, rates, amounts, specific details)
     Examples: "What is the coupon rate of Tranche A-1?", "When is the first payment date?"

   - "general_overview": Asking for summaries, explanations, or broad understanding
     Examples: "What are the main risk factors?", "Explain the deal structure"

   - "comparison": Asking to compare multiple entities or concepts
     Examples: "Compare the senior and subordinate tranches", "What's the difference between..."

2. **Named Entities**: Extract specific entities mentioned:
   - Tranche names (e.g., "A-1", "Class A", "Z-tranche")
   - Specific dates or time periods
   - Specific rates, amounts, or percentages
   - Named sections (e.g., "General", "Risk Factors")

3. **Topics**: Identify semantic topics:
   - risk factors, tranches, payment priority, prepayment, credit enhancement, etc.

4. **Requires Structured Data**:
   - True if asking for exact factual values
   - False if asking for explanations or summaries

5. **Recommended K** (number of chunks):
   - 5-10 for specific_fact queries (precise answers)
   - 15-20 for comparison queries (need multiple perspectives)
   - 25-30 for general_overview queries (need broad context)

6. **Search Strategy**:
   - "keyword_heavy": Use when query has specific terms (tranche names, exact phrases)
     → Higher weight on BM25/keyword search

   - "semantic_heavy": Use when query is conceptual or uses different wording
     → Higher weight on vector/semantic search

   - "hybrid": Use when query has both specific terms AND semantic concepts
     → Balanced weight on both

Provide a structured analysis following the QueryAnalysis schema.
"""


def analyze_query(query: str) -> Dict:
    """
    Analyze user query to determine optimal retrieval strategy.

    Args:
        query: User's question about the prospectus

    Returns:
        Dictionary with analysis results:
        {
            'query_type': str,
            'entities': List[str],
            'topics': List[str],
            'requires_structured_data': bool,
            'recommended_k': int,
            'search_strategy': str,
            'reasoning': str
        }

    Example:
        >>> analyze_query("What is the coupon rate of Tranche A-1?")
        {
            'query_type': 'specific_fact',
            'entities': ['Tranche A-1', 'coupon rate'],
            'topics': ['tranches', 'certificates'],
            'requires_structured_data': True,
            'recommended_k': 8,
            'search_strategy': 'keyword_heavy',
            'reasoning': 'Query asks for exact value (coupon rate) for specific tranche'
        }
    """
    # Use structured output
    structured_llm = llm.with_structured_output(QueryAnalysis)

    prompt = QUERY_ANALYSIS_PROMPT.format(query=query)
    result = structured_llm.invoke(prompt)

    # Convert Pydantic model to dict
    return result.model_dump()


def should_use_metadata_filter(analysis: Dict) -> bool:
    """
    Determine if metadata filtering should be applied based on query analysis.

    Args:
        analysis: Query analysis result from analyze_query()

    Returns:
        True if metadata filtering would be beneficial
    """
    # Use metadata filtering if:
    # 1. Query has specific entities (narrow down search space)
    # 2. Query requires structured data (tables are likely relevant)
    has_entities = len(analysis.get('entities', [])) > 0
    requires_data = analysis.get('requires_structured_data', False)

    return has_entities or requires_data


def get_metadata_filters(analysis: Dict) -> Dict:
    """
    Build metadata filters based on query analysis.

    Args:
        analysis: Query analysis result from analyze_query()

    Returns:
        Dictionary of metadata filters to apply
    """
    filters = {}

    # If query requires structured data, prioritize table chunks
    if analysis.get('requires_structured_data', False):
        filters['has_table'] = True

    # Could add more sophisticated filtering based on entities/topics
    # e.g., if entity contains "tranche", filter by sections with "tranche" in path

    return filters
