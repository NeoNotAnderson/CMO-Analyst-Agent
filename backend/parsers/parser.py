from unstructured.partition.pdf import partition_pdf
import os
from dotenv import load_dotenv
import fitz
from typing import Dict, List, Tuple
from page_parser_openai_vision import OpenaiVisonPageParser
import tempfile
from unstructured.documents.elements import Element
import json
from pathlib import Path

class ProspectusParser:
    def parse_prospectus(self, pdf_path: str, index: Dict) -> Dict:
        load_dotenv()
        api_key=os.getenv("OPENAI_API_KEY")
        openai_vison_parser = OpenaiVisonPageParser(api_key)
        # go through each level 1 section
        for i, parent_section in enumerate(index['sections']):
            #first page is index, so the starting page and ending page for each section is offset by 1. so no need to subtract by one
            starting_page = int(parent_section['page'][parent_section['page'].index('-')+1 :].strip())
            doc = fitz.open(pdf_path)
            ending_page = len(doc) - 1
            next_index_section_title = ""
            if i < len(index['sections']) - 1:
                next_section = index['sections'][i+1]
                ending_page = int(next_section['page'][next_section['page'].index('-')+1 :].strip())
                next_index_section_title = next_section['title']
            if ending_page > len(doc) - 1:
                break
            pos = -1
            last_processed_section = None

            for page_number in range(starting_page, ending_page+1):
                file_name = f"page_{page_number}.json"
                file_path = './backend/saved_pages'
                saved_page = Path(file_path) / file_name
                page_sections = []
                if not saved_page.is_file():
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
                        page_sections = openai_vison_parser.parse_page_with_table(pdf_path, page_number)
                    else:
                        page_sections = self._extract_sections(elements, page_number)
                    
                    # save page sections:
                    with open(saved_page, 'w', encoding='utf-8') as f:
                        json.dump(page_sections, f, indent = 4)
                else:
                    with open(saved_page, 'r') as f:
                        page_sections = json.load(f)
                pos, last_processed_section = self._combine_sections(parent_section, next_index_section_title, page_sections, pos, last_processed_section)
            doc.close()

        file_name = "combined_index.json"
        file_path = './backend/saved_pages'
        saved_page = Path(file_path) / file_name
        with open(saved_page, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent = 4)

        return index
    def _combine_sections(self, index_section: Dict, next_index_section_title: str, page_sections: List[Dict], pos: int, last_processed_section: Dict) -> None:
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
                
        
    def _extract_sections(self, elements: Element, page_number: int) -> List[Dict]:
        # all_section does not contain the hierachy of different sections, 
        # it will be used to create a full prospectus together with index structure
        all_sections = []
        cur_section = {
            'title': '',
            'page': page_number,
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
                    'page': page_number,
                    'text': ''
                }
                section_content = []
            elif any(element.category == item for item in ['NarrativeText', 'UncategorizedText', 'ListItem']):
                section_content.append(element.text)
        if section_content:
            cur_section['text'] =  "\n".join(section_content)
        all_sections.append(cur_section)
        
        return all_sections
    
    def parse_page_without_tables(self, pdf_path: str, page_number: int) -> Dict:
        pass