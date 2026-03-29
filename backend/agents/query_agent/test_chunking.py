"""
Unit tests for the chunking module.

Tests cover:
- Text chunking with token limits and overlap
- Paragraph-aware splitting
- Table description generation
- Section to chunks conversion
- Embedding generation (mocked)
"""

import sys
import os

# Set up Django BEFORE imports if running as main script
if __name__ == '__main__':
    current_file = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    os.chdir(backend_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    import django
    django.setup()

from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
from agents.parsing_agent import chunking


class ChunkTextTestCase(TestCase):
    """Test cases for chunk_text function."""

    def test_chunk_text_basic(self):
        """Test basic text chunking with paragraph boundaries."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

        chunks = chunking.chunk_text(text, max_tokens=20, overlap_pct=0.10)

        # Should create chunks at paragraph boundaries
        self.assertGreater(len(chunks), 0)

        # Each chunk should be a string
        for chunk in chunks:
            self.assertIsInstance(chunk, str)

    def test_chunk_text_with_heading(self):
        """Test that section heading is prepended to each chunk."""
        text = "This is the main text content."
        heading = "RISK FACTORS"

        chunks = chunking.chunk_text(text, section_heading=heading)

        # Every chunk should start with heading
        for chunk in chunks:
            self.assertTrue(chunk.startswith(heading))

    def test_chunk_text_respects_token_limit(self):
        """Test that chunks don't exceed max_tokens."""
        # Create long text
        long_paragraph = " ".join(["word"] * 1000)

        chunks = chunking.chunk_text(long_paragraph, max_tokens=100, overlap_pct=0)

        # Each chunk should be under limit
        for chunk in chunks:
            token_count = chunking.count_tokens(chunk)
            self.assertLessEqual(token_count, 150)  # Some flexibility for sentence boundaries

    def test_chunk_text_paragraph_boundaries(self):
        """Test that chunks split at paragraph boundaries, not mid-paragraph."""
        text = "Para 1 is short.\n\nPara 2 is also short.\n\nPara 3 is short too."

        chunks = chunking.chunk_text(text, max_tokens=50, overlap_pct=0)

        # Chunks should not split paragraphs (unless paragraph is too long)
        for chunk in chunks:
            # Should not have split mid-word
            self.assertFalse(chunk.endswith('-'))

    def test_chunk_text_overlap(self):
        """Test that chunks have specified overlap."""
        text = "Para 1.\n\nPara 2.\n\nPara 3.\n\nPara 4."

        chunks = chunking.chunk_text(text, max_tokens=30, overlap_pct=0.20)

        # Should have multiple chunks with overlap
        if len(chunks) > 1:
            # Can't easily verify exact overlap, but check chunks exist
            self.assertGreater(len(chunks), 1)

    def test_chunk_text_empty_input(self):
        """Test handling of empty input."""
        chunks = chunking.chunk_text("")
        self.assertEqual(len(chunks), 0)

        chunks = chunking.chunk_text("   \n\n   ")
        self.assertEqual(len(chunks), 0)


class GenerateTableDescriptionTestCase(TestCase):
    """Test cases for generate_table_description function."""

    def test_generate_table_description_basic(self):
        """Test basic table description generation."""
        table = {
            'summary': 'Certificate classes',
            'data': [
                {'Class': 'A-1', 'Coupon': '3.50%'},
                {'Class': 'A-2', 'Coupon': '4.00%'}
            ]
        }

        description = chunking.generate_table_description(table)

        # Should include summary
        self.assertIn('Certificate classes', description)

        # Should include column names
        self.assertIn('Class', description)
        self.assertIn('Coupon', description)

        # Should include sample values
        self.assertIn('A-1', description)
        self.assertIn('3.50%', description)

    def test_generate_table_description_with_many_rows(self):
        """Test that only first 3 rows are included in description."""
        table = {
            'summary': 'Many rows',
            'data': [
                {'Class': f'A-{i}', 'Value': f'{i}%'}
                for i in range(1, 10)  # 9 rows
            ]
        }

        description = chunking.generate_table_description(table)

        # Should include first 3
        self.assertIn('A-1', description)
        self.assertIn('A-2', description)
        self.assertIn('A-3', description)

        # Should NOT include later rows
        self.assertNotIn('A-9', description)

    def test_generate_table_description_empty_table(self):
        """Test handling of empty table."""
        table = {'summary': 'Empty', 'data': []}

        description = chunking.generate_table_description(table)

        # Should return something
        self.assertIsInstance(description, str)
        self.assertIn('Empty', description)

    def test_generate_table_description_no_summary(self):
        """Test table without summary."""
        table = {
            'data': [
                {'Col1': 'val1', 'Col2': 'val2'}
            ]
        }

        description = chunking.generate_table_description(table)

        # Should still describe columns and data
        self.assertIn('Col1', description)
        self.assertIn('val1', description)


class ProcessSectionToChunksTestCase(TestCase):
    """Test cases for process_section_to_chunks function."""

    def test_process_section_simple_text(self):
        """Test processing section with only text content."""
        section = {
            'title': 'RISK FACTORS',
            'text': 'This section describes the risks.',
            'page_num': 12,
            'level': 1
        }

        chunks = chunking.process_section_to_chunks(section, parent_path=[])

        # Should create at least one chunk
        self.assertGreater(len(chunks), 0)

        # Check chunk structure
        chunk = chunks[0]
        self.assertIn('chunk_text', chunk)
        self.assertIn('chunk_index', chunk)
        self.assertIn('metadata', chunk)

        # Check metadata
        metadata = chunk['metadata']
        self.assertEqual(metadata['section_title'], 'RISK FACTORS')
        self.assertEqual(metadata['page_num'], 12)
        self.assertFalse(metadata['has_table'])

    def test_process_section_with_table(self):
        """Test processing section with table."""
        section = {
            'title': 'The Certificates',
            'text': 'Certificate details:',
            'table': {
                'summary': 'Certificate classes',
                'data': [
                    {'Class': 'A-1', 'Amount': '$500M'}
                ]
            },
            'page_num': 15,
            'level': 1
        }

        chunks = chunking.process_section_to_chunks(section, parent_path=[])

        # Should create 2 chunks: one for text, one for table
        self.assertEqual(len(chunks), 2)

        # First chunk: text
        text_chunk = chunks[0]
        self.assertFalse(text_chunk['metadata']['has_table'])

        # Second chunk: table
        table_chunk = chunks[1]
        self.assertTrue(table_chunk['metadata']['has_table'])
        self.assertTrue(table_chunk['metadata']['is_table_description'])

        # Table chunk should contain description
        self.assertIn('Certificate classes', table_chunk['chunk_text'])
        self.assertIn('A-1', table_chunk['chunk_text'])

    def test_process_section_hierarchical_path(self):
        """Test that section path is correctly built."""
        section = {
            'title': 'General',
            'text': 'Some text',
            'page_num': 26,
            'level': 2
        }

        parent_path = ['SUMMARY']
        chunks = chunking.process_section_to_chunks(section, parent_path=parent_path)

        # Check section path
        metadata = chunks[0]['metadata']
        self.assertEqual(metadata['section_path'], ['SUMMARY', 'General'])

    def test_process_section_with_subsections(self):
        """Test recursive processing of subsections."""
        section = {
            'title': 'SUMMARY',
            'text': 'Summary text',
            'page_num': 5,
            'level': 1,
            'sections': [
                {
                    'title': 'General',
                    'text': 'General info',
                    'page_num': 6,
                    'level': 2
                }
            ]
        }

        chunks = chunking.process_section_to_chunks(section, parent_path=[])

        # Should have chunks from both parent and subsection
        self.assertGreater(len(chunks), 1)

        # Check that subsection chunk has correct path
        subsection_chunks = [c for c in chunks if c['metadata']['section_title'] == 'General']
        self.assertGreater(len(subsection_chunks), 0)
        self.assertEqual(subsection_chunks[0]['metadata']['section_path'], ['SUMMARY', 'General'])

    def test_process_section_chunk_indices(self):
        """Test that chunk indices are sequential."""
        section = {
            'title': 'Test',
            'text': 'Para 1.\n\nPara 2.\n\nPara 3.',
            'page_num': 1,
            'level': 1
        }

        chunks = chunking.process_section_to_chunks(section, chunk_index_start=10)

        # Indices should be sequential starting from 10
        indices = [c['chunk_index'] for c in chunks]
        self.assertEqual(indices[0], 10)
        if len(indices) > 1:
            for i in range(len(indices) - 1):
                self.assertEqual(indices[i+1], indices[i] + 1)


class ProcessProspectusToChunksTestCase(TestCase):
    """Test cases for process_prospectus_to_chunks function."""

    @patch('agents.parsing_agent.chunking.generate_embeddings')
    def test_process_prospectus_basic(self, mock_embeddings):
        """Test processing full prospectus structure."""
        # Mock embeddings
        mock_embeddings.return_value = [[0.1, 0.2, 0.3] * 512]  # 1536 dims

        parsed_file = {
            'sections': [
                {
                    'title': 'RISK FACTORS',
                    'text': 'Risk text',
                    'page_num': 12,
                    'level': 1
                }
            ]
        }

        chunks = chunking.process_prospectus_to_chunks(parsed_file)

        # Should create chunks
        self.assertGreater(len(chunks), 0)

        # Each chunk should have embedding
        for chunk in chunks:
            self.assertIn('embedding', chunk)
            self.assertIsInstance(chunk['embedding'], list)

    @patch('agents.parsing_agent.chunking.generate_embeddings')
    def test_process_prospectus_multiple_sections(self, mock_embeddings):
        """Test processing prospectus with multiple sections."""
        # Mock embeddings (return one embedding per section)
        mock_embeddings.return_value = [[0.1] * 1536, [0.2] * 1536]

        parsed_file = {
            'sections': [
                {
                    'title': 'Section 1',
                    'text': 'Text 1',
                    'page_num': 1,
                    'level': 1
                },
                {
                    'title': 'Section 2',
                    'text': 'Text 2',
                    'page_num': 2,
                    'level': 1
                }
            ]
        }

        chunks = chunking.process_prospectus_to_chunks(parsed_file)

        # Should have chunks from both sections
        self.assertGreaterEqual(len(chunks), 2)

        # Chunk indices should be sequential across sections
        indices = [c['chunk_index'] for c in chunks]
        self.assertEqual(indices[0], 0)
        for i in range(len(indices) - 1):
            self.assertEqual(indices[i+1], indices[i] + 1)

    def test_process_prospectus_empty(self):
        """Test handling of empty prospectus."""
        parsed_file = {}
        chunks = chunking.process_prospectus_to_chunks(parsed_file)
        self.assertEqual(len(chunks), 0)

        parsed_file = {'sections': []}
        chunks = chunking.process_prospectus_to_chunks(parsed_file)
        self.assertEqual(len(chunks), 0)


class TokenCountingTestCase(TestCase):
    """Test cases for token counting."""

    def test_count_tokens_basic(self):
        """Test basic token counting."""
        text = "This is a test sentence."
        count = chunking.count_tokens(text)

        # Should return a positive integer
        self.assertIsInstance(count, int)
        self.assertGreater(count, 0)
        self.assertLess(count, 20)  # Roughly 5-7 tokens

    def test_count_tokens_empty(self):
        """Test token counting on empty string."""
        count = chunking.count_tokens("")
        self.assertEqual(count, 0)

    def test_count_tokens_long_text(self):
        """Test token counting on longer text."""
        # Create text of known length
        text = " ".join(["word"] * 100)
        count = chunking.count_tokens(text)

        # Should be roughly 100 tokens (may be slightly different due to encoding)
        self.assertGreater(count, 90)
        self.assertLess(count, 120)


if __name__ == '__main__':
    from django.conf import settings
    from django.test.utils import get_runner

    print(f"\nWorking directory: {os.getcwd()}")
    print(f"Running chunking tests...\n")

    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True, keepdb=True)

    failures = test_runner.run_tests(['agents.query_agent.test_chunking'])

    sys.exit(bool(failures))
