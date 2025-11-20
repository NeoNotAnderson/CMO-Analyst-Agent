"""
Tools for the Parsing Agent.

This module contains tools that the parsing agent can use to:
- Parse PDF using Unstructured.io and openai vision
- Extract sections and classify them
- Store parsed data in the database
"""

from typing import List, Dict, Callable
from langchain_core.tools import tool
from openai import OpenAI
import fitz
import base64
import os

@tool
def parse_pdf_with_unstructured(file_path: str) -> List[Dict]:
    """
    Parse a PDF file using Unstructured.io.

    Args:
        file_path: Path to the PDF file

    Returns:
        List of parsed page elements with text, metadata, and structure

    TODO: Implement Unstructured.io integration
    """
    pass

@tool
def parse_page_with_unstructured(file_path: str) -> List[Dict]:
    """
    Parse a PDF file using Unstructured.io.

    Args:
        file_path: Path to the PDF file

    Returns:
        List of parsed page elements with text, metadata, and structure

    TODO: Implement Unstructured.io integration
    """
    pass

@tool
def parse_page_with_openai(file_path: str) -> List[Dict]:
    """
    Parse a PDF file using Unstructured.io.

    Args:
        file_path: Path to the PDF file

    Returns:
        List of parsed page elements with text, metadata, and structure
    """
    pass

#TODO: do not make this as a tool, try to see if the agent is capable of calling all the other tools in order to extract and create the index structure
def create_file_index_structure(file_path: str) -> List[Dict]:
    """
    extract and parse the index pages of the pdf file, create a index strcuture which will be used to build the hierarchy

    Args:
        file_path: Path to the PDF file

    Returns:
        a json object which represents the index of the PDF file
    """
    index_pages = find_index_page(file_path, doc_type)
    if not index_pages:
        raise ValueError("Could not locate index page")

    images = convert_pages_to_images(file_path, index_pages)

    parsed_index = parse_page_images_with_openai(images, self.build_vision_prompt)

    return parsed_index

@tool
def parse_page_images_with_openai(page_images: List[Dict]) -> List[Dict]:
    """
    Parse PDF pages images using openai vision

    Args:
        file_path: Path to the PDF file
        page_images: images converted from PDF pages
        build_prompt: function used to create user prompt to feed llm

    Returns:
        List of parsed page elements with text, metadata, and structure
    """
    #TODO is there a better way to store api_key, how can I let llm AGENT knows where to find the api key!!
    from dotenv import load_dotenv
    load_dotenv()
    api_key=os.getenv("OPENAI_API_KEY")
    llm_client = OpenAI(api_key=api_key)

    parsed_pages = []
    for page in page_images:
        messages = [
            {
                'role': 'user',
                'content': build_prompt_for_index_parsing(page)
            }
        ]
        response = llm_client.chat.completions.create(
            model='gpt-5-nano',
            messages = messages,
            max_tokens=4096,
            temperature=0
        )
        content = response.choices[0].message.content
        parsed_pages.append(extract_json(content))
    return parsed_pages

@tool
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

@tool
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
def find_index_page(file_path: str, doc_type: str = "supplement") -> List[int]:
    """
    find the idnex page of the PDF file

    Args:
        file_path: Path to the PDF file
        doc_type: the type of the PDF file, could be either supplement or prospectus. Normally can be found in the file name.

    Returns:
        List of index page numbers
    """
    keywords = ["table of contents", "index"]
    doc = fitz.open(file_path)
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
    return index_pages

@tool
def convert_pages_to_images(file_path: str, page_numbers: List[int]) -> List[Dict]:
    """
    convert PDF pages to images, so it can be fed to openai vision to further parse

    Args:
        file_path: Path to the PDF file
        page_numbers: the page number of the pages which needed to be parsed

    Returns:
        List of page images
    """
    doc = fitz.open(file_path)
    images = []

    for page_num in page_numbers:
        page = doc[page_num-1]
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

@tool
def classify_sections(parsed_pages: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Classify parsed content into CMO prospectus sections.

    Uses LLM to identify and categorize sections like:
    - Deal Summary, Tranche List, Payment Priority, etc.

    Args:
        parsed_pages: List of parsed page elements

    Returns:
        Dictionary mapping section types to their content

    TODO: Implement LLM-based section classification
    """
    pass


@tool
def build_section_hierarchy(sections: List[Dict]) -> List[Dict]:
    """
    Build hierarchical structure for sections and subsections.

    Args:
        sections: List of classified sections

    Returns:
        List of sections with parent-child relationships

    TODO: Implement hierarchy building logic
    """
    pass


@tool
def store_sections_in_db(prospectus_id: str, sections: List[Dict]) -> bool:
    """
    Store parsed sections in the database.

    Args:
        prospectus_id: UUID of the prospectus
        sections: List of sections to store

    Returns:
        True if successful, False otherwise

    TODO: Implement database storage logic using Django ORM
    """
    pass
