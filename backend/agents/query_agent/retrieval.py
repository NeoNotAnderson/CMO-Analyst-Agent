"""
Hybrid search retrieval module combining semantic search (vector) + keyword search (BM25).

This module implements:
1. Semantic search using pgvector
2. Keyword search using BM25
3. Reciprocal Rank Fusion (RRF) for merging results
4. Metadata filtering for precision
5. Cross-encoder reranking for final relevance scoring
"""

from typing import List, Dict, Optional
from openai import OpenAI
import os
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
import numpy as np
from .rag_logger import log_semantic_results, log_keyword_results, log_rrf_results, log_rerank_results

load_dotenv()

# Initialize OpenAI client for embeddings
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize cross-encoder for reranking (lightweight model)
reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')


def generate_query_embedding(query: str) -> List[float]:
    """
    Generate embedding for search query using OpenAI text-embedding-3-small.

    Args:
        query: Search query string

    Returns:
        1536-dimensional embedding vector
    """
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=[query]
    )
    return response.data[0].embedding


def semantic_search(
    query: str,
    prospectus_id: str,
    top_k: int = 20,
    metadata_filters: Optional[Dict] = None
) -> List[Dict]:
    """
    Semantic search using pgvector similarity.

    Args:
        query: Search query
        prospectus_id: UUID of prospectus to search
        top_k: Number of top results to return
        metadata_filters: Optional metadata filters (e.g., {'has_table': True})

    Returns:
        List of dicts with keys: chunk_id, chunk_text, metadata, similarity_score, rank
    """
    from core.models import ProspectusChunk, Prospectus
    from pgvector.django import CosineDistance

    # Generate query embedding
    query_embedding = generate_query_embedding(query)

    # Build query
    queryset = ProspectusChunk.objects.filter(
        prospectus_id=prospectus_id
    )

    # Apply metadata filters
    if metadata_filters:
        for key, value in metadata_filters.items():
            queryset = queryset.filter(**{f'metadata__{key}': value})

    # Perform vector similarity search
    results = queryset.annotate(
        distance=CosineDistance('embedding', query_embedding)
    ).order_by('distance')[:top_k]

    # Format results
    search_results = []
    for rank, chunk in enumerate(results, 1):
        # Convert distance to similarity score (cosine similarity = 1 - distance)
        similarity = 1 - float(chunk.distance)

        search_results.append({
            'chunk_id': str(chunk.chunk_id),
            'chunk_text': chunk.chunk_text,
            'chunk_index': chunk.chunk_index,
            'metadata': chunk.metadata,
            'similarity_score': similarity,
            'rank': rank,
            'source': 'semantic'
        })

    log_semantic_results(query, search_results)
    return search_results


def keyword_search(
    query: str,
    prospectus_id: str,
    top_k: int = 20,
    metadata_filters: Optional[Dict] = None
) -> List[Dict]:
    """
    Keyword search using BM25 algorithm.

    Args:
        query: Search query
        prospectus_id: UUID of prospectus to search
        top_k: Number of top results to return
        metadata_filters: Optional metadata filters

    Returns:
        List of dicts with keys: chunk_id, chunk_text, metadata, bm25_score, rank
    """
    from core.models import ProspectusChunk

    # Load all chunks for the prospectus
    queryset = ProspectusChunk.objects.filter(
        prospectus_id=prospectus_id
    ).order_by('chunk_index')

    # Apply metadata filters
    if metadata_filters:
        for key, value in metadata_filters.items():
            queryset = queryset.filter(**{f'metadata__{key}': value})

    chunks = list(queryset)

    if not chunks:
        return []

    # Tokenize corpus (simple whitespace tokenization)
    tokenized_corpus = [chunk.chunk_text.lower().split() for chunk in chunks]

    # Build BM25 index
    bm25 = BM25Okapi(tokenized_corpus)

    # Tokenize query
    tokenized_query = query.lower().split()

    # Get BM25 scores
    scores = bm25.get_scores(tokenized_query)

    # Get top-k indices
    top_indices = np.argsort(scores)[::-1][:top_k]

    # Format results
    search_results = []
    for rank, idx in enumerate(top_indices, 1):
        chunk = chunks[idx]
        search_results.append({
            'chunk_id': str(chunk.chunk_id),
            'chunk_text': chunk.chunk_text,
            'chunk_index': chunk.chunk_index,
            'metadata': chunk.metadata,
            'bm25_score': float(scores[idx]),
            'rank': rank,
            'source': 'keyword'
        })

    log_keyword_results(query, search_results)
    return search_results


