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

load_dotenv()
llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@tool
def parse_index_pages(prospectus: Prospectus) -> None:
    """
    extract and parse the index pages of the pdf file, create a index strcuture which will be used to build the hierarchy

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
    parsed_index = parse_page_images_with_openai(images, build_prompt_for_index_parsing)
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

def determin_doc_type(file_name: str) -> str:
    if "supplement" in file_name.lower():
        return "supplement"
    else:
        return "prospectus"

def find_index_pages(prospectus: Prospectus, doc_type: str = "supplement") -> List[int]:
    """
    find the idnex page of the PDF file

    Args:
        prospectus: 
        doc_type: the type of the PDF file, could be either supplement or prospectus. Normally can be found in the file name.

    Returns:
        List of index page numbers
    """
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
        prospectus: 
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

def convert_pages_to_images(prospectus: Prospectus, page_numbers: List[int]) -> List[Dict]:
    """
    convert PDF pages to images, so it can be fed to openai vision to further parse

    Args:
        prospectus: 
        page_numbers: the page number of the pages which needed to be parsed

    Returns:
        List of page images
    """
    doc = fitz.open(prospectus.prospectus_file.path)
    images = []

    for page_num in page_numbers:
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        images.append(
            {
                'page_num': page_num,
                'image': img_base64
            }
        )
    doc.close()
    return images

def parse_page_images_with_openai(page_images: List[Dict], build_prompt: Callable) -> Dict:
    """
    Parse PDF pages images using openai vision

    Args:
        file_path: Path to the PDF file
        page_images: images converted from PDF pages
        build_prompt: function used to create user prompt to feed llm

    Returns:
        List of parsed page elements with text, metadata, and structure
    """
    messages = [
        {
            'role': 'user',
            'content': build_prompt(page_images)
        }
    ]
    response = llm_client.chat.completions.create(
        model='gpt-5-nano',
        messages = messages
    )
    content = response.choices[0].message.content
    return extract_json(content)

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
def parse_prospectus_with_parsed_index(prospectus: Prospectus) -> Dict:
    """
    Parse the full prospectus using the parsed index structure as a guide.

    Args:
        prospectus: Prospectus object with parsed_index already populated

    Returns:
        Complete parsed prospectus structure with all sections filled in
    """
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
                    page_image = convert_pages_to_images(prospectus, [page_number])
                    page_sections = parse_page_images_with_openai(page_image, build_prompt_for_parsing_pages_with_table)
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
    prospectus.parsed_file = index
    prospectus.save()
    
    return index
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
        prospectus: 
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
  
@tool
def classify_sections_with_llm(sections: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Use LLM to classify sections into CMO prospectus section types.

    Args:
        sections: List of parsed sections with hierarchy

    Returns:
        Dictionary mapping section types to their content

    TODO: Implement LLM-based classification
    """
    pass

#parse_index_pages()