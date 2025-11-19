from index_parser_openai_vision import OpenaiVisonIndexParser
import os
from dotenv import load_dotenv
from pathlib import Path
from parser import ProspectusParser
import json

# Load environment variables from .env file
load_dotenv()

def example_basic_usage():
    """Basic usage example"""
    api_key=os.getenv("OPENAI_API_KEY")
    # Initialize parser
    parser = OpenaiVisonIndexParser(api_key)
    doc_type = "supplement"
    # Extract index
    script_dir = Path(__file__).parent
    pdf_path =  script_dir / "JPM03_index.pdf"
    index_data = parser.extract_index(str(pdf_path), doc_type, 2)
    
    # Print results
    print("\n" + "=" * 60)
    print("EXTRACTED INDEX")
    print("=" * 60)
    
    for section in index_data['sections']:
        print(f"\n{section['title']} → Page {section['page']}")
        
        for subsection in section.get('subsections', []):
            print(f"  {subsection['title']} → Page {subsection['page']}")
    
    # Save to file
    parser.save_to_file(index_data, '/Users/yugao/Desktop/project/CMO-Analyst-Agent/parsed_index.json')
    
    return index_data

def parse_page_with_table():
    """Basic usage example"""
    api_key=os.getenv("OPENAI_API_KEY")
    # Initialize parser
    parser = OpenaiVisonIndexParser(api_key)
    #doc_type = "supplement"
    # Extract index
    script_dir = Path(__file__).parent
    pdf_path =  script_dir / "JPM03_summary01.pdf"
    parsed_page = parser.parse_pages_with_table(str(pdf_path), 1)
    
    # Save to file
    parser.save_parsed_page_to_file(parsed_page, '/Users/yugao/Desktop/project/CMO-Analyst-Agent/parsed_page_with_table.json')

    # Print results
    print("\n" + "=" * 60)
    print("EXTRACTED INDEX")
    print("=" * 60)
    
    for section in parsed_page:
        print(f"\n{section['title']}")
        
        if section.get('table'):
            print(section['table']['summary'])
            print(section['table']['data'][0])
    
    return parsed_page

def parse_prospectus_supplement():
    """Basic usage example"""
    # api_key=os.getenv("OPENAI_API_KEY")
    # # Initialize parser
    # parser = OpenaiVisonIndexParser(api_key)
    # doc_type = "supplement"
    # Extract index
    script_dir = Path(__file__).parent
    pdf_path =  script_dir / "JPM03_supplement.pdf"
    index_data = None
    index_file_path = '/Users/yugao/Desktop/project/CMO-Analyst-Agent/backend/saved_pages/parsed_index.json'
    with open(index_file_path, 'r') as f:
        index_data = json.load(f)
    
    parser = ProspectusParser()
    parsed_prospectus = parser.parse_prospectus(pdf_path, index_data)
    #parser.save_to_file(parsed_prospectus, '/Users/yugao/Desktop/project/CMO-Analyst-Agent/backend/saved_pages/parsed_prospectus.json')

parse_prospectus_supplement()

# def test():
#     index = {
#                 "title": "SUMMARY",
#                 "page": "S- 12345 " ,
#                 "level": 1,
#                 "sections": []
#             }
#     x = index['page'].index('-')
#     num = int(index['page'][x+1 : ].strip())
#     print(num)

# test()