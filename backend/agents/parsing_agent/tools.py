"""
Tools for the Parsing Agent.

This module contains tools that the parsing agent can use to:
- Parse PDF using Unstructured.io and openai vision
- Extract sections and classify them
- Store parsed data in the database
"""
from core.models import Prospectus
from typing import List, Dict, Callable
from langchain_core.tools import tool
from openai import OpenAI
import fitz
import base64
import os
import json
from unstructured.partition.pdf import partition_pdf
import tempfile
from unstructured.documents.elements import Element
from pathlib import Path
from dotenv import load_dotenv

# LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    # Fallback if langsmith not installed
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    LANGSMITH_AVAILABLE = False

load_dotenv()
llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@tool
@traceable(name="check_parse_status", tags=["tool", "parsing", "status"])
def check_parse_status(prospectus_id: str) -> str:
    """
    Check the current parsing status of a prospectus.

    Args:
        prospectus_id: UUID string of the Prospectus object

    Returns:
        str: Parse status (one of: 'pending', 'parsing_index', 'parsing_sections',
             'completed', 'failed')
    """
    try:
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)
        return prospectus.parse_status
    except Prospectus.DoesNotExist:
        print(f'[ERROR] Prospectus with id {prospectus_id} does not exist')
        return False

@tool
@traceable(name="check_parsed_index_exists", tags=["tool", "parsing", "index"])
def check_parsed_index_exists(prospectus_id: str) -> bool:
    """
    Check if parsed index already exists in the database.

    Args:
        prospectus_id: UUID string of the Prospectus object

    Returns:
        True if parsed_index exists and is not empty, False otherwise
    """
    print(f"[DEBUG] check_parsed_index_exists called with: {prospectus_id} (type: {type(prospectus_id)})")

    try:
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)
        print(f"[DEBUG] Found prospectus: {prospectus.prospectus_name}")
        return prospectus.parsed_index is not None and len(prospectus.parsed_index) > 0
    except Prospectus.DoesNotExist:
        print(f'[ERROR] Prospectus with id {prospectus_id} does not exist')
        return False
    
def save_parsed_index_to_db(prospectus_id: str, parsed_index: Dict) -> None:
    """
    Save parsed index to the database.

    Automatically adds page_num to all sections if not already present.

    Args:
        prospectus_id: UUID string of the Prospectus object
        parsed_index: Parsed index structure to save

    Returns:
        None
    """
    prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)

    # Ensure page_num is added to all sections before saving
    # Check if page_num already exists in first section
    if parsed_index.get('sections') and len(parsed_index['sections']) > 0:
        first_section = parsed_index['sections'][0]
        if 'page_num' not in first_section:
            # page_num not present, add it
            add_page_number_to_parsed_index(parsed_index)

    prospectus.parsed_index = parsed_index
    prospectus.save()

def parse_index_pages(prospectus: Prospectus) -> None:
    """
    Orchestration function (NOT a tool) - extract and parse the index pages of the pdf file, create a index strcuture which will be used to build the hierarchy.

    This function is kept for reference but should NOT be used as a tool in ReAct agent.
    The agent should autonomously call the granular tools instead.

    Args:
        prospectus: a Prospectus object of the prospectuss being parsed
        doc_type: the type of the PDF file, could be either supplement or prospectus. Normally can be found in the file name.

    Returns:
        a json object which represents the index of the PDF file
    """
    # Check if index pages are already parsed and stored in the database
    if prospectus.parsed_index is not None and len(prospectus.parsed_index):
        return prospectus.parsed_index
    
    doc_type = determin_doc_type(prospectus.prospectus_name)
    #index_pages are 0-indexed
    index_pages = find_index_pages(prospectus, doc_type)
    if not index_pages:
        raise ValueError("Could not locate index page")

    # Parse index pages if not found in database
    images = convert_pages_to_images(prospectus, index_pages)
    parsed_index = parse_page_images_with_openai(images, True)
    add_page_number_to_parsed_index(parsed_index)
    prospectus.parsed_index = parsed_index
    prospectus.save()

