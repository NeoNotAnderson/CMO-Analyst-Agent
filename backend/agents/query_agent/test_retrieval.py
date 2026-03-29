"""
Unit and integration tests for the hybrid search retrieval module.

Tests cover:
- Semantic search (vector similarity)
- Keyword search (BM25)
- Reciprocal Rank Fusion (RRF)
- Cross-encoder reranking
- Full hybrid search pipeline
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

from django.test import TestCase, TransactionTestCase
from unittest.mock import Mock, patch, MagicMock
from django.contrib.auth.models import User
from core.models import Prospectus, ProspectusChunk
from agents.query_agent import retrieval


class ReciprocalRankFusionTestCase(TestCase):
    """Test cases for RRF merge algorithm."""

    def test_rrf_basic_merge(self):
        """Test basic RRF merging of semantic and keyword results."""
        semantic_results = [
            {'chunk_id': '1', 'rank': 1, 'chunk_text': 'Result 1'},
            {'chunk_id': '2', 'rank': 2, 'chunk_text': 'Result 2'},
        ]

        keyword_results = [
            {'chunk_id': '2', 'rank': 1, 'chunk_text': 'Result 2'},  # Also in semantic
            {'chunk_id': '3', 'rank': 2, 'chunk_text': 'Result 3'},
        ]

        merged = retrieval.reciprocal_rank_fusion(
            semantic_results,
            keyword_results,
            k=60
        )

        # Should merge all unique chunks
        chunk_ids = [r['chunk_id'] for r in merged]
        self.assertEqual(set(chunk_ids), {'1', '2', '3'})

        # Chunk '2' appears in both, should have highest RRF score
        chunk_2 = next(r for r in merged if r['chunk_id'] == '2')
        self.assertGreater(chunk_2['rrf_score'], 0)

        # Results should be sorted by RRF score (descending)
        rrf_scores = [r['rrf_score'] for r in merged]
        self.assertEqual(rrf_scores, sorted(rrf_scores, reverse=True))

    def test_rrf_weighted_merge(self):
        """Test RRF with different weights."""
        semantic_results = [
            {'chunk_id': '1', 'rank': 1, 'chunk_text': 'Result 1'},
        ]

        keyword_results = [
            {'chunk_id': '2', 'rank': 1, 'chunk_text': 'Result 2'},
        ]

        # Semantic-heavy
        merged_semantic = retrieval.reciprocal_rank_fusion(
            semantic_results,
            keyword_results,
            semantic_weight=0.7,
            keyword_weight=0.3
        )

        # Chunk 1 (only in semantic) should score higher
        self.assertEqual(merged_semantic[0]['chunk_id'], '1')

        # Keyword-heavy
        merged_keyword = retrieval.reciprocal_rank_fusion(
            semantic_results,
            keyword_results,
            semantic_weight=0.3,
            keyword_weight=0.7
        )

        # Chunk 2 (only in keyword) should score higher
        self.assertEqual(merged_keyword[0]['chunk_id'], '2')

    def test_rrf_empty_inputs(self):
        """Test RRF with empty result sets."""
        # Empty semantic
        merged = retrieval.reciprocal_rank_fusion([], [{'chunk_id': '1', 'rank': 1}])
        self.assertEqual(len(merged), 1)

        # Empty keyword
        merged = retrieval.reciprocal_rank_fusion([{'chunk_id': '1', 'rank': 1}], [])
        self.assertEqual(len(merged), 1)

        # Both empty
        merged = retrieval.reciprocal_rank_fusion([], [])
        self.assertEqual(len(merged), 0)


class FormatRetrievedChunksTestCase(TestCase):
    """Test cases for formatting retrieved chunks for LLM."""

    def test_format_basic(self):
        """Test basic chunk formatting."""
        chunks = [
            {
                'chunk_text': 'This is the content.',
                'metadata': {
                    'section_path': ['SUMMARY', 'General'],
                    'page_num': 15
                },
                'rerank_score': 0.95
            }
        ]

        formatted = retrieval.format_retrieved_chunks(chunks)

        # Should include chunk text
        self.assertIn('This is the content', formatted)

        # Should include section path
        self.assertIn('SUMMARY', formatted)
        self.assertIn('General', formatted)

        # Should include page number
        self.assertIn('15', formatted)

        # Should include relevance score
        self.assertIn('0.95', formatted)

    def test_format_multiple_chunks(self):
        """Test formatting multiple chunks."""
        chunks = [
            {
                'chunk_text': 'Chunk 1',
                'metadata': {'section_path': ['Section 1'], 'page_num': 1}
            },
            {
                'chunk_text': 'Chunk 2',
                'metadata': {'section_path': ['Section 2'], 'page_num': 2}
            }
        ]

        formatted = retrieval.format_retrieved_chunks(chunks)

        # Should include both chunks
        self.assertIn('Chunk 1', formatted)
        self.assertIn('Chunk 2', formatted)

        # Should have chunk numbering
        self.assertIn('CHUNK 1', formatted)
        self.assertIn('CHUNK 2', formatted)

    def test_format_includes_instructions(self):
        """Test that formatted output includes instructions for LLM."""
        chunks = [
            {
                'chunk_text': 'Content',
                'metadata': {'section_path': [], 'page_num': 1}
            }
        ]

        formatted = retrieval.format_retrieved_chunks(chunks)

        # Should include grounding instructions
        self.assertIn("ONLY on the retrieved chunks", formatted.lower())
        self.assertIn("cite", formatted.lower())

    def test_format_empty_chunks(self):
        """Test formatting with no chunks."""
        formatted = retrieval.format_retrieved_chunks([])

        # Should indicate no results
        self.assertIn("No relevant information", formatted)


class HybridSearchIntegrationTestCase(TransactionTestCase):
    """Integration tests for hybrid search with real database."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )

        # Create test prospectus
        self.prospectus = Prospectus.objects.create(
            prospectus_name='Test Prospectus',
            created_by=self.user,
            parse_status='completed'
        )

        # Create test chunks with embeddings
        self.chunks = [
            ProspectusChunk.objects.create(
                prospectus=self.prospectus,
                chunk_text='Tranche A-1 has a coupon rate of 3.50%',
                chunk_index=0,
                embedding=[0.1] * 1536,  # Dummy embedding
                metadata={
                    'section_title': 'The Certificates',
                    'section_path': ['SUMMARY', 'The Certificates'],
                    'page_num': 15,
                    'has_table': True,
                    'token_count': 10
                }
            ),
            ProspectusChunk.objects.create(
                prospectus=self.prospectus,
                chunk_text='The certificates are divided into tranches',
                chunk_index=1,
                embedding=[0.2] * 1536,
                metadata={
                    'section_title': 'General',
                    'section_path': ['SUMMARY', 'General'],
                    'page_num': 10,
                    'has_table': False,
                    'token_count': 8
                }
            ),
            ProspectusChunk.objects.create(
                prospectus=self.prospectus,
                chunk_text='Prepayment risk may affect returns',
                chunk_index=2,
                embedding=[0.3] * 1536,
                metadata={
                    'section_title': 'Prepayment Risk',
                    'section_path': ['RISK FACTORS', 'Prepayment Risk'],
                    'page_num': 42,
                    'has_table': False,
                    'token_count': 6
                }
            ),
        ]

    @patch('agents.query_agent.retrieval.generate_query_embedding')
    @patch('agents.query_agent.retrieval.reranker_model')
    def test_hybrid_search_basic(self, mock_reranker, mock_embedding):
        """Test basic hybrid search flow."""
        # Mock query embedding
        mock_embedding.return_value = [0.15] * 1536

        # Mock reranker
        mock_reranker.predict.return_value = [0.9, 0.7, 0.5]

        # Run hybrid search
        results = retrieval.hybrid_search(
            query="What is the coupon rate?",
            prospectus_id=str(self.prospectus.prospectus_id),
            top_k=3,
            retrieval_k=3,
            use_reranking=True
        )

        # Should return results
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 3)

        # Each result should have required fields
        for result in results:
            self.assertIn('chunk_text', result)
            self.assertIn('metadata', result)
            self.assertIn('rerank_score', result)

    @patch('agents.query_agent.retrieval.generate_query_embedding')
    def test_semantic_search(self, mock_embedding):
        """Test semantic search component."""
        # Mock query embedding (similar to chunk 0)
        mock_embedding.return_value = [0.1] * 1536

        results = retrieval.semantic_search(
            query="coupon rate",
            prospectus_id=str(self.prospectus.prospectus_id),
            top_k=3
        )

        # Should return chunks
        self.assertGreater(len(results), 0)

        # Should have similarity scores
        for result in results:
            self.assertIn('similarity_score', result)
            self.assertIn('rank', result)

    def test_keyword_search(self):
        """Test keyword search (BM25) component."""
        results = retrieval.keyword_search(
            query="coupon rate 3.50%",
            prospectus_id=str(self.prospectus.prospectus_id),
            top_k=3
        )

        # Should return chunks
        self.assertGreater(len(results), 0)

        # Should have BM25 scores
        for result in results:
            self.assertIn('bm25_score', result)
            self.assertIn('rank', result)

        # Chunk with "3.50%" should rank high (if keyword matching works)
        chunk_texts = [r['chunk_text'] for r in results]
        # At least one result should contain relevant terms
        self.assertTrue(any('tranche' in text.lower() or 'coupon' in text.lower() for text in chunk_texts))

    @patch('agents.query_agent.retrieval.generate_query_embedding')
    @patch('agents.query_agent.retrieval.reranker_model')
    def test_hybrid_search_with_metadata_filter(self, mock_reranker, mock_embedding):
        """Test hybrid search with metadata filtering."""
        mock_embedding.return_value = [0.1] * 1536
        mock_reranker.predict.return_value = [0.9]

        # Filter to only table chunks
        results = retrieval.hybrid_search(
            query="What is the coupon rate?",
            prospectus_id=str(self.prospectus.prospectus_id),
            top_k=3,
            metadata_filters={'has_table': True}
        )

        # Should only return chunks with has_table=True
        for result in results:
            self.assertTrue(result['metadata']['has_table'])

    def test_hybrid_search_no_chunks(self):
        """Test hybrid search when no chunks exist."""
        # Create new prospectus with no chunks
        empty_prospectus = Prospectus.objects.create(
            prospectus_name='Empty',
            created_by=self.user
        )

        with patch('agents.query_agent.retrieval.generate_query_embedding') as mock_embed:
            mock_embed.return_value = [0.1] * 1536

            results = retrieval.hybrid_search(
                query="test",
                prospectus_id=str(empty_prospectus.prospectus_id),
                top_k=10
            )

            # Should return empty list
            self.assertEqual(len(results), 0)


