import fitz
import os
from openai import OpenAI
from typing import Dict, List, Callable
import base64
import json

class OpenaiVisonPageParser:
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

    def parse_page_with_table(self, pdf_path: str, page_number: int) -> Dict:
        #page_number is 0-indexed
        images = self._convert_pages_to_images(pdf_path, [page_number])
        parsed_page = self._parse_page_with_openai_vision(images, self.build_vision_prompt_for_pages_with_table)
        return parsed_page
    

    def _convert_pages_to_images(self, pdf_path: str, pages: List[int]) -> List[Dict]:
        doc = fitz.open(pdf_path)
        images = []

        for page_num in pages:
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
    
    def build_vision_prompt_for_pages_with_table(self, images: List[Dict]) -> Dict:
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
    
    def _parse_page_with_openai_vision(self, images: List[Dict], build_prompt: Callable) -> Dict:
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

    def save_parsed_page_to_file(self, parsed_page: Dict, output_path: str):
        """
        Save parsed pages to text file
        
        Args:
            parsed_page: list of dictionary, each dictionary is a section
            output_path: Output file path
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("PARSED PAGES\n")
            f.write("=" * 80 + "\n\n")
            
            for section in parsed_page:
                if section['title']:
                    f.write(f"section title: {section['title']}\n")
                else:
                    f.write(f"section title: \n")
                if section['text']:
                    f.write(f"section text: {section['text']} \n")
                
                if section['table']:
                    f.write(f"table summary: {section['table']['summary']} \n")
                    for row in section['table']['data']:
                        f.write(f" {json.dumps(row, indent=4)}\n")
                
                f.write("\n")
        
        print(f"page saved to: {output_path}")