def add_page_number_to_parsed_index(index_structure: Dict) -> Dict:
    """
    Add page_num key-value pair to all sections in the index structure by parsing 'page' field.

    This function recursively processes all sections (top-level to bottom-level) in the index,
    extracts the numeric portion from the 'page' field (e.g., 'S-12' -> 12), and adds a
    'page_num' field with the extracted number.

    Args:
        index_structure: Index structure containing 'sections' list

    Returns:
        The same structure with page_num added to all sections (modifies in place and returns)

    Example:
        Input section: {"title": "RISK FACTORS", "page": "S-12", "level": 1, "sections": [...]}
        Output section: {"title": "RISK FACTORS", "page": "S-12", "page_num": 12, "level": 1, "sections": [...]}
    """
    import re

    def process_section(section: Dict) -> None:
        """Recursively process a section and its subsections."""
        if not isinstance(section, dict):
            return

        # Extract page_num from 'page' field if it exists
        if 'page' in section and section['page']:
            page_str = str(section['page'])
            # Extract numbers from strings like "S-12", "I-5", "12", etc.
            # Pattern matches: optional letters/hyphens, then one or more digits
            match = re.search(r'(\d+)', page_str)
            if match:
                section['page_num'] = int(match.group(1))

        # Recursively process subsections
        if 'sections' in section and isinstance(section['sections'], list):
            for subsection in section['sections']:
                process_section(subsection)

    # Process all top-level sections
    if 'sections' in index_structure and isinstance(index_structure['sections'], list):
        for section in index_structure['sections']:
            process_section(section)

    return index_structure

@tool
@traceable(name="determin_doc_type", tags=["tool", "parsing", "doc_type"])
def determin_doc_type(file_name: str) -> str:
    """
    Determine document type from filename.

    Args:
        file_name: Name of the prospectus file

    Returns:
        "supplement" or "prospectus"
    """
    if "supplement" in file_name.lower():
        return "supplement"
    else:
        return "prospectus"

@tool
@traceable(name="find_index_pages", tags=["tool", "parsing", "index"])
def find_index_pages(prospectus_id: str, doc_type: str = "supplement") -> List[int]:
    """
    find the index page of the PDF file

    Args:
        prospectus_id: UUID string of the Prospectus object
        doc_type: the type of the PDF file, could be either supplement or prospectus. Normally can be found in the file name.

    Returns:
        List of index page numbers
    """
    prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)

    if prospectus.index_page_numbers:
        return prospectus.index_page_numbers
    keywords = ["table of contents", "index"]
    doc = fitz.open(prospectus.prospectus_file.path)
    index_pages = []
    for page_num in range(min(10, len(doc))):
        page = doc[page_num]
        content = page.get_text().lower()
        if any(keyword in content for keyword in keywords):
            if doc_type in content:
                index_pages.append(page_num)
        if len(index_pages) and page_num > index_pages[-1]:
            break
    doc.close()
    prospectus.index_page_numbers = index_pages
    prospectus.parse_status = "parsing_index"
    prospectus.save()
    return index_pages

def parsed_pages_exist_in_db(page_numbers: List[int], prospectus: Prospectus) -> bool:
    """
    Check if parsed pages already exist in the database.

    Args:
        page_numbers: List of page numbers
        prospectus:

    Returns:
        True if all pages are already parsed and stored, False otherwise
    """
    from core.models import Prospectus
    import os

    try:
        # Check if parsed_pages exists and is not empty
        if not prospectus.parsed_pages:
            return False

        # Check if the specific pages are in parsed_pages
        # parsed_pages is a list of page objects with page_num field
        parsed_page_numbers = {page[0].get('page_num') for page in prospectus.parsed_pages if isinstance(page, list)}

        # Verify all requested pages are already parsed
        return all(page_num in parsed_page_numbers for page_num in page_numbers)

    except Exception as e:
        # If any error occurs, return False to trigger new parsing
        print(f"Error checking database for parsed index pages: {e}")
        return False

def retrieve_parsed_pages_from_db(prospectus: Prospectus, page_numbers: List[int]) -> List[Dict]:
    """
    Retrieve previously parsed pages from the database.

    Args:
        prospectus: Prospectus object
        page_numbers: List of page numbers

    Returns:
        Previously parsed pages as a list of dictionaries
    """
    try:
        # Filter and return only the requested pages
        parsed_pages = [
            page for page in prospectus.parsed_pages
            if isinstance(page, list) and page[0].get('page_num') in page_numbers
        ]

        if not parsed_pages:
            raise ValueError(f"Requested page numbers {page_numbers} not found in database")

        return parsed_pages

    except Exception as e:
        print(f"Error retrieving parsed pages from database: {e}")
        raise