def reciprocal_rank_fusion(
    semantic_results: List[Dict],
    keyword_results: List[Dict],
    k: int = 60,
    semantic_weight: float = 0.5,
    keyword_weight: float = 0.5
) -> List[Dict]:
    """
    Merge semantic and keyword search results using Reciprocal Rank Fusion.

    RRF formula: score = w1 / (k + rank_semantic) + w2 / (k + rank_keyword)

    Args:
        semantic_results: Results from semantic_search()
        keyword_results: Results from keyword_search()
        k: Constant for RRF (typical value: 60)
        semantic_weight: Weight for semantic results (0-1)
        keyword_weight: Weight for keyword results (0-1)

    Returns:
        Merged and sorted list of results with RRF scores
    """
    # Build lookup tables by chunk_id
    semantic_lookup = {r['chunk_id']: r for r in semantic_results}
    keyword_lookup = {r['chunk_id']: r for r in keyword_results}

    # Get all unique chunk IDs
    all_chunk_ids = set(semantic_lookup.keys()) | set(keyword_lookup.keys())

    # Calculate RRF scores
    rrf_results = []
    for chunk_id in all_chunk_ids:
        # Get ranks (0 if not present in that result set)
        semantic_rank = semantic_lookup.get(chunk_id, {}).get('rank', 0)
        keyword_rank = keyword_lookup.get(chunk_id, {}).get('rank', 0)

        # RRF score
        rrf_score = 0.0
        if semantic_rank > 0:
            rrf_score += semantic_weight / (k + semantic_rank)
        if keyword_rank > 0:
            rrf_score += keyword_weight / (k + keyword_rank)

        # Get chunk data (prefer semantic result if available)
        chunk_data = semantic_lookup.get(chunk_id, keyword_lookup.get(chunk_id))

        rrf_results.append({
            **chunk_data,
            'rrf_score': rrf_score,
            'semantic_rank': semantic_rank,
            'keyword_rank': keyword_rank
        })

    # Sort by RRF score (descending)
    rrf_results.sort(key=lambda x: x['rrf_score'], reverse=True)

    log_rrf_results(rrf_results)
    return rrf_results


def rerank_with_cross_encoder(
    query: str,
    chunks: List[Dict],
    top_k: int = 10
) -> List[Dict]:
    """
    Rerank chunks using cross-encoder model for final relevance scoring.

    Cross-encoders provide more accurate relevance scores than bi-encoders
    by jointly encoding query + document, but are slower (use after initial retrieval).

    Args:
        query: Search query
        chunks: List of candidate chunks from hybrid search
        top_k: Number of top results to return after reranking

    Returns:
        Reranked list of chunks with cross-encoder scores
    """
    if not chunks:
        return []

    # Prepare (query, chunk_text) pairs
    pairs = [(query, chunk['chunk_text']) for chunk in chunks]

    # Get cross-encoder scores
    scores = reranker_model.predict(pairs)

    # Add scores to chunks
    for chunk, score in zip(chunks, scores):
        chunk['rerank_score'] = float(score)

    # Sort by rerank score
    chunks.sort(key=lambda x: x['rerank_score'], reverse=True)
    final = chunks[:top_k]

    log_rerank_results(query, final)
    return final


