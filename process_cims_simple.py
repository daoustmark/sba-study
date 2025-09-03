#!/usr/bin/env python3
"""
Simplified CIM processing focused on extracting SBA eligibility from Executive Summary.
Uses Grok API with better JSON handling.
"""

import os
import json
import re
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import PyPDF2
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

GROK_API_KEY = os.getenv('GROK_API_KEY')
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# Paths
CIM_DIR = Path('/Users/markdaoust/Developer/ql_stats/cims')
CACHE_DIR = Path('/Users/markdaoust/Developer/ql_stats/.cache/cim_analysis')
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def extract_listing_id(filename: str) -> Optional[int]:
    """Extract listing ID from CIM filename."""
    # Try different patterns
    patterns = [
        r'^(\d+)[_\-]',  # 12345_business_name.pdf
        r'^listing[_\-](\d+)',  # listing_12345_name.pdf
        r'[_\-](\d+)[_\-]',  # business_12345_name.pdf
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None

def extract_executive_summary(pdf_path: str) -> str:
    """Extract first 8 pages which usually contain Executive Summary and Financial Quickview."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            text = ""
            # Extract more pages to ensure we get the Executive Summary
            pages_to_read = min(8, total_pages)
            
            for page_num in range(pages_to_read):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page_text
            
            return text
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""

def analyze_with_grok(text: str, listing_id: int) -> Dict:
    """Send text to Grok for SBA analysis with improved JSON handling."""
    
    # Simple, focused prompt
    prompt = """Analyze this business document excerpt for SBA loan eligibility.

Look specifically for:
1. A "Financial Quickview" or similar table with "SBA Eligible" field
2. Direct statements about SBA qualification/eligibility
3. Mentions that seller is in Canada (which disqualifies SBA)

Document text:
{text}

Respond with ONLY a JSON object (no markdown, no explanation) in this exact format:
{{
  "listing_id": {listing_id},
  "sba_eligible": "yes|no|unknown",
  "sba_evidence": "quote from document or 'not found'",
  "seller_location": "location if mentioned or unknown",
  "asking_price": 0,
  "sde": 0
}}"""

    try:
        headers = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Use grok-2-1212 as the model name
        data = {
            "model": "grok-2-1212",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are analyzing business documents. Return ONLY valid JSON with no additional text or formatting."
                },
                {
                    "role": "user", 
                    "content": prompt.format(text=text[:15000], listing_id=listing_id)  # Limit text
                }
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }
        
        response = requests.post(GROK_API_URL, headers=headers, json=data, timeout=30)
        
        # Debug: print response if error
        if response.status_code != 200:
            print(f"API Error: {response.status_code}")
            print(f"Response: {response.text}")
        
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Clean up response - remove markdown code blocks if present
        content = content.strip()
        if '```json' in content:
            # Extract JSON from markdown code block
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            # Extract from generic code block
            parts = content.split('```')
            if len(parts) >= 2:
                content = parts[1]
                if content.startswith('json'):
                    content = content[4:]
        
        # Try to parse JSON
        try:
            parsed = json.loads(content.strip())
            return parsed
        except json.JSONDecodeError:
            # Try to extract JSON object from text
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            # Return default if parsing fails
            return {
                "listing_id": listing_id,
                "sba_eligible": "unknown",
                "sba_evidence": "JSON parsing failed",
                "seller_location": "unknown",
                "asking_price": 0,
                "sde": 0
            }
            
    except Exception as e:
        print(f"Grok API error for listing {listing_id}: {e}")
        return {
            "listing_id": listing_id,
            "sba_eligible": "unknown",
            "sba_evidence": f"API error: {str(e)}",
            "seller_location": "unknown",
            "asking_price": 0,
            "sde": 0
        }

def process_single_cim(pdf_path: Path) -> Dict:
    """Process a single CIM file."""
    filename = pdf_path.name
    listing_id = extract_listing_id(filename)
    
    if listing_id is None:
        print(f"Could not extract listing ID from: {filename}")
        return None
    
    # Check cache
    cache_file = CACHE_DIR / f"{listing_id}_simple.json"
    if cache_file.exists():
        print(f"Using cached result for listing {listing_id}")
        with open(cache_file, 'r') as f:
            return json.load(f)
    
    print(f"Processing listing {listing_id}: {filename}")
    
    # Extract text from Executive Summary area
    text = extract_executive_summary(str(pdf_path))
    
    if not text:
        result = {
            "listing_id": listing_id,
            "filename": filename,
            "sba_eligible": "unknown",
            "sba_evidence": "Could not extract text",
            "seller_location": "unknown",
            "asking_price": 0,
            "sde": 0
        }
    else:
        # Analyze with Grok
        result = analyze_with_grok(text, listing_id)
        result["filename"] = filename
    
    # Save to cache
    with open(cache_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    # Rate limiting
    time.sleep(0.5)
    
    return result

def test_batch(num_files: int = 5):
    """Test processing on a small batch of files."""
    
    print("=" * 80)
    print(f"TESTING CIM PROCESSING - {num_files} FILES")
    print("=" * 80)
    
    # Get PDF files
    pdf_files = list(CIM_DIR.glob('*.pdf'))[:num_files]
    
    if not pdf_files:
        print("No PDF files found in CIM directory!")
        return []
    
    results = []
    for pdf_path in pdf_files:
        result = process_single_cim(pdf_path)
        if result:
            results.append(result)
            
            # Display result
            print(f"\nListing {result['listing_id']}:")
            print(f"  SBA Eligible: {result['sba_eligible']}")
            print(f"  Evidence: {result['sba_evidence'][:100]}...")
            print(f"  Location: {result['seller_location']}")
    
    # Save test results
    output_file = 'cim_test_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📁 Test results saved to {output_file}")
    
    # Summary
    sba_yes = sum(1 for r in results if r['sba_eligible'] == 'yes')
    sba_no = sum(1 for r in results if r['sba_eligible'] == 'no')
    sba_unknown = sum(1 for r in results if r['sba_eligible'] == 'unknown')
    
    print(f"\nSummary:")
    print(f"  SBA Eligible: {sba_yes}")
    print(f"  Not Eligible: {sba_no}")
    print(f"  Unknown: {sba_unknown}")
    
    return results

def process_all_cims(max_workers: int = 5):
    """Process all CIM files with parallel execution."""
    
    print("=" * 80)
    print("PROCESSING ALL CIM FILES")
    print("=" * 80)
    
    # Get all PDF files
    pdf_files = list(CIM_DIR.glob('*.pdf'))
    total_files = len(pdf_files)
    
    print(f"Found {total_files} PDF files to process")
    print(f"Using {max_workers} parallel workers")
    
    results = []
    failed = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pdf = {executor.submit(process_single_cim, pdf): pdf for pdf in pdf_files}
        
        for future in as_completed(future_to_pdf):
            pdf = future_to_pdf[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
                    print(f"✓ Processed: {pdf.name}")
            except Exception as e:
                print(f"✗ Failed: {pdf.name} - {e}")
                failed.append(pdf.name)
    
    # Save all results
    output_file = f'cim_analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📁 Results saved to {output_file}")
    
    # Summary statistics
    sba_yes = sum(1 for r in results if r['sba_eligible'] == 'yes')
    sba_no = sum(1 for r in results if r['sba_eligible'] == 'no')
    sba_unknown = sum(1 for r in results if r['sba_eligible'] == 'unknown')
    
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"Total Processed: {len(results)}/{total_files}")
    print(f"SBA Eligible: {sba_yes} ({sba_yes/len(results)*100:.1f}%)")
    print(f"Not Eligible: {sba_no} ({sba_no/len(results)*100:.1f}%)")
    print(f"Unknown: {sba_unknown} ({sba_unknown/len(results)*100:.1f}%)")
    
    if failed:
        print(f"\nFailed to process {len(failed)} files:")
        for f in failed[:5]:
            print(f"  - {f}")
    
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'all':
        # Process all files
        process_all_cims()
    else:
        # Test with 5 files first
        test_batch(5)