@tool
@traceable(name="convert_pages_to_images", tags=["tool", "parsing", "image_conversion"])
def convert_pages_to_images(prospectus_id: str, page_numbers: List[int]) -> str:
    """
    Convert PDF pages to images and store them in the prospectus object.

    IMPORTANT: This tool does NOT return the images (too large for tool results).
    Instead, it stores them in the prospectus.metadata['temp_images'] field.
    Use parse_page_images_with_openai to parse them.

    Args:
        prospectus_id: Prospectus ID
        page_numbers: the page number of the pages which needed to be parsed

    Returns:
        Success message with page numbers converted
    """
    from PIL import Image
    import io

    # Hard limit to prevent token overflow
    if len(page_numbers) > 2:
        raise ValueError(
            f"Too many pages requested: {len(page_numbers)}. "
            f"Maximum is 2 pages at a time to avoid exceeding token limits. "
            f"Please convert pages in smaller batches."
        )

    prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)
    doc = fitz.open(prospectus.prospectus_file.path)
    images = []

    for page_num in page_numbers:
        page = doc[page_num]
        # Use DPI=72 (standard screen resolution) to minimize token usage
        pix = page.get_pixmap(dpi=72)

        # Convert through PIL to ensure valid format
        img_data = pix.tobytes("ppm")
        pil_image = Image.open(io.BytesIO(img_data))

        # Save as PNG
        buffer = io.BytesIO()
        pil_image.save(buffer, format='PNG', optimize=False)
        img_bytes = buffer.getvalue()

        # Verify the image is valid
        Image.open(io.BytesIO(img_bytes)).verify()

        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        # Log image size
        img_size_kb = len(img_base64) / 1024
        print(f"[DEBUG] Page {page_num}: {img_size_kb:.1f} KB (base64), {len(img_base64)} chars")

        images.append({
            'page_num': page_num,
            'image': img_base64
        })
    doc.close()

    # Store images in prospectus metadata (not returned through tool result)
    if not prospectus.metadata:
        prospectus.metadata = {}
    prospectus.metadata['temp_images'] = images
    prospectus.save()

    total_size_mb = sum(len(img['image']) for img in images) / (1024 * 1024)
    print(f"[DEBUG] Stored {len(images)} images in prospectus metadata: {total_size_mb:.2f} MB")

    return f"Successfully converted {len(page_numbers)} pages to images: {page_numbers}. Images stored in prospectus metadata."

def convert_pages_to_images_direct(prospectus: Prospectus, page_numbers: List[int]) -> List[Dict]:
    """
    Helper function (NOT a tool) to convert pages to images and return them directly.
    Used by parse_prospectus_with_parsed_index which is not agent-driven.

    Args:
        prospectus: Prospectus object
        page_numbers: List of page numbers to convert

    Returns:
        List of image dictionaries with 'page_num' and 'image' (base64) keys
    """
    from PIL import Image
    import io

    doc = fitz.open(prospectus.prospectus_file.path)
    images = []

    for page_num in page_numbers:
        page = doc[page_num]
        pix = page.get_pixmap(dpi=72)

        # Convert through PIL
        img_data = pix.tobytes("ppm")
        pil_image = Image.open(io.BytesIO(img_data))

        # Save as PNG
        buffer = io.BytesIO()
        pil_image.save(buffer, format='PNG', optimize=False)
        img_bytes = buffer.getvalue()

        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        images.append({
            'page_num': page_num,
            'image': img_base64
        })
    doc.close()

    return images

