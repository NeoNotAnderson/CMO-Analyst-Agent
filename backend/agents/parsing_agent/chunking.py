"""
Chunking module for converting parsed prospectus sections into retrievable chunks.

This module handles:
1. Text chunking with paragraph-aware splitting and token-based limits
2. Table-to-text conversion for better semantic search
3. Metadata extraction for filtering and citation
4. Embedding generation for vector search
"""

from typing import List, Dict, Optional
import tiktoken
import re
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client for embeddings
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Token counter for text-embedding-3-small (uses cl100k_base encoding)
tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    return len(tokenizer.encode(text))


def chunk_text(
    text: str,
    max_tokens: int = 512,
    overlap_pct: float = 0.10,
    section_heading: str = ""
) -> List[str]:
    """
    Chunk text into overlapping segments respecting paragraph boundaries.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk (default 512)
        overlap_pct: Overlap percentage between chunks (default 10%)
        section_heading: Optional section heading to prepend to each chunk

    Returns:
        List of text chunks

    Strategy:
        - Split on paragraph boundaries (\\n\\n)
        - Build chunks by adding complete paragraphs
        - Never split mid-paragraph
        - Add overlap by including last few paragraphs from previous chunk
    """
    if not text or not text.strip():
        return []

    # Prepend section heading if provided (improves semantic signal)
    heading_prefix = f"{section_heading}\n\n" if section_heading else ""

    # Split into paragraphs
    paragraphs = re.split(r'\n\n+', text.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return []

    chunks = []
    current_chunk_paragraphs = []
    current_token_count = count_tokens(heading_prefix) if heading_prefix else 0
    overlap_tokens = int(max_tokens * overlap_pct)

    for paragraph in paragraphs:
        para_tokens = count_tokens(paragraph)

        # If single paragraph exceeds max_tokens, split it by sentences
        if para_tokens > max_tokens:
            sentences = re.split(r'(?<=[.!?])\s+', paragraph)
            for sentence in sentences:
                sent_tokens = count_tokens(sentence)
                if current_token_count + sent_tokens > max_tokens:
                    # Finalize current chunk
                    if current_chunk_paragraphs:
                        chunk_text = heading_prefix + '\n\n'.join(current_chunk_paragraphs)
                        chunks.append(chunk_text)

                    # Start new chunk with overlap
                    current_chunk_paragraphs = _get_overlap_paragraphs(
                        current_chunk_paragraphs, overlap_tokens
                    )
                    current_token_count = count_tokens('\n\n'.join(current_chunk_paragraphs)) + count_tokens(heading_prefix)

                current_chunk_paragraphs.append(sentence)
                current_token_count += sent_tokens
        else:
            # Check if adding this paragraph would exceed limit
            if current_token_count + para_tokens > max_tokens and current_chunk_paragraphs:
                # Finalize current chunk
                chunk_text = heading_prefix + '\n\n'.join(current_chunk_paragraphs)
                chunks.append(chunk_text)

                # Start new chunk with overlap
                current_chunk_paragraphs = _get_overlap_paragraphs(
                    current_chunk_paragraphs, overlap_tokens
                )
                current_token_count = count_tokens('\n\n'.join(current_chunk_paragraphs)) + count_tokens(heading_prefix)

            # Add paragraph to current chunk
            current_chunk_paragraphs.append(paragraph)
            current_token_count += para_tokens

    # Add final chunk
    if current_chunk_paragraphs:
        chunk_text = heading_prefix + '\n\n'.join(current_chunk_paragraphs)
        chunks.append(chunk_text)

    return chunks


def _get_overlap_paragraphs(paragraphs: List[str], overlap_tokens: int) -> List[str]:
    """
    Get paragraphs from the end that fit within overlap token budget.

    Args:
        paragraphs: List of paragraphs from previous chunk
        overlap_tokens: Maximum tokens for overlap

    Returns:
        List of paragraphs to carry over to next chunk
    """
    if not paragraphs or overlap_tokens <= 0:
        return []

    overlap_paragraphs = []
    total_tokens = 0

    # Add paragraphs from end until we hit overlap limit
    for paragraph in reversed(paragraphs):
        para_tokens = count_tokens(paragraph)
        if total_tokens + para_tokens > overlap_tokens:
            break
        overlap_paragraphs.insert(0, paragraph)
        total_tokens += para_tokens

    return overlap_paragraphs


def generate_table_description(table_dict: Dict) -> str:
    """
    Convert table JSON to natural language description for better semantic search.

    Args:
        table_dict: Table data with 'summary' and 'data' fields

    Returns:
        Natural language description of the table

    Example:
        Input: {"summary": "Tranche details", "data": [{"Class": "A-1", "Coupon": "3.5%"}]}
        Output: "This table shows Tranche details. The table contains information about:
                Class, Coupon. Key values include: Class A-1 with Coupon 3.5%."
    """
    if not table_dict or not isinstance(table_dict, dict):
        return ""

    summary = table_dict.get('summary', '')
    data = table_dict.get('data', [])

    if not data:
        return f"Table: {summary}" if summary else "Empty table"

    # Extract column names
    if isinstance(data[0], dict):
        columns = list(data[0].keys())
    else:
        columns = []

    description_parts = []

    # Add summary
    if summary:
        description_parts.append(f"This table shows {summary}.")

    # Add column information
    if columns:
        columns_str = ', '.join(columns)
        description_parts.append(f"The table contains information about: {columns_str}.")

    # Add sample values (first 3 rows)
    sample_rows = data[:3]
    if sample_rows:
        description_parts.append("Key values include:")
        for row in sample_rows:
            if isinstance(row, dict):
                row_str = ', '.join(f"{k} {v}" for k, v in row.items())
                description_parts.append(f"  - {row_str}")

    return ' '.join(description_parts)


def process_section_to_chunks(
    section: Dict,
    parent_path: Optional[List[str]] = None,
    chunk_index_start: int = 0
) -> List[Dict]:
    """
    Recursively process section and subsections into chunks with metadata.

    Args:
        section: Section dict with 'title', 'text', 'table', 'sections' fields
        parent_path: Hierarchical path to this section (e.g., ["SUMMARY", "General"])
        chunk_index_start: Starting index for chunks

    Returns:
        List of chunk dicts with structure:
        {
            'chunk_text': str,
            'chunk_index': int,
            'metadata': {
                'section_title': str,
                'section_path': List[str],
                'page_num': int,
                'token_count': int,
                'has_table': bool,
                'is_table_description': bool
            }
        }
    """
    if parent_path is None:
        parent_path = []

    chunks = []
    current_index = chunk_index_start

    # Build section path
    section_title = section.get('title', '')
    current_path = parent_path + [section_title] if section_title else parent_path
    page_num = section.get('page_num', section.get('page', 'Unknown'))

    # Extract text content
    text_content = section.get('text', '')

    # Process text chunks
    if text_content and text_content.strip():
        text_chunks = chunk_text(
            text=text_content,
            max_tokens=512,
            overlap_pct=0.10,
            section_heading=section_title
        )

        for chunk_text_content in text_chunks:
            chunk = {
                'chunk_text': chunk_text_content,
                'chunk_index': current_index,
                'metadata': {
                    'section_title': section_title,
                    'section_path': current_path,
                    'page_num': page_num,
                    'token_count': count_tokens(chunk_text_content),
                    'has_table': False,
                    'is_table_description': False
                }
            }
            chunks.append(chunk)
            current_index += 1

    # Process table (create separate chunk with description + data)
    table = section.get('table')
    if table and isinstance(table, dict):
        # Generate natural language description
        table_description = generate_table_description(table)

        # Combine description with structured data for better search
        table_text = f"{section_title}\n\n{table_description}"

        # Add raw table data for exact value lookups
        table_data = table.get('data', [])
        if table_data:
            table_text += "\n\nTable data:\n"
            for row in table_data:
                if isinstance(row, dict):
                    row_str = ' | '.join(f"{k}: {v}" for k, v in row.items())
                    table_text += f"{row_str}\n"

        chunk = {
            'chunk_text': table_text,
            'chunk_index': current_index,
            'metadata': {
                'section_title': section_title,
                'section_path': current_path,
                'page_num': page_num,
                'token_count': count_tokens(table_text),
                'has_table': True,
                'is_table_description': True
            }
        }
        chunks.append(chunk)
        current_index += 1

    # Recursively process subsections
    subsections = section.get('sections', [])
    if subsections:
        for subsection in subsections:
            subsection_chunks = process_section_to_chunks(
                section=subsection,
                parent_path=current_path,
                chunk_index_start=current_index
            )
            chunks.extend(subsection_chunks)
            current_index += len(subsection_chunks)

    return chunks


def generate_embeddings(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using OpenAI text-embedding-3-small.

    Args:
        texts: List of text strings to embed
        batch_size: Number of texts to embed per API call

    Returns:
        List of embedding vectors (1536-dimensional)
    """
    if not texts:
        return []

    all_embeddings = []

    # Process in batches to avoid API limits
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )

        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


def process_prospectus_to_chunks(parsed_file: Dict) -> List[Dict]:
    """
    Convert entire parsed prospectus into chunks with embeddings.

    Args:
        parsed_file: Parsed prospectus JSON (from Prospectus.parsed_file)

    Returns:
        List of chunk dicts ready for database insertion

    Example usage:
        chunks = process_prospectus_to_chunks(prospectus.parsed_file)
        # chunks = [{'chunk_text': ..., 'chunk_index': ..., 'metadata': ..., 'embedding': [...]}, ...]
    """
    if not parsed_file or 'sections' not in parsed_file:
        return []

    # Process all sections into chunks
    all_chunks = []
    current_index = 0

    for section in parsed_file['sections']:
        section_chunks = process_section_to_chunks(
            section=section,
            parent_path=[],
            chunk_index_start=current_index
        )
        all_chunks.extend(section_chunks)
        current_index += len(section_chunks)

    # Generate embeddings for all chunks
    chunk_texts = [chunk['chunk_text'] for chunk in all_chunks]
    embeddings = generate_embeddings(chunk_texts)

    # Add embeddings to chunks
    for chunk, embedding in zip(all_chunks, embeddings):
        chunk['embedding'] = embedding

    return all_chunks
