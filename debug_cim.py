#!/usr/bin/env python3
"""
Debug CIM extraction to see what text we're getting.
"""

import PyPDF2
from pathlib import Path

def extract_and_show(pdf_path: str, pages: int = 3):
    """Extract and display text from PDF."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            print(f"PDF: {Path(pdf_path).name}")
            print(f"Total pages: {total_pages}")
            print("=" * 80)
            
            for page_num in range(min(pages, total_pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                print(f"\n--- Page {page_num + 1} ---")
                print(text[:1500])  # First 1500 chars of each page
                
                # Look for SBA mentions
                if 'sba' in text.lower():
                    print("\n>>> FOUND SBA MENTION! <<<")
                    # Find context around SBA
                    lines = text.split('\n')
                    for i, line in enumerate(lines):
                        if 'sba' in line.lower():
                            # Print surrounding lines
                            start = max(0, i-2)
                            end = min(len(lines), i+3)
                            for j in range(start, end):
                                if j == i:
                                    print(f">>> {lines[j]}")
                                else:
                                    print(f"    {lines[j]}")
                
                # Look for Financial Quickview
                if 'financial quickview' in text.lower() or 'financial quick view' in text.lower():
                    print("\n>>> FOUND FINANCIAL QUICKVIEW! <<<")
                    # Print the section
                    lines = text.split('\n')
                    in_table = False
                    for line in lines:
                        if 'financial quick' in line.lower():
                            in_table = True
                        if in_table:
                            print(f"    {line}")
                            if 'asking' in line.lower() and 'multiple' in line.lower():
                                break  # End of typical quickview table
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test with first CIM
    cim_dir = Path('/Users/markdaoust/Developer/ql_stats/cims')
    pdf_files = list(cim_dir.glob('*.pdf'))[:1]
    
    if pdf_files:
        extract_and_show(str(pdf_files[0]), pages=5)