@tool
@traceable(name="parse_page_images_with_openai", tags=["tool", "parsing", "openai_vision"])
def parse_page_images_with_openai(prospectus_id: str, is_index: bool) -> str:
    """
    Parse and save PDF pages images using OpenAI vision.

    Retrieves images from prospectus.metadata['temp_images'] that were stored
    by convert_pages_to_images tool. Parses with OpenAI and saves directly
    to database to avoid LangChain truncating large return values.

    Args:
        prospectus_id: Prospectus ID to retrieve images from
        is_index: if current page_images are index pages or not

    Returns:
        Success message (parsed data is saved to DB, not returned)
    """
    print(f"\n{'='*60}")
    print(f"[TOOL ENTRY] parse_page_images_with_openai called")
    print(f"[TOOL ENTRY] prospectus_id: {prospectus_id}")
    print(f"[TOOL ENTRY] is_index: {is_index}")
    print(f"{'='*60}\n")

    # Retrieve images from prospectus metadata
    prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)

    if not prospectus.metadata or 'temp_images' not in prospectus.metadata:
        raise ValueError("No images found in prospectus metadata. Call convert_pages_to_images first.")

    page_images = prospectus.metadata['temp_images']
    print(f"[DEBUG] Retrieved {len(page_images)} images from prospectus metadata")

    # Verify image data integrity
    for i, img_dict in enumerate(page_images):
        img_b64 = img_dict['image']
        print(f"[VERIFY] Image {i}: Length={len(img_b64)} chars")

        # Verify it's valid
        try:
            import io
            from PIL import Image
            img_bytes = base64.b64decode(img_b64)
            Image.open(io.BytesIO(img_bytes)).verify()
            print(f"[VERIFY] Image {i}: Valid ✓")
        except Exception as e:
            print(f"[ERROR] Image {i}: Invalid: {e}")
            raise ValueError(f"Image {i} is corrupted: {e}")

    print(f"[DEBUG] Building prompt content...")
    content = build_prompt_for_index_parsing(page_images) if is_index else build_prompt_for_parsing_pages_with_table(page_images)
    print(f"[DEBUG] Prompt content built")
    messages = [
        {
            'role': 'user',
            'content': content
        }
    ]

    try:
        response = llm_client.chat.completions.create(
            model='gpt-5-nano',
            messages = messages
        )
        content = response.choices[0].message.content
        parsed_pages = extract_json(content)
        if is_index:
            add_page_number_to_parsed_index(parsed_pages)
            prospectus.parsed_index = parsed_pages
            prospectus.parse_status = 'parsing_sections'
            prospectus.save()
            num_sections = len(parsed_pages.get('sections', []))
            print(f"[SUCCESS] Parsed and saved index with {num_sections} sections")
            print(f"[STATUS] Updated parse_status to: parsing_sections")
            return f"Successfully parsed and saved index pages with {num_sections} top-level sections to database."
        else:
            if not prospectus.metadata:
                prospectus.metadata = {}
            prospectus.metadata['temp_parsed_pages'] = parsed_pages
            prospectus.save()
            num_sections = len(parsed_pages) if isinstance(parsed_pages, list) else 0
            print(f"[SUCCESS] Parsed and saved {num_sections} page sections")
            return f"Successfully parsed and saved {num_sections} page sections to database."

    except Exception as e:
        prospectus.parse_status = 'failed'
        prospectus.save()
        print(f"[STATUS] Updated parse_status to: failed")

        if "context_length_exceeded" in str(e):
            print(f"[ERROR] Token limit exceeded with {len(page_images)} pages")
            print(f"[ERROR] Image sizes: {[len(img['image'])/1024 for img in page_images]} KB")
            raise ValueError(f"Too many tokens. Try parsing fewer pages at once (currently {len(page_images)} pages)")
        raise

def parse_page_images_with_openai_direct(page_images: List[Dict], is_index: bool) -> Dict:
    """
    Helper function (NOT a tool) to parse images directly without agent.
    Used by parse_prospectus_with_parsed_index.

    Args:
        page_images: List of image dicts with 'page_num' and 'image' keys
        is_index: Whether parsing index pages

    Returns:
        Parsed structure
    """
    content = build_prompt_for_index_parsing(page_images) if is_index else build_prompt_for_parsing_pages_with_table(page_images)
    messages = [
        {
            'role': 'user',
            'content': content
        }
    ]

    try:
        response = llm_client.chat.completions.create(
            model='gpt-5-nano',
            messages=messages
        )
        content = response.choices[0].message.content
        return extract_json(content)
    except Exception as e:
        if "context_length_exceeded" in str(e):
            raise ValueError(f"Token limit exceeded with {len(page_images)} pages")
        raise

def build_prompt_for_index_parsing(images:List[Dict]) -> List[Dict]:
    """
    Parse PDF index page images using openai vision

    Args:
        images: images converted from PDF index pages

    Returns:
        prompt, with images embeded, which provides parsing instructions to llm for it to parse index pages
    """
    content = []
    content.append(
        {
            'type': 'text',
            'text': """
                    You are parsing the Table of Contents / Index from a CMO prospectus.
                    
                    The images show index pages in a 2-COLUMN layout.

                    CRITICAL INSTRUCTIONS:
                    1. Read the LEFT column from top to bottom FIRST
                    2. Then read the RIGHT column from top to bottom
                    3. Do NOT treat columns as a single table row
                    4. Each entry has a similar format: "Section Title.....Page Number" or "Section Title"
                    5. One section title may take several lines, and the page number maybe missing. you need to return the page number if you could figure it out.
                    6. Some entries are indented (these are subsections)
                    7. Skip page headers/footers like "Table of Contents" or page numbers at top
                    8, there maybe more than on page iamge in the prompt, parse each page one by one in the original order, combine them into one json object and return
                    9, when combining parsed pages together, pay attention to the level of starting section of each page, make sure they are in the correct section relative to the ending section of the previous page.

                    Extract each entry with:
                    - title: The section name (keep exact text including capitalization)
                    - page: The page number(which starts with S or I)
                    - level: 1 for main sections, 2 for subsections, 3 for sub-subsections
                    - Subsections should be nested under their parent section

                    Return ONLY valid JSON in this format:
                    {
                    "sections": [
                        {
                        "title": "RISK FACTORS",
                        "page": "S-12",
                        "level": 1,
                        "sections": [...]
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
                            "sections": [...]
                            },
                            {
                            "title": "Priority of Distributions",
                            "page": "S-30",
                            "level": 2,
                            "sections": [...]
                            }
                        ]
                        }
                    ]
                    }

                    IMPORTANT: Return ONLY the JSON, no additional text or explanation.
                    """
        }
    )
    for img_data in images:
        content.append(
            {
                'type':'image_url',
                'image_url': {
                    "url": f"data:image/png;base64,{img_data['image']}",
                    "detail": "high"
                }
            }
        )
    return content