def hybrid_search(
    query: str,
    prospectus_id: str,
    top_k: int = 10,
    retrieval_k: int = 30,
    metadata_filters: Optional[Dict] = None,
    search_strategy: str = "hybrid",
    use_reranking: bool = True
) -> List[Dict]:
    """
    Perform hybrid search combining semantic + keyword search with reranking.

    Args:
        query: Search query
        prospectus_id: UUID of prospectus to search
        top_k: Final number of results to return (after reranking)
        retrieval_k: Number of candidates to retrieve before reranking (higher = better recall)
        metadata_filters: Optional metadata filters
        search_strategy: "hybrid", "semantic_heavy", or "keyword_heavy"
        use_reranking: Whether to apply cross-encoder reranking

    Returns:
        List of top-k most relevant chunks with scores and metadata

    Pipeline:
        1. Semantic search (vector similarity)
        2. Keyword search (BM25)
        3. Reciprocal Rank Fusion (merge results)
        4. Cross-encoder reranking (optional)
        5. Return top-k
    """
    # Determine weights based on strategy
    if search_strategy == "semantic_heavy":
        semantic_weight = 0.7
        keyword_weight = 0.3
    elif search_strategy == "keyword_heavy":
        semantic_weight = 0.3
        keyword_weight = 0.7
    else:  # hybrid
        semantic_weight = 0.5
        keyword_weight = 0.5

    # Step 1: Semantic search
    print(f"[RETRIEVAL] Running semantic search (top_k={retrieval_k})...")
    semantic_results = semantic_search(
        query=query,
        prospectus_id=prospectus_id,
        top_k=retrieval_k,
        metadata_filters=metadata_filters
    )

    # Step 2: Keyword search
    print(f"[RETRIEVAL] Running keyword search (top_k={retrieval_k})...")
    keyword_results = keyword_search(
        query=query,
        prospectus_id=prospectus_id,
        top_k=retrieval_k,
        metadata_filters=metadata_filters
    )

    # Step 3: Merge with RRF
    print(f"[RETRIEVAL] Merging results with RRF (weights: {semantic_weight}/{keyword_weight})...")
    merged_results = reciprocal_rank_fusion(
        semantic_results=semantic_results,
        keyword_results=keyword_results,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )

    # Step 4: Rerank with cross-encoder (optional)
    if use_reranking:
        print(f"[RETRIEVAL] Reranking with cross-encoder (top_k={top_k})...")
        final_results = rerank_with_cross_encoder(
            query=query,
            chunks=merged_results,
            top_k=top_k
        )
    else:
        final_results = merged_results[:top_k]

    print(f"[RETRIEVAL] Returning {len(final_results)} chunks")
    return final_results


def format_retrieved_chunks(chunks: List[Dict], include_metadata: bool = True) -> str:
    """
    Format retrieved chunks into a readable string for LLM context.

    Args:
        chunks: List of retrieved chunks from hybrid_search()
        include_metadata: Whether to include section paths and page numbers

    Returns:
        Formatted string with all chunks and citations
    """
    if not chunks:
        return "No relevant information found in the prospectus."

    result = [f"Retrieved {len(chunks)} relevant chunks from the prospectus:\n"]

    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get('metadata', {})
        section_path = metadata.get('section_path', [])
        page_num = metadata.get('page_num', 'Unknown')

        # Build header
        section_str = ' > '.join(section_path) if section_path else 'Unknown Section'
        header = f"\n{'='*80}\nCHUNK {i}: [{section_str}] (Page {page_num})"

        # Add relevance score if available
        if 'rerank_score' in chunk:
            header += f" | Relevance: {chunk['rerank_score']:.3f}"

        result.append(header)
        result.append(f"{'='*80}\n")
        result.append(chunk['chunk_text'])
        result.append("\n")

    result.append(f"\n{'='*80}")
    result.append("END OF RETRIEVED CHUNKS")
    result.append(f"{'='*80}\n")

    instructions = """
INSTRUCTIONS FOR ANSWERING:
- Base your answer ONLY on the retrieved chunks above
- Always cite sources using [Section Name, Page X] format
- If the answer is not in the retrieved chunks, say "I don't have enough information to answer this question"
- Never make up or hallucinate information
"""
    result.append(instructions)

    return '\n'.join(result)