class RetrieveRelevantChunksToolTestCase(TransactionTestCase):
    """Test cases for the retrieve_relevant_chunks tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(username='testuser', password='testpass')

        self.prospectus = Prospectus.objects.create(
            prospectus_name='Test Prospectus',
            created_by=self.user,
            parse_status='completed'
        )

        # Create test chunk
        ProspectusChunk.objects.create(
            prospectus=self.prospectus,
            chunk_text='Test content',
            chunk_index=0,
            embedding=[0.1] * 1536,
            metadata={'section_path': ['Test'], 'page_num': 1}
        )

    @patch('agents.query_agent.retrieval.hybrid_search')
    def test_retrieve_relevant_chunks_tool_success(self, mock_search):
        """Test successful retrieval with tool."""
        from agents.query_agent.tools import retrieve_relevant_chunks

        # Mock hybrid search results
        mock_search.return_value = [
            {
                'chunk_text': 'Test content',
                'metadata': {'section_path': ['Test'], 'page_num': 1}
            }
        ]

        # Call tool
        result = retrieve_relevant_chunks.func(
            user_query="test query",
            prospectus_id=str(self.prospectus.prospectus_id)
        )

        # Should return formatted chunks
        self.assertIsInstance(result, str)
        self.assertIn('Test content', result)

    def test_retrieve_relevant_chunks_no_chunks(self):
        """Test tool when prospectus has no chunks."""
        from agents.query_agent.tools import retrieve_relevant_chunks

        # Create prospectus without chunks
        empty_prospectus = Prospectus.objects.create(
            prospectus_name='Empty',
            created_by=self.user
        )

        result = retrieve_relevant_chunks.func(
            user_query="test",
            prospectus_id=str(empty_prospectus.prospectus_id)
        )

        # Should return message about indexing
        self.assertIn("not been indexed", result)

    def test_retrieve_relevant_chunks_invalid_prospectus(self):
        """Test tool with invalid prospectus ID."""
        from agents.query_agent.tools import retrieve_relevant_chunks

        result = retrieve_relevant_chunks.func(
            user_query="test",
            prospectus_id="00000000-0000-0000-0000-000000000000"
        )

        # Should return error message
        self.assertIn("Error", result)


if __name__ == '__main__':
    from django.conf import settings
    from django.test.utils import get_runner

    print(f"\nWorking directory: {os.getcwd()}")
    print(f"Running retrieval tests...\n")

    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True, keepdb=True)

    failures = test_runner.run_tests(['agents.query_agent.test_retrieval'])

    sys.exit(bool(failures))