def extract_json(content: str) -> Dict:
    """
    Extract JSON from response (handles markdown code blocks)
    
    Args:
        content: Response text
        
    Returns:
        Parsed JSON dictionary
    """
    # Try to find JSON in markdown code blocks
    import re
    
    # Look for ```json ... ```
    json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        return json.loads(json_str)
    
    # Look for ``` ... ``` (without json tag)
    code_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
    if code_match:
        json_str = code_match.group(1)
        return json.loads(json_str)
    
    # Try to parse entire content as JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Last resort: look for { ... } pattern
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        
        raise ValueError(f"Could not extract JSON from response: {content[:200]}")

@tool
@traceable(name="parse_prospectus_with_parsed_index", tags=["tool", "parsing", "full_parsing"])
def parse_prospectus_with_parsed_index(prospectus_id: str) -> str:
    """
    Parse the full prospectus using the parsed index structure as a guide.

    This is a complex orchestration tool that manages nested loops and state across pages.
    It uses granular helper tools internally but the agent should call this as a single operation
    because the stateful iteration logic is too complex for the agent to manage manually.

    Saves the parsed prospectus to database instead of returning it to avoid truncation.

    Args:
        prospectus_id: Prospectus ID with parsed_index already populated

    Returns:
        Success message indicating parsing is complete
    """
    prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)

    try:
        # Update status to parsing_sections at the start
        prospectus.parse_status = 'parsing_sections'
        prospectus.save()
        print(f"[STATUS] Updated parse_status to: parsing_sections")

        index = prospectus.parsed_index
        # go through each level 1 section
        for i, parent_section in enumerate(index['sections']):
            #first page is index, so the starting page and ending page for each section is offset by 1. so no need to subtract by one
            starting_page = int(parent_section['page_num'])
            doc = fitz.open(prospectus.prospectus_file.path)
            ending_page = len(doc)
            next_index_section_title = ""
            if i < len(index['sections']) - 1:
                next_section = index['sections'][i+1]
                ending_page = int(next_section['page_num'])
                next_index_section_title = next_section['title']
            if ending_page > len(doc):
                break
            pos = -1
            last_processed_section = None

            for page_number in range(starting_page, ending_page+1):
                page_sections = []
                if not parsed_pages_exist_in_db([page_number], prospectus):
                    #extract single page to temporary pdf
                    page_doc = fitz.open()
                    page_doc.insert_pdf(doc, from_page=page_number, to_page=page_number)

                    #save to temp file
                    temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                    page_doc.save(temp_file.name)
                    page_doc.close()

                    #parse with unstructured
                    elements = partition_pdf(
                        filename=temp_file.name,
                        strategy='hi_res',
                        infer_table_structure=True
                    )
                    #clean up temp file
                    os.unlink(temp_file.name)

                    #check if file contains table:
                    has_table = any(element.category == 'Table' for element in elements)
                    if has_table:
                        page_image = convert_pages_to_images_direct(prospectus, [page_number])
                        page_sections = parse_page_images_with_openai_direct(page_image, False)
                        add_page_number_to_parsed_sections(page_sections, page_number)
                    else:
                        page_sections = extract_sections(elements, page_number)
                    
                    # save parsed page:
                    store_parsed_pages_in_db(prospectus, [page_number], [page_sections])
                else:
                    # Retrieve already parsed page from database
                    # parsed_pages is a list of lists, each sublist is a page with sections
                    for page in prospectus.parsed_pages:
                        if isinstance(page, list) and len(page) > 0 and page[0].get('page_num') == page_number:
                            page_sections = page  # page is already a list of dictionaries
                            break
                pos, last_processed_section = combine_sections(parent_section, next_index_section_title, page_sections, pos, last_processed_section)
            doc.close()

        # Add level and sample_text to all sections for query analysis
        if 'sections' in index:
            add_level_to_sections(index['sections'])
            add_sample_text_to_sections(index['sections'])

        prospectus.parsed_file = index
        prospectus.parse_status = 'completed'
        prospectus.save()

        num_sections = len(index.get('sections', []))
        print(f"[SUCCESS] Parsed and saved full prospectus with {num_sections} top-level sections")
        print(f"[STATUS] Updated parse_status to: completed")
        return f"Successfully parsed and saved full prospectus with {num_sections} top-level sections to database."

    except Exception as e:
        prospectus.parse_status = 'failed'
        prospectus.save()
        print(f"[ERROR] Parsing failed: {e}")
        print(f"[STATUS] Updated parse_status to: failed")
        raise

