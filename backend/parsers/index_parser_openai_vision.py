import fitz
import os
from openai import OpenAI
from typing import Dict, List, Callable
import base64
import json

class OpenaiVisonIndexParser:
    """
    Parse prospectus index using OpenAI's GPT-4 Vision
    Handles complex 2-column layouts
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key

        if not self.api_key:
            raise ValueError (
                "Openai api key required"
            )
        self.client = OpenAI(api_key = self.api_key)

    def extract_index(self, pdf_path: str, doc_type: str, max_pages: int = 1) -> Dict:
        # first step, find the index pages
        # second step, convert index pages to image
        # third, send image to openai vison to process(build system prompt, structured output)
        # fourth, extrac index

        index_pages = self._find_index_pages(pdf_path, max_pages, doc_type)
        if not index_pages:
            raise ValueError("Could not locate index page")

        images = self._convert_pages_to_images(pdf_path, index_pages)

        parsed_index = self._parse_with_openai_vision(images, self.build_vision_prompt)

        return parsed_index

    def _find_index_pages(self, pdf_path: str, max_pages: int, doc_type: str) -> List[int]:
        #doc_type can be supplement or prospectus, both of them have their own index
        keywords = ["table of contents", "index"]
        doc = fitz.open(pdf_path)
        index_pages = []
        for page_num in range(min(10, len(doc))):
            page = doc[page_num]
            content = page.get_text().lower()
            if any(keyword in content for keyword in keywords):
                if not doc_type in content:
                    continue
                start_page = page_num + 1
                end_page = min(start_page + max_pages - 1, len(doc))
                index_pages = list(range(start_page, end_page + 1))
                break
        doc.close()
        return index_pages
    
    def _convert_pages_to_images(self, pdf_path: str, index_pages: List[int]) -> List[Dict]:
        doc = fitz.open(pdf_path)
        images = []

        for page_num in index_pages:
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
    
    def _parse_with_openai_vision(self, images: List[Dict], build_prompt: Callable) -> Dict:
        messages = [
            {
                'role': 'user',
                'content': build_prompt(images)
            }
        ]
        response = self.client.chat.completions.create(
            model='gpt-4o',
            messages = messages,
            max_tokens=4096,
            temperature=0
        )
        content = response.choices[0].message.content
        parsed_data = self._extract_json(content)
        return parsed_data
    
    def build_vision_prompt(self, images:List[Dict]) -> List[Dict]:
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
    
    def _extract_json(self, content: str) -> Dict:
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
    
    def save_to_file(self, input_data: Dict, output_path: str):
        """
        Save parsed index to text file
        
        Args:
            input_data: Parsed index dictionary
            output_path: Output file path
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(input_data, f, indent = 4)
        
        print(f"file saved to: {output_path}")

    def load_file(self, file_path: str):
        """
        Save parsed index to text file
        
        Args:
            input_data: Parsed index dictionary
            output_path: Output file path
        """
        x = None
        with open(file_path, 'r') as f:
            x = json.load(f)
        return x