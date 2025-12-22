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

from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock, call
from core.models import Prospectus
import json

# Import the tool and get the underlying function
from agents.parsing_agent import tools
parse_index_pages = tools.parse_index_pages.func  # Access the actual function, not the StructuredTool wrapper


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

    # Option 3: Run only integration tests (uncomment to use)
    # failures = test_runner.run_tests(['agents.parsing_agent.test.ParseIndexPagesIntegrationTestCase'])

    # Option 4: Run a specific test (uncomment to use)
    failures = test_runner.run_tests(['agents.parsing_agent.test.ParseIndexPagesIntegrationTestCase.test_parse_prospectus_with_parsed_index_integration'])

    sys.exit(bool(failures))