def add_page_number_to_parsed_sections(page_sections: List[Dict], page_number: int) -> List[Dict]:
    """
    Add page_num key-value pair to all top-level sections.

    Args:
        page_sections: List of parsed sections from a page
        page_number: The page number to add to each section

    Returns:
        The same list with page_num added to each section (modifies in place and returns)
    """
    for section in page_sections:
        if isinstance(section, dict):
            section['page_num'] = page_number
    return page_sections


def add_sample_text_to_sections(sections: List[Dict]) -> None:
    """
    Recursively add 'sample_text' field to all sections and subsections.

    This function extracts the first 500 characters from each section's 'text' field
    and stores it as 'sample_text'. This sample is used by the query agent to help
    the LLM identify relevant sections without needing to process the full text.

    The function processes all sections recursively (both level 1 and level 2 subsections).

    Args:
        sections: List of section dicts (modified in place)
                 Each section should have a 'text' field
                 May contain nested 'sections' for subsections

    Returns:
        None (modifies sections in place by adding 'sample_text' field to each section)

    Side effects:
        - Adds 'sample_text' field to each section (first 500 chars of 'text')
        - If 'text' is empty, 'sample_text' will be an empty string
    """
    for section in sections:
        if isinstance(section, dict):
            # Add sample_text from the text field
            text = section.get('text', '')
            if text:
                section['sample_text'] = text[:500]
            else:
                section['sample_text'] = ''

            # Recursively process subsections
            if 'sections' in section and section['sections']:
                add_sample_text_to_sections(section['sections'])


def add_level_to_sections(sections: List[Dict], parent_level: int = 0) -> None:
    """
    Recursively add 'level' field to all sections and subsections if not present.

    This function ensures all sections have a 'level' field for hierarchical organization.
    Top-level sections get level=1, their subsections get level=2.

    Args:
        sections: List of section dicts (modified in place)
        parent_level: Level of the parent section (0 for root, used for recursion)

    Returns:
        None (modifies sections in place by adding 'level' field if missing)

    Side effects:
        - Adds 'level' field to sections that don't have it
        - Level 1 for top-level sections
        - Level 2 for subsections
    """
    for section in sections:
        if isinstance(section, dict):
            # Add level if not present
            if 'level' not in section:
                section['level'] = parent_level + 1

            # Recursively process subsections
            if 'sections' in section and section['sections']:
                add_level_to_sections(section['sections'], parent_level=section['level'])

