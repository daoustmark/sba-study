#!/usr/bin/env python3
"""
Test processing one specific CIM to debug the extraction and API response.
"""

import os
import json
import PyPDF2
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GROK_API_KEY = os.getenv('GROK_API_KEY')
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def extract_full_text(pdf_path: str, max_pages: int = 10) -> str:
    """Extract text from PDF."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            text = ""
            pages_to_read = min(max_pages, total_pages)
            
            for page_num in range(pages_to_read):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page_text
            
            return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

def test_grok_api(text: str):
    """Test Grok API with detailed output."""
    
    prompt = """You are analyzing a business CIM document. Extract the following information:

1. Look for "SBA Eligible" or "SBA Pre-qualified" or any SBA mentions
2. Look for asking price and financial metrics
3. Look for seller location

Here is the document text:

{text}

Return a JSON object with these fields:
- sba_status: "eligible", "not_eligible", or "unknown"
- sba_evidence: exact quote from document about SBA, or "not found"
- asking_price: number or 0
- seller_location: location string or "unknown"

Return ONLY the JSON object, no other text."""

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-1212",
        "messages": [
            {"role": "user", "content": prompt.format(text=text[:10000])}
        ],
        "temperature": 0.1,
        "max_tokens": 500
    }
    
    print("Sending request to Grok API...")
    response = requests.post(GROK_API_URL, headers=headers, json=data, timeout=30)
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        print(f"\nRaw response:\n{content}\n")
        
        # Try to parse as JSON
        try:
            # Clean up response
            content = content.strip()
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.split('```')[0]
            
            parsed = json.loads(content.strip())
            print(f"Parsed JSON:\n{json.dumps(parsed, indent=2)}")
            return parsed
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Trying to clean: {content[:200]}")
    else:
        print(f"Error: {response.text}")
    
    return None

# Test with listing 13990 which should be SBA pre-qualified
pdf_path = "/Users/markdaoust/Developer/ql_stats/cims/13990_1.  Armed American Supply Business Summary.pdf"

if os.path.exists(pdf_path):
    print(f"Testing with: {Path(pdf_path).name}")
    print("=" * 80)
    
    # Extract text
    text = extract_full_text(pdf_path, max_pages=8)
    
    # Show first 2000 chars to see what we're working with
    print("First 2000 chars of extracted text:")
    print(text[:2000])
    print("\n" + "=" * 80)
    
    # Test API
    result = test_grok_api(text)
    
else:
    print(f"File not found: {pdf_path}")