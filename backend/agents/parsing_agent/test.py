"""
Test methods for parsing_agent tools.
"""
import sys
import os

# Set up Django BEFORE imports if running as main script
if __name__ == '__main__':
    # Get the backend directory
    current_file = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

    # Add to path and setup Django
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    os.chdir(backend_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    import django
    django.setup()

from django.test import TestCase, TransactionTestCase
from unittest.mock import Mock, patch, MagicMock, call
from core.models import Prospectus
import json


class ParseIndexPagesTestCase(TestCase):
    """Test cases for parse_index_pages function."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock prospectus object
        self.mock_prospectus = Mock(spec=Prospectus)
        self.mock_prospectus.prospectus_name = "Test CMO 2024-1 Supplement.pdf"
        self.mock_prospectus.parsed_index = None
        self.mock_prospectus.index_page_numbers = None

        # Sample parsed index structure
        self.sample_parsed_index = {
            "sections": [
                {
                    "title": "RISK FACTORS",
                    "page": "S-12",
                    "level": 1,
                    "sections": []
                },
                {
                    "title": "DESCRIPTION OF CERTIFICATES",
                    "page": "S-25",
                    "level": 1,
                    "sections": [
                        {
                            "title": "General",
                            "page": "S-26",
                            "level": 2,
                            "sections": []
                        }
                    ]
                }
            ]
        }

    @patch('agents.parsing_agent.tools.find_index_pages')
    @patch('agents.parsing_agent.tools.parsed_pages_exist_in_db')
    @patch('agents.parsing_agent.tools.retrieve_parsed_pages_from_db')
    def test_parse_index_pages_cached_in_db(
        self,
        mock_retrieve,
        mock_exists,
        mock_find
    ):
        """Test parse_index_pages when index pages are already cached in database."""
        from agents.parsing_agent import tools
        parse_index_pages = tools.parse_index_pages.func

        # Setup mocks
        mock_find.return_value = [0, 1]
        mock_exists.return_value = True
        mock_retrieve.return_value = self.sample_parsed_index

        # Call function
        result = parse_index_pages(self.mock_prospectus)

        # Verify behavior
        mock_find.assert_called_once()
        mock_exists.assert_called_once_with([0, 1], self.mock_prospectus)
        mock_retrieve.assert_called_once_with(self.mock_prospectus, [0, 1])
        self.assertEqual(result, self.sample_parsed_index)

    @patch('agents.parsing_agent.tools.find_index_pages')
    @patch('agents.parsing_agent.tools.parsed_pages_exist_in_db')
    @patch('agents.parsing_agent.tools.convert_pages_to_images')
    @patch('agents.parsing_agent.tools.parse_page_images_with_openai')
    def test_parse_index_pages_new_parsing(
        self,
        mock_parse_openai,
        mock_convert,
        mock_exists,
        mock_find
    ):
        """Test parse_index_pages when parsing is needed (not in cache)."""
        from agents.parsing_agent import tools
        parse_index_pages = tools.parse_index_pages.func

        # Setup mocks
        mock_find.return_value = [0, 1]
        mock_exists.return_value = False

        sample_images = [
            {'page_num': 0, 'image': 'base64_image_data_1'},
            {'page_num': 1, 'image': 'base64_image_data_2'}
        ]
        mock_convert.return_value = sample_images
        mock_parse_openai.return_value = self.sample_parsed_index

        # Call function (returns None, but updates prospectus object)
        result = parse_index_pages(self.mock_prospectus)

        # Verify behavior
        mock_find.assert_called_once()
        mock_exists.assert_called_once_with([0, 1], self.mock_prospectus)
        mock_convert.assert_called_once_with(self.mock_prospectus, [0, 1])

        # Verify parse_page_images_with_openai was called with images and build_prompt function
        from agents.parsing_agent.tools import build_prompt_for_index_parsing
        mock_parse_openai.assert_called_once_with(sample_images, build_prompt_for_index_parsing)

        # Verify prospectus was updated and saved
        self.assertEqual(self.mock_prospectus.parsed_index, self.sample_parsed_index)
        self.mock_prospectus.save.assert_called_once()

        # Function should return None when parsing new pages
        self.assertIsNone(result)

    @patch('agents.parsing_agent.tools.find_index_pages')
    def test_parse_index_pages_no_index_found(self, mock_find):
        """Test parse_index_pages when no index pages are found in document."""
        from agents.parsing_agent import tools
        parse_index_pages = tools.parse_index_pages.func

        # Setup mock to return empty list
        mock_find.return_value = []

        # Verify ValueError is raised
        with self.assertRaises(ValueError) as context:
            parse_index_pages(self.mock_prospectus)

        self.assertEqual(str(context.exception), "Could not locate index page")

    @patch('agents.parsing_agent.tools.determin_doc_type')
    @patch('agents.parsing_agent.tools.find_index_pages')
    @patch('agents.parsing_agent.tools.parsed_pages_exist_in_db')
    @patch('agents.parsing_agent.tools.convert_pages_to_images')
    @patch('agents.parsing_agent.tools.parse_page_images_with_openai')
    def test_parse_index_pages_supplement_document(
        self,
        mock_parse_openai,
        mock_convert,
        mock_exists,
        mock_find,
        mock_determin_type
    ):
        """Test parse_index_pages correctly identifies supplement document type."""
        from agents.parsing_agent import tools
        parse_index_pages = tools.parse_index_pages.func

        # Setup mocks
        self.mock_prospectus.prospectus_name = "CMO 2024-1 Supplement.pdf"
        mock_determin_type.return_value = "supplement"
        mock_find.return_value = [0, 1]
        mock_exists.return_value = False
        mock_convert.return_value = [{'page_num': 0, 'image': 'data'}]
        mock_parse_openai.return_value = self.sample_parsed_index

        # Call function
        parse_index_pages(self.mock_prospectus)

        # Verify doc_type determination
        mock_determin_type.assert_called_once_with(self.mock_prospectus.prospectus_name)
        mock_find.assert_called_once_with(self.mock_prospectus, "supplement")

    @patch('agents.parsing_agent.tools.determin_doc_type')
    @patch('agents.parsing_agent.tools.find_index_pages')
    @patch('agents.parsing_agent.tools.parsed_pages_exist_in_db')
    @patch('agents.parsing_agent.tools.convert_pages_to_images')
    @patch('agents.parsing_agent.tools.parse_page_images_with_openai')
    def test_parse_index_pages_prospectus_document(
        self,
        mock_parse_openai,
        mock_convert,
        mock_exists,
        mock_find,
        mock_determin_type
    ):
        """Test parse_index_pages correctly identifies prospectus document type."""
        from agents.parsing_agent import tools
        parse_index_pages = tools.parse_index_pages.func

        # Setup mocks
        self.mock_prospectus.prospectus_name = "CMO 2024-1 Prospectus.pdf"
        mock_determin_type.return_value = "prospectus"
        mock_find.return_value = [0, 1]
        mock_exists.return_value = False
        mock_convert.return_value = [{'page_num': 0, 'image': 'data'}]
        mock_parse_openai.return_value = self.sample_parsed_index

        # Call function
        parse_index_pages(self.mock_prospectus)

        # Verify doc_type determination
        mock_determin_type.assert_called_once_with(self.mock_prospectus.prospectus_name)
        mock_find.assert_called_once_with(self.mock_prospectus, "prospectus")

    @patch('agents.parsing_agent.tools.find_index_pages')
    @patch('agents.parsing_agent.tools.parsed_pages_exist_in_db')
    @patch('agents.parsing_agent.tools.convert_pages_to_images')
    @patch('agents.parsing_agent.tools.parse_page_images_with_openai')
    @patch('agents.parsing_agent.tools.build_prompt_for_index_parsing')
    def test_parse_index_pages_uses_correct_prompt_builder(
        self,
        mock_build_prompt,
        mock_parse_openai,
        mock_convert,
        mock_exists,
        mock_find
    ):
        """Test parse_index_pages passes correct prompt builder to OpenAI parser."""
        from agents.parsing_agent import tools
        parse_index_pages = tools.parse_index_pages.func

        # Setup mocks
        mock_find.return_value = [0, 1]
        mock_exists.return_value = False
        sample_images = [{'page_num': 0, 'image': 'data'}]
        mock_convert.return_value = sample_images
        mock_parse_openai.return_value = self.sample_parsed_index

        # Call function
        parse_index_pages(self.mock_prospectus)

        # Verify parse_page_images_with_openai was called with build_prompt_for_index_parsing
        mock_parse_openai.assert_called_once()
        args = mock_parse_openai.call_args[0]
        self.assertEqual(args[0], sample_images)
        # Second argument should be the build_prompt_for_index_parsing function
        from agents.parsing_agent.tools import build_prompt_for_index_parsing
        self.assertEqual(args[1], build_prompt_for_index_parsing)


class ParseIndexPagesIntegrationTestCase(TestCase):
    """Integration tests for parse_index_pages with real files and API calls."""

    def setUp(self):
        """Set up test fixtures with real file paths."""
        import os
        from django.contrib.auth.models import User

        print(f"\n{'='*60}")
        print("setUp() is running - this happens before EACH test method")
        print(f"{'='*60}")

        # Create a test user for Prospectus.created_by field
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        print(f"✓ Created test user: {self.test_user.username}")

        # Get the directory where this test file is located
        test_dir = os.path.dirname(os.path.abspath(__file__))
        test_data_dir = os.path.join(test_dir, 'test_data')

        # Look for any PDF file in test_data directory
        self.test_pdf_path = None
        self.test_pdf_name = None
        if os.path.exists(test_data_dir):
            pdf_files = [f for f in os.listdir(test_data_dir) if f.endswith('.pdf')]
            if pdf_files:
                # Use the first PDF file found
                self.test_pdf_name = pdf_files[0]
                self.test_pdf_path = os.path.join(test_data_dir, self.test_pdf_name)
                print(f"✓ Found PDF: {self.test_pdf_name}")

        # Fallback to specific file if it exists
        if not self.test_pdf_path:
            fallback_path = os.path.join(test_dir, 'test_data', 'JPM03_supplement.pdf')
            if os.path.exists(fallback_path):
                self.test_pdf_path = fallback_path
                self.test_pdf_name = 'JPM03_supplement.pdf'
                print(f"✓ Using fallback PDF: {self.test_pdf_name}")

        if not self.test_pdf_path:
            print("✗ No PDF found in test_data/")

    def test_parse_index_pages_with_real_pdf(self):
        """
        Integration test: Parse a real CMO prospectus PDF and verify results.

        Note: This test requires:
        1. A real PDF file in test_data/ directory
        2. Valid OpenAI API key in environment
        3. Active database connection

        Skip this test if these requirements aren't met.
        """
        import os
        from django.core.files import File
        from agents.parsing_agent import tools
        parse_index_pages = tools.parse_index_pages.func

        # Skip test if PDF file doesn't exist
        if not self.test_pdf_path or not os.path.exists(self.test_pdf_path):
            self.skipTest(f"Test PDF not found. Please add a PDF file to test_data/ directory")

        # Skip test if API key not available
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not found in environment")

        print(f"\n{'='*60}")
        print(f"Running integration test with: {self.test_pdf_name}")
        print(f"{'='*60}")

        # Create a real Prospectus object in test database
        with open(self.test_pdf_path, 'rb') as pdf_file:
            prospectus = Prospectus.objects.create(
                prospectus_name=self.test_pdf_name,
                prospectus_file=File(pdf_file, name=self.test_pdf_name),
                created_by=self.test_user
            )

        try:
            # Call parse_index_pages without mocks - uses real implementations
            parse_index_pages(prospectus)

            # Reload from database to get updated values
            prospectus.refresh_from_db()

            # Verify structure exists
            self.assertIsNotNone(prospectus.parsed_index)
            self.assertIn('sections', prospectus.parsed_index)

            # Verify sections were parsed
            sections = prospectus.parsed_index['sections']
            self.assertGreater(len(sections), 0, "Should have at least one section")

            # Verify section structure
            first_section = sections[0]
            self.assertIn('title', first_section)
            self.assertIn('page', first_section)
            self.assertIn('level', first_section)
            self.assertIn('sections', first_section)

            # Verify section values are not empty
            self.assertTrue(first_section['title'], "Section title should not be empty")
            self.assertTrue(first_section['page'], "Section page should not be empty")
            self.assertEqual(first_section['level'], 1, "Top-level sections should have level 1")

            # Verify page format (should be like "S-12" or "I-5")
            self.assertRegex(
                first_section['page'],
                r'^[A-Z]-\d+$',
                "Page number should match format like 'S-12' or 'I-5'"
            )

            # Verify index_page_numbers was stored
            self.assertIsNotNone(prospectus.index_page_numbers)
            self.assertGreater(len(prospectus.index_page_numbers), 0)

            print(f"\n✓ Successfully parsed {len(sections)} top-level sections")
            print(f"✓ First section: {first_section['title']} (page {first_section['page']})")

        finally:
            # Clean up: delete test prospectus from database
            prospectus.delete()

    def test_parse_index_pages_caching(self):
        """
        Integration test: Verify that parsed index is cached in database.

        This test verifies that:
        1. First call parses and stores in DB
        2. Second call retrieves from DB without re-parsing
        """
        import os
        from django.core.files import File
        from unittest.mock import patch
        from agents.parsing_agent import tools
        parse_index_pages = tools.parse_index_pages.func

        # Skip if requirements not met
        if not self.test_pdf_path or not os.path.exists(self.test_pdf_path):
            self.skipTest(f"Test PDF not found. Please add a PDF file to test_data/ directory")
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not found in environment")

        # Create prospectus
        with open(self.test_pdf_path, 'rb') as pdf_file:
            prospectus = Prospectus.objects.create(
                prospectus_name=self.test_pdf_name,
                prospectus_file=File(pdf_file, name=self.test_pdf_name),
                created_by=self.test_user
            )

        try:
            # First call - should parse and cache
            parse_index_pages(prospectus)
            prospectus.refresh_from_db()
            cached_result = prospectus.parsed_index

            # Verify it was cached
            self.assertIsNotNone(cached_result)

            # Second call - should retrieve from cache
            # Mock parse_page_images_with_openai to verify it's NOT called
            with patch('agents.parsing_agent.tools.parse_page_images_with_openai') as mock_parse:
                result = parse_index_pages(prospectus)

                # Should return cached result
                self.assertEqual(result, cached_result)

                # OpenAI parsing should NOT have been called
                mock_parse.assert_not_called()

            print("\n✓ Caching working correctly - second call retrieved from DB")

        finally:
            # Clean up
            prospectus.delete()

    def test_parse_prospectus_with_parsed_index_integration(self):
        """
        Integration test: Parse full prospectus using the parsed index structure.

        This test verifies:
        1. Index is parsed first
        2. Full prospectus is parsed section by section
        3. Text and tables are extracted
        4. Results are stored in database

        Note: This test requires:
        - Real PDF file in test_data/
        - Valid OpenAI API key
        - Active database connection
        - This test may take several minutes to complete
        """
        import os
        from django.core.files import File

        # Skip if requirements not met
        if not self.test_pdf_path or not os.path.exists(self.test_pdf_path):
            self.skipTest(f"Test PDF not found. Please add a PDF file to test_data/ directory")
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not found in environment")

        print(f"\n{'='*60}")
        print(f"Running full prospectus parsing test with: {self.test_pdf_name}")
        print(f"WARNING: This test may take several minutes")
        print(f"{'='*60}")

        # Create prospectus
        with open(self.test_pdf_path, 'rb') as pdf_file:
            prospectus = Prospectus.objects.create(
                prospectus_name=self.test_pdf_name,
                prospectus_file=File(pdf_file, name=self.test_pdf_name),
                created_by=self.test_user
            )

        try:
            # Step 1: Load parsed index and parsed pages from JSON files
            print(f"\n📑 Step 1: Loading parsed data from test_data folder...")

            test_dir = os.path.dirname(os.path.abspath(__file__))
            test_data_dir = os.path.join(test_dir, 'test_data')

            # 1a. Load parsed index from JSON file
            parsed_index_path = os.path.join(test_data_dir, 'parsed_index.json')

            if not os.path.exists(parsed_index_path):
                self.skipTest(f"parsed_index.json not found at {parsed_index_path}")

            with open(parsed_index_path, 'r') as f:
                parsed_index_data = json.load(f)

            # Store parsed_index in prospectus
            prospectus.parsed_index = parsed_index_data

            # 1b. Load all parsed pages from page_*.json files
            import glob
            page_files = glob.glob(os.path.join(test_data_dir, 'page_*.json'))
            page_files.sort()  # Sort to process in order

            if not page_files:
                print(f"⚠ Warning: No page_*.json files found in {test_data_dir}")
                parsed_pages = []
            else:
                # Load all parsed pages
                parsed_pages = []
                for page_file in page_files:
                    with open(page_file, 'r') as f:
                        page_data = json.load(f)
                        # page_data is a list of sections from this page
                        parsed_pages.append(page_data)
                            
                print(f"✓ Loaded {len(page_files)} page files with {len(parsed_pages)} total sections")

            # Store parsed_pages in prospectus
            prospectus.parsed_pages = parsed_pages

            # Save to database
            prospectus.save()
            prospectus.refresh_from_db()

            # Verify both were loaded
            self.assertIsNotNone(prospectus.parsed_index)
            self.assertIn('sections', prospectus.parsed_index)
            index_sections = prospectus.parsed_index['sections']
            self.assertGreater(len(index_sections), 0, "Index should have at least one section")

            print(f"✓ Parsed index loaded: {len(index_sections)} top-level sections")
            for i, section in enumerate(index_sections[:3]):  # Show first 3
                print(f"  Section {i+1}: {section.get('title')} (page {section.get('page')})")

            # Step 2: Parse full prospectus using the index
            print(f"\n📄 Step 2: Parsing full prospectus (this will take time)...")

            from agents.parsing_agent import tools
            parse_prospectus_func = tools.parse_prospectus_with_parsed_index.func

            result = parse_prospectus_func(prospectus)

            # Save result to test_data folder
            output_path = os.path.join(test_data_dir, 'parsed_supplement.json')
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=4)
            print(f"\n✓ Saved parsed result to: {output_path}")

            prospectus.refresh_from_db()

            # Verify parsing results
            self.assertIsNotNone(result)
            self.assertIn('sections', result)

            # Verify parsed_file was updated
            self.assertIsNotNone(prospectus.parsed_file)
            self.assertEqual(prospectus.parsed_file, result)

            # Verify sections have been populated with content
            parsed_sections = result['sections']
            self.assertGreater(len(parsed_sections), 0)

            # Check that at least some sections have text content
            sections_with_text = [s for s in parsed_sections if s.get('text')]
            print(f"\n✓ Prospectus parsed: {len(parsed_sections)} total sections")
            print(f"✓ Sections with text content: {len(sections_with_text)}")

            # Verify structure of first section with content
            if sections_with_text:
                first_section = sections_with_text[0]
                self.assertIn('title', first_section)
                self.assertIn('text', first_section)
                self.assertIn('page', first_section)
                self.assertTrue(len(first_section['text']) > 0, "Section should have text content")

                print(f"\n📖 First section sample:")
                print(f"  Title: {first_section['title']}")
                print(f"  Page: {first_section['page']}")
                print(f"  Text length: {len(first_section['text'])} characters")
                print(f"  Text preview: {first_section['text'][:200]}...")

            # Verify parsed_pages were stored
            if prospectus.parsed_pages:
                print(f"\n✓ Parsed pages stored: {len(prospectus.parsed_pages)} pages")

            print(f"\n{'='*60}")
            print(f"✅ Full prospectus parsing completed successfully!")
            print(f"{'='*60}")

        finally:
            # Clean up
            prospectus.delete()


class RunAgentTestCase(TestCase):
    """Test cases for run_agent function."""

    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth.models import User

        # Create test user
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )

        # Create mock prospectus
        self.mock_prospectus = Mock(spec=Prospectus)
        self.mock_prospectus.prospectus_id = "test-123"
        self.mock_prospectus.prospectus_name = "Test CMO 2024-1.pdf"

    @patch('agents.parsing_agent.graph.create_parsing_graph')
    def test_run_agent_creates_correct_initial_state(self, mock_create_graph):
        """Test that run_agent creates correct initial state with system and user messages."""
        from agents.parsing_agent.graph import run_agent
        from langchain_core.messages import HumanMessage, SystemMessage

        # Setup mock graph
        mock_graph = Mock()
        mock_graph.invoke.return_value = {"messages": [], "prospectus": self.mock_prospectus}
        mock_create_graph.return_value = mock_graph

        # Call run_agent
        run_agent(self.mock_prospectus)

        # Verify invoke was called once
        mock_graph.invoke.assert_called_once()

        # Get the state passed to invoke
        call_args = mock_graph.invoke.call_args[0][0]

        # Verify state structure
        self.assertIn('prospectus', call_args)
        self.assertIn('messages', call_args)
        self.assertIn('errors', call_args)

        # Verify prospectus
        self.assertEqual(call_args['prospectus'], self.mock_prospectus)

        # Verify messages
        messages = call_args['messages']
        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIsInstance(messages[1], HumanMessage)

        # Verify system message contains prospectus info
        system_content = messages[0].content
        self.assertIn(self.mock_prospectus.prospectus_id, system_content)
        self.assertIn(self.mock_prospectus.prospectus_name, system_content)

        # Verify user message contains task
        user_content = messages[1].content
        self.assertIn(self.mock_prospectus.prospectus_id, user_content)
        self.assertIn("parse", user_content.lower())

    @patch('agents.parsing_agent.graph.create_parsing_graph')
    def test_run_agent_returns_graph_output(self, mock_create_graph):
        """Test that run_agent returns the output from the graph execution."""
        from agents.parsing_agent.graph import run_agent

        # Setup mock graph with expected output
        expected_output = {
            "messages": ["message1", "message2"],
            "prospectus": self.mock_prospectus,
            "errors": []
        }
        mock_graph = Mock()
        mock_graph.invoke.return_value = expected_output
        mock_create_graph.return_value = mock_graph

        # Call run_agent
        result = run_agent(self.mock_prospectus)

        # Verify result matches expected output
        self.assertEqual(result, expected_output)

    @patch('agents.parsing_agent.graph.create_parsing_graph')
    def test_run_agent_initializes_empty_errors_list(self, mock_create_graph):
        """Test that run_agent initializes errors as empty list."""
        from agents.parsing_agent.graph import run_agent

        mock_graph = Mock()
        mock_graph.invoke.return_value = {}
        mock_create_graph.return_value = mock_graph

        # Call run_agent
        run_agent(self.mock_prospectus)

        # Get the state passed to invoke
        call_args = mock_graph.invoke.call_args[0][0]

        # Verify errors is empty list
        self.assertEqual(call_args['errors'], [])


class RunAgentIntegrationTestCase(TransactionTestCase):
    """Integration tests for run_agent function with real execution.

    Uses TransactionTestCase instead of TestCase to ensure database commits
    are visible to tools running in the agent. This is necessary because
    LangChain tools may run in different contexts and need to see committed data.
    """

    def setUp(self):
        """Set up test fixtures with real file paths."""
        import os
        from django.contrib.auth.models import User

        print(f"\n{'='*60}")
        print("setUp() is running - this happens before EACH test method")
        print(f"{'='*60}")

        # Create a test user for Prospectus.created_by field
        self.test_user = User.objects.create_user(
            username='testuser_agent',
            email='test@example.com',
            password='testpassword'
        )
        print(f"✓ Created test user: {self.test_user.username}")

        # Get the directory where this test file is located
        test_dir = os.path.dirname(os.path.abspath(__file__))
        test_data_dir = os.path.join(test_dir, 'test_data')

        # Look for any PDF file in test_data directory
        self.test_pdf_path = None
        self.test_pdf_name = None
        if os.path.exists(test_data_dir):
            pdf_files = [f for f in os.listdir(test_data_dir) if f.endswith('.pdf')]
            if pdf_files:
                # Use the first PDF file found
                self.test_pdf_name = pdf_files[0]
                self.test_pdf_path = os.path.join(test_data_dir, self.test_pdf_name)
                print(f"✓ Found PDF: {self.test_pdf_name}")

        # Fallback to specific file if it exists
        if not self.test_pdf_path:
            fallback_path = os.path.join(test_dir, 'test_data', 'JPM03_supplement.pdf')
            if os.path.exists(fallback_path):
                self.test_pdf_path = fallback_path
                self.test_pdf_name = 'JPM03_supplement.pdf'
                print(f"✓ Using fallback PDF: {self.test_pdf_name}")

        if not self.test_pdf_path:
            print("✗ No PDF found in test_data/")

    def test_run_agent_with_real_prospectus(self):
        """
        Integration test: Run the agent with a real prospectus and verify parsing completes.

        This test verifies:
        1. Agent can be invoked successfully
        2. Agent calls parse_index_pages tool
        3. Agent calls parse_prospectus_with_parsed_index tool
        4. Prospectus is fully parsed and stored in database
        5. Final state contains expected data

        Note: This test requires:
        - Real PDF file in test_data/
        - Valid OpenAI API key
        - Active database connection
        - This test may take several minutes to complete
        """
        import os
        import json
        import logging
        from django.core.files import File
        from agents.parsing_agent.graph import run_agent
        import langchain
        from langchain_core.callbacks.base import BaseCallbackHandler

        # Create a custom callback handler to allow stopping execution
        class StoppableCallbackHandler(BaseCallbackHandler):
            """Callback handler that allows stopping execution at runtime."""

            def __init__(self):
                self.should_stop = False
                self.step_count = 0

            def on_tool_start(self, serialized, input_str, **kwargs):
                """Called when a tool starts executing."""
                self.step_count += 1
                tool_name = serialized.get('name', 'unknown')
                print(f"\n[Step {self.step_count}] 🔧 Tool starting: {tool_name}")

                # You can set breakpoint here to pause execution
                # Or check self.should_stop flag
                if self.should_stop:
                    raise KeyboardInterrupt("Execution stopped by user")

            def on_tool_end(self, output, **kwargs):
                """Called when a tool finishes executing."""
                print(f"[Step {self.step_count}] ✓ Tool completed")

        # Set up logging to file
        test_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(test_dir, 'test_data', 'agent_execution.log')

        # Configure logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='w'),  # Write to file
                logging.StreamHandler()  # Also print to console
            ]
        )

        # Create callback handler
        callback_handler = StoppableCallbackHandler()

        # Enable debug mode to see tool calls and agent reasoning
        langchain.debug = True
        langchain.verbose = True

        print(f"📝 Logging agent execution to: {log_file}")
        print(f"💡 Tip: Set a breakpoint in StoppableCallbackHandler.on_tool_start() to pause execution")

        # Skip if requirements not met
        if not self.test_pdf_path or not os.path.exists(self.test_pdf_path):
            self.skipTest(f"Test PDF not found. Please add a PDF file to test_data/ directory")
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not found in environment")

        print(f"\n{'='*60}")
        print(f"Running agent integration test with: {self.test_pdf_name}")
        print(f"WARNING: This test may take several minutes")
        print(f"{'='*60}")

        # Create a real Prospectus object in test database
        with open(self.test_pdf_path, 'rb') as pdf_file:
            prospectus = Prospectus.objects.create(
                prospectus_name=self.test_pdf_name,
                prospectus_file=File(pdf_file, name=self.test_pdf_name),
                created_by=self.test_user
            )

        print(f"✓ Created prospectus in database:")
        print(f"  ID: {prospectus.prospectus_id}")
        print(f"  ID Type: {type(prospectus.prospectus_id)}")
        print(f"  ID as String: {str(prospectus.prospectus_id)}")
        print(f"  Name: {prospectus.prospectus_name}")
        print(f"  File: {prospectus.prospectus_file.name if prospectus.prospectus_file else 'None'}")

        # Verify it's actually saved
        prospectus.refresh_from_db()
        print(f"✓ Verified prospectus exists in database")

        # Test if we can retrieve it by ID
        try:
            test_lookup = Prospectus.objects.get(prospectus_id=prospectus.prospectus_id)
            print(f"✓ Successfully retrieved prospectus by UUID object")
        except Prospectus.DoesNotExist:
            print(f"✗ ERROR: Cannot retrieve prospectus by UUID object")

        try:
            test_lookup_str = Prospectus.objects.get(prospectus_id=str(prospectus.prospectus_id))
            print(f"✓ Successfully retrieved prospectus by UUID string")
        except Prospectus.DoesNotExist:
            print(f"✗ ERROR: Cannot retrieve prospectus by UUID string")

        # Load and save parsed pages (page 10 to 41) from test_data folder
        print(f"\n📑 Loading parsed pages from test_data folder...")
        test_dir = os.path.dirname(os.path.abspath(__file__))
        test_data_dir = os.path.join(test_dir, 'test_data')

        parsed_pages = []
        loaded_count = 0
        for page_num in range(10, 42):  # 10 to 41 inclusive
            page_file_path = os.path.join(test_data_dir, f'page_{page_num}.json')
            if os.path.exists(page_file_path):
                try:
                    with open(page_file_path, 'r') as f:
                        page_data = json.load(f)
                        parsed_pages.append(page_data)
                        loaded_count += 1
                except Exception as e:
                    print(f"⚠ Warning: Failed to load {page_file_path}: {e}")
            else:
                print(f"⚠ Warning: {page_file_path} not found")

        if loaded_count > 0:
            prospectus.parsed_pages = parsed_pages
            prospectus.save()
            print(f"✓ Loaded and saved {loaded_count} parsed pages to database")

            # Verify parsed pages were saved
            prospectus.refresh_from_db()
            if prospectus.parsed_pages:
                print(f"✓ Verified: parsed_pages field contains {len(prospectus.parsed_pages)} items")
            else:
                print(f"⚠ Warning: parsed_pages field is empty after save")
        else:
            print(f"⚠ No parsed pages found, continuing without them")

        try:
            # Run the agent with callback handler
            print(f"\n🤖 Running agent...")
            print(f"⏸️  To pause: Set breakpoint at line 775 (on_tool_start method)")
            print(f"🛑 To stop: In debugger, set callback_handler.should_stop = True\n")

            # Pass callback handler to run_agent
            config = {"callbacks": [callback_handler]}
            result = run_agent(prospectus, config=config)

            # Disable debug mode
            langchain.debug = False
            langchain.verbose = False

            print(f"✓ Agent execution log saved to: {log_file}")

            # Verify result structure
            self.assertIsNotNone(result)
            self.assertIn('messages', result)
            self.assertIn('prospectus', result)
            self.assertIn('errors', result)

            print(f"\n✓ Agent completed with {len(result['messages'])} messages")

            # Print tool call summary
            print(f"\n🔧 Tool Call Summary:")
            from langchain_core.messages import ToolMessage, AIMessage
            tool_calls_made = []
            for msg in result['messages']:
                if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_calls_made.append(tool_call['name'])

            if tool_calls_made:
                for i, tool_name in enumerate(tool_calls_made, 1):
                    print(f"  {i}. {tool_name}")
            else:
                print(f"  No tool calls found")

            # Verify no errors occurred
            if result['errors']:
                print(f"\n⚠ Errors encountered: {result['errors']}")

            # Reload prospectus from database to verify updates
            prospectus.refresh_from_db()

            # Verify parsed_index was created
            self.assertIsNotNone(prospectus.parsed_index, "Agent should have parsed the index")
            self.assertIn('sections', prospectus.parsed_index)
            index_sections = prospectus.parsed_index['sections']
            self.assertGreater(len(index_sections), 0, "Index should have at least one section")

            print(f"✓ Parsed index created: {len(index_sections)} top-level sections")

            # Verify parsed_file was created
            self.assertIsNotNone(prospectus.parsed_file, "Agent should have parsed the full prospectus")
            self.assertIn('sections', prospectus.parsed_file)
            parsed_sections = prospectus.parsed_file['sections']
            self.assertGreater(len(parsed_sections), 0, "Parsed file should have at least one section")

            print(f"✓ Full prospectus parsed: {len(parsed_sections)} sections")

            # Verify at least some sections have text content
            sections_with_text = [s for s in parsed_sections if s.get('text')]
            self.assertGreater(len(sections_with_text), 0, "At least some sections should have text")

            print(f"✓ Sections with text content: {len(sections_with_text)}")

            print(f"\n{'='*60}")
            print(f"✅ Agent integration test completed successfully!")
            print(f"{'='*60}")

        finally:
            # Clean up: delete test prospectus from database
            prospectus.delete()

    def test_run_agent_messages_and_tool_calls(self):
        """
        Integration test: Verify agent generates correct message flow and tool calls.

        This test verifies:
        1. Agent generates messages in expected order
        2. Agent makes tool calls for parsing
        3. Messages contain tool call results
        """
        import os
        from django.core.files import File
        from agents.parsing_agent.graph import run_agent
        from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage

        # Skip if requirements not met
        if not self.test_pdf_path or not os.path.exists(self.test_pdf_path):
            self.skipTest(f"Test PDF not found. Please add a PDF file to test_data/ directory")
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not found in environment")

        print(f"\n{'='*60}")
        print(f"Testing agent message flow with: {self.test_pdf_name}")
        print(f"{'='*60}")

        # Create prospectus
        with open(self.test_pdf_path, 'rb') as pdf_file:
            prospectus = Prospectus.objects.create(
                prospectus_name=self.test_pdf_name,
                prospectus_file=File(pdf_file, name=self.test_pdf_name),
                created_by=self.test_user
            )
            prospectus.save()

        try:
            # Run the agent
            result = run_agent(prospectus)

            # Verify messages list
            messages = result['messages']
            self.assertGreater(len(messages), 2, "Should have system, user, and agent messages")

            # First message should be SystemMessage
            self.assertIsInstance(messages[0], SystemMessage, "First message should be SystemMessage")

            # Second message should be HumanMessage
            self.assertIsInstance(messages[1], HumanMessage, "Second message should be HumanMessage")

            # Should contain at least one AIMessage with tool calls
            ai_messages = [m for m in messages if isinstance(m, AIMessage)]
            self.assertGreater(len(ai_messages), 0, "Should have at least one AI message")

            # Should contain ToolMessages (results of tool calls)
            tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
            self.assertGreater(len(tool_messages), 0, "Should have tool call results")

            print(f"\n✓ Message flow verified:")
            print(f"  Total messages: {len(messages)}")
            print(f"  AI messages: {len(ai_messages)}")
            print(f"  Tool messages: {len(tool_messages)}")

            # Verify tool calls were made
            has_parse_index = False
            has_parse_prospectus = False

            for msg in tool_messages:
                if 'parse_index' in msg.name.lower():
                    has_parse_index = True
                if 'parse_prospectus' in msg.name.lower():
                    has_parse_prospectus = True

            self.assertTrue(has_parse_index, "Should have called parse_index_pages tool")
            print(f"✓ parse_index_pages tool was called")

            # Note: parse_prospectus may or may not be called depending on agent behavior
            if has_parse_prospectus:
                print(f"✓ parse_prospectus_with_parsed_index tool was called")

            print(f"\n{'='*60}")
            print(f"✅ Message flow test completed successfully!")
            print(f"{'='*60}")

        finally:
            # Clean up
            prospectus.delete()


if __name__ == '__main__':
    """
    Run tests directly with Python debugger.

    Usage:
        # From backend directory:
        python agents/parsing_agent/test.py

        # Or use VS Code debugger:
        # 1. Set breakpoints in test.py or tools.py
        # 2. Press F5 → "Python: Current File"
    """
    # Django is already set up at the top of this file
    from django.conf import settings
    from django.test.utils import get_runner

    print(f"\nWorking directory: {os.getcwd()}")
    print(f"Django settings: {settings.SETTINGS_MODULE}")
    print(f"Running tests...\n")

    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True, keepdb=True)

    # You can specify which tests to run:
    # Option 1: Run all tests in this file
    # failures = test_runner.run_tests(['agents.parsing_agent.test'])

    # Option 2: Run only unit tests (uncomment to use)
    # failures = test_runner.run_tests(['agents.parsing_agent.test.ParseIndexPagesTestCase'])
    # failures = test_runner.run_tests(['agents.parsing_agent.test.RunAgentTestCase'])

    # Option 3: Run only integration tests (uncomment to use)
    # failures = test_runner.run_tests(['agents.parsing_agent.test.ParseIndexPagesIntegrationTestCase'])

    # Option 4: Run agent integration tests (uncomment to use)
    failures = test_runner.run_tests(['agents.parsing_agent.test.RunAgentIntegrationTestCase.test_run_agent_with_real_prospectus'])

    # Option 5: Run a specific test method (uncomment to use)
    # failures = test_runner.run_tests(['agents.parsing_agent.test.RunAgentIntegrationTestCase.test_run_agent_with_real_prospectus'])

    sys.exit(bool(failures))