def build_prompt_for_parsing_pages_with_table(images: List[Dict]) -> Dict:
    """
    Build prompt for parsing PDF pages that contain tables using OpenAI vision.

    Args:
        images: List of page images converted from PDF pages

    Returns:
        Prompt content with embedded images and parsing instructions for pages with tables
    """
    content = []
    content.append(
        {
            'type': 'text',
            'text': """Parse this PDF page and extract all content in structured JSON format.

                        # OUTPUT FORMAT
                        Return a JSON array of sections:
                        ```json
                        [
                        {
                            "title": "SECTION TITLE or empty string",
                            "text": "Body text with paragraphs separated by \\n\\n",
                            "table": {
                            "summary": "One sentence describing the table",
                            "data": [
                                {"Column1": "value", "Column2": "value"}
                            ]
                            } or null
                        },
                        {
                            ...
                        }
                        ]
                        ```
                        # SECTION IDENTIFICATION
                        - each section starts with a title text
                        - titles are normally in bold font, all caps, bigger font than body text

                        # LAYOUT & READING ORDER

                        **Two-column sections:** Read LEFT column completely (top to bottom), THEN right column (top to bottom)

                        **One-column sections:** Read top to bottom

                        # TEXT FIELD RULES

                        **The text field must include ALL body text in the section, including:**
                        1. Text BEFORE the table
                        2. Text AFTER the table
                        3. Text between multiple tables
                        4. Any explanatory paragraphs

                        **Example structure:**
                        ```
                        Subsection Title
                        [Text before table - include this]
                        [Table]
                        [Reference and footnote]
                        [Text after footnote - MUST include this too!]
                        [More text - include everything]
                        ```

                        **IMPORTANT:** Don't stop capturing text just because you found a table. Keep reading and include ALL text content that belongs to that section until you reach the next section/subsection title or the end of the section
                        
                        # TABLE PARSING RULES
                        1. **Structure:** Each row = dictionary, keys = column headers
                        2. **Summary:** Write one sentence describing table content
                        3. **References:** References are part of the table. Tables contain references like (1), (2), *, †
                        - **Find footnotes in TWO places:**
                            - Directly under the table
                            - Footer area at bottom of page (look for smaller text, horizontal lines, or spacing)
                        - **Resolve references:** Replace "(1)" with "[footnote text]"
                        - **Format:** "Original Value [Footnote Text]"
                        - **Example:** "Class A-1 (1)" + footnote "(1) Senior class" → "Class A-1 [Senior class]"
                        4. **Multiple references:** "Value (1)(2)" → "Value [text1] [text2]"
                        5. **Column references:** Can apply to headers OR cells
                        6. **If not found:** Keep reference as-is
                        
                        **Example 1: Simple reference**
                        ```
                        Table content:
                        | Class   | Size      |
                        |---------|-----------|
                        | A-1 (1) | $500M     |

                        Footnote:
                        (1) Senior class
                        ```

                        **Output:**
                        ```json
                        "table": {
                        "summary": "Certificate classes and their sizes",
                        "data": [
                            {
                            "Class": "A-1 [Senior class]",
                            "Size": "$500M"
                            }
                        ]
                        }
                        ```
                        **Example 3: Reference in multiple cells**
                        ```
                        Table:
                        | Class | Coupon (1) | WAC (1) |
                        |-------|------------|---------|
                        | A-1   | 3.50%      | 4.25%   |

                        Footnote:
                        (1) As of Closing Date
                        ```

                        **Output:**
                        ```json
                        "table": {
                        "summary": "Class coupons and weighted average coupons as of closing",
                        "data": [
                            {
                            "Class": "A-1",
                            "Coupon [As of Closing Date]": "3.50%",
                            "WAC [As of Closing Date]": "4.25%"
                            }
                        ]
                        }
                        ```
                        # COMPLETE CONTENT CAPTURE

                        **Ensure you capture:**
                        - Opening paragraphs (before any table)
                        - Text between tables (if multiple tables)
                        - Closing paragraphs (after all tables)
                        - Footnote area is NOT text content (it's for resolving references only)
                        - References in the table is resolved(replaced by reference text)

                        **Text vs Footnotes:**
                        - Text = actual content paragraphs (goes in "text" field)
                        - Footnotes = reference explanations (used to resolve table references, NOT in text field)

                        # CRITICAL RULES
                        1. Always check BOTH under-table AND footer for references
                        2. Resolve ALL references found in the table
                        3. Don't include page headers/footers/page numbers
                        4. Return ONLY valid JSON

                        # VALIDATION CHECKLIST
                        ✓ Sections correctly identified 
                        ✓ References checked in both locations
                        ✓ All references resolved with [text]
                        ✓ Table summaries included
                        ✓ Valid JSON structure

                        Parse the image now."""
        }
    )
    for img_data in images:
        content.append(
            {
                'type':'image_url',
                'image_url': {
                    "url": f"data:image/png;base64,{img_data['image']}",
                    "detail": "high"
                }
            }
        )
    return content

def combine_sections(index_section: Dict, next_index_section_title: str, page_sections: List[Dict], pos: int, last_processed_section: Dict) -> None:
    """
    Combine page_sections from a single page into the index_section (level 1 section from index).

    Args:
        index_section: Level 1 section from index containing 'title', 'text', 'page', 'level', 'sections',
        'sections' represent a list of level 2 sections parsed from index page, containing 'title', 'text', 'table'
        page_sections: List of sections parsed from current page, each with 'title', 'text', 'table', 'title' and 'table' values may be empty
        pos: Current position in index_section['sections']
        last_processed_section: Last section that was processed

    Returns:
        Tuple of (next_pos, last_processed_section)
    """
    #if pos == -1, it means this is the first page of the current index_section
    # first locate the starting section, which has the same title as index_sction
    idx = 0
    if pos == -1:
        for i in range(len(page_sections)):
            if page_sections[i]['title'] == index_section['title']:
                pos = 0
                if 'text' not in index_section:
                    index_section['text'] = ''
                index_section['text'] += page_sections[i]['text']
                idx = i + 1
                break
    # idx is the index for te sections in the current page that we need to porcess next, it belongs to the subsections of the current index_section
    # the next thing is to add all the sections starting from idx to the next index subsection to index_section['sections']
        
    # idx == 0 it means current page is not the first page, so the leading sections may have empty title
    # they belong to the last section of the last page we have processed
    # this step addes these sections to last processed section
    if idx == 0:
        content = []
        while idx < len(page_sections) and not page_sections[idx]['title']:
            content.append(page_sections[idx]['text'])
            idx += 1
        if len(content) and last_processed_section:
            if 'text' not in last_processed_section:
                last_processed_section['text'] = ''
            last_processed_section['text'] += '\n'.join(content)
    if idx == len(page_sections):
        return pos, last_processed_section
    next_pos = pos
    if len(index_section['sections']) == 0 or pos == len(index_section['sections']):
        for i in range(idx, len(page_sections)):
            if page_sections[i]['title'] == next_index_section_title:
                break
            index_section['sections'].append(page_sections[i])
        # these values need to be used by the next function call:
        next_pos = len(index_section['sections'])
        last_processed_section = index_section['sections'][-1]
    else:
        # the index for the next index subsection we should look for: pos
        section_map = [None] * len(index_section['sections'])
        for i in range(pos, len(index_section['sections'])):
            subsection = index_section['sections'][i]
            section_list = []
            while idx < len(page_sections) and page_sections[idx]['title'] != subsection['title']:
                if not page_sections[idx]['title']:
                    last_processed_section['text'] += page_sections[idx]['text']
                    if page_sections[idx]['table']:
                        last_processed_section['table'] = page_sections[idx]['table']
                else:
                    section_list.append(page_sections[idx])
                    last_processed_section = page_sections[idx]
                
                idx += 1
            section_map[i] = section_list
            #these values need to be updated and used to process the next page:
            next_pos = i+1
            if len(section_list):
                last_processed_section = section_list[-1]
            else:
                last_processed_section = subsection
            #find the page section with the same title as the index sub section
            if idx < len(page_sections):
                if 'text' not in subsection:
                    subsection['text'] = ''
                subsection['text'] += page_sections[idx]['text']
                idx += 1
            if idx == len(page_sections):
                break
        combined_sections = []
        for i in range(len(index_section['sections'])):
            if section_map[i]:
                for section in section_map[i]:
                    combined_sections.append(section)
            combined_sections.append(index_section['sections'][i])
        index_section['sections'] = combined_sections

    return next_pos, last_processed_section

def extract_sections(elements: Element, page_number: int) -> List[Dict]:
    """
    Extract sections from parsed PDF elements using Unstructured.io.

    This function processes elements from a single PDF page and groups them into sections
    based on title elements. Each section contains a title, page number, and text content.
    The sections are flattened (no hierarchy) and will be combined with the index structure
    to create the full prospectus.

    Args:
        elements: List of elements from Unstructured.io partition_pdf
        page_number: The page number being processed (used for page_num field)

    Returns:
        List of section dictionaries, each containing:
            - title (str): Section title text (empty string if no title found)
            - page_num (int): Page number where this section appears
            - text (str): Concatenated text content from the section

    Note:
        - Sections are identified by 'Title' category elements
        - Text content includes 'NarrativeText', 'UncategorizedText', and 'ListItem' categories
        - Each new title starts a new section
        - The function does not preserve hierarchical relationships between sections
    """
    # all_section does not contain the hierachy of different sections,
    # it will be used to create a full prospectus together with index structure
    all_sections = []
    cur_section = {
        'title': '',
        'page_num': page_number,
        'text': ''
    }
    section_content = []
    
    for element in elements:
        if element.category == 'Title':
            if element.text != cur_section.get('title'):
                cur_section['text'] =  "\n".join(section_content)
                all_sections.append(cur_section)
            cur_section = {
                'title': element.text,
                'page_num': page_number,
                'text': ''
            }
            section_content = []
        elif any(element.category == item for item in ['NarrativeText', 'UncategorizedText', 'ListItem']):
            section_content.append(element.text)
    if section_content:
        cur_section['text'] =  "\n".join(section_content)
    all_sections.append(cur_section)
    
    return all_sections

def store_parsed_pages_in_db(prospectus: Prospectus, page_numbers: List[int], parsed_pages: list) -> bool:
    """
    Store the parsed pages in the database for future retrieval.

    Args:
        prospectus: Prospectus object
        page_numbers: List of page numbers that were parsed
        parsed_pages: The parsed pages to store

    Returns:
        True if storage was successful, False otherwise
    """
    try:
        # if the pages are already parsed, return True
        if all(page[0].get('page_num') in page_numbers for page in prospectus.parsed_pages):
            return True
        # Initialize parsed_pages if it doesn't exist
        if not prospectus.parsed_pages:
            prospectus.parsed_pages = []

        # Add the new parsed pages
        for page in parsed_pages:
            prospectus.parsed_pages.append(page)

        # Save to database
        prospectus.save()

        print(f"Successfully stored {len(parsed_pages)} parsed index pages for {prospectus.prospectus_name}")
        return True

    except Exception as e:
        print(f"Error storing parsed pages in database: {e}")
        return False
