#!/usr/bin/env python3
"""
Process CIM PDFs to detect SBA pre-qualification status using OpenAI API.
Uses a multi-step approach:
1. Check Executive Summary for SBA indicators
2. Cross-reference with database listing titles
3. Analyze full CIM if needed
4. Mark as undetermined if unclear
"""

import os
import json
import re
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import PyPDF2
import openai
from concurrent.futures import ThreadPoolExecutor, as_completed
import pymysql
import pandas as pd
from datetime import datetime
import time

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CACHE_DIR = Path('cache/sba_analysis')
CIMS_DIR = Path('/Users/markdaoust/Developer/ql_stats/cims')
MAX_WORKERS = 3  # Parallel processing threads
RATE_LIMIT_DELAY = 1  # Seconds between API calls

# Create cache directory
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY

def get_db_connection():
    return pymysql.connect(
        host='127.0.0.1',
        port=3307,
        user='forge',
        password='mFGaHKEBBYLqpnUV3VUW',
        database='ac_prod',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def get_cache_key(file_path: str) -> str:
    """Generate cache key for a CIM file."""
    return hashlib.md5(file_path.encode()).hexdigest()

def load_from_cache(file_path: str) -> Optional[Dict]:
    """Load cached analysis results."""
    cache_key = get_cache_key(file_path)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None

def save_to_cache(file_path: str, result: Dict):
    """Save analysis results to cache."""
    cache_key = get_cache_key(file_path)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    with open(cache_file, 'w') as f:
        json.dump(result, f, indent=2)

def extract_listing_id(filename: str) -> Optional[int]:
    """Extract listing ID from CIM filename."""
    match = re.match(r'^(\d+)[_\-]', filename)
    if match:
        return int(match.group(1))
    return None

def extract_pdf_text(pdf_path: str, max_pages: int = None) -> Tuple[str, int]:
    """Extract text from PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            text = ""
            pages_to_read = min(max_pages, total_pages) if max_pages else total_pages
            
            for page_num in range(pages_to_read):
                page = pdf_reader.pages[page_num]
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page.extract_text()
            
            return text, total_pages
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return "", 0

def analyze_with_openai(text: str, prompt_template: str) -> Dict:
    """Send text to OpenAI for analysis."""
    try:
        # Limit text length to avoid token limits
        max_chars = 12000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[Text truncated for analysis]"
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing business documents for SBA loan qualification indicators."},
                {"role": "user", "content": prompt_template.format(content=text)}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content
        
        # Try to parse as JSON
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            # Fallback to text parsing
            return {
                "sba_status": "undetermined",
                "confidence": 0.0,
                "evidence": [result_text],
                "page_numbers": [],
                "analysis_note": "Could not parse structured response"
            }
            
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return {
            "sba_status": "error",
            "confidence": 0.0,
            "evidence": [],
            "error": str(e)
        }

def analyze_executive_summary(pdf_text: str) -> Dict:
    """Analyze Executive Summary for SBA indicators."""
    
    # Extract first 3 pages (usually contains exec summary)
    pages = pdf_text.split('--- Page')[:4]
    exec_summary = ''.join(pages)
    
    prompt = """
    Analyze this Executive Summary section of a business listing to determine SBA pre-qualification status.
    
    Look for these PRIMARY indicators:
    - Explicit mention of "SBA Pre-Qualified", "SBA Qualified", or "SBA Approved"
    - Tables or sections labeled "Financing Options" that mention SBA
    - Checkmarks, bullets, or "Yes" next to SBA-related items
    - Statements like "Buyer can use SBA loan" or "SBA financing available"
    
    Look for these SECONDARY indicators:
    - "90% financing available" or "10% down payment"
    - "Government-backed loan eligible"
    - "Meets SBA requirements"
    - Financial metrics: positive cash flow, 2+ years history, SDE > $100k
    
    Look for DISQUALIFYING factors:
    - "Not SBA eligible" or "No SBA financing"
    - Real estate heavy (>50% of business value)
    - Less than 2 years operating history
    - Negative cash flow
    
    Return a JSON response:
    {{
        "sba_status": "qualified" | "not_qualified" | "undetermined",
        "confidence": 0.0-1.0,
        "evidence": ["exact quotes from the text"],
        "page_numbers": [1, 2, 3],
        "disqualifying_factors": ["any factors found"]
    }}
    
    Content to analyze:
    {content}
    """
    
    return analyze_with_openai(exec_summary, prompt)

def analyze_full_cim(pdf_text: str) -> Dict:
    """Analyze full CIM for SBA indicators if Executive Summary is inconclusive."""
    
    prompt = """
    Analyze this full business listing document for SBA loan eligibility indicators.
    
    Since the Executive Summary was inconclusive, look throughout the document for:
    
    FINANCIAL INDICATORS of SBA eligibility:
    - SDE (Seller's Discretionary Earnings) > $100,000
    - Positive cash flow for 2+ consecutive years
    - Debt service coverage ratio > 1.25
    - Business operating for 2+ years
    
    BUSINESS MODEL INDICATORS:
    - Online/digital business (favorable for SBA)
    - Limited physical assets or inventory
    - Owner working <40 hours/week (absentee friendly)
    - Transferable operations and systems
    
    EXPLICIT MENTIONS anywhere in document:
    - SBA, Small Business Administration
    - Government loans, bank financing
    - Down payment structures (10%, 20%, etc.)
    - Seller financing combined with bank loans
    
    NEGATIVE INDICATORS:
    - Heavy real estate component
    - Declining revenue trend
    - High customer concentration
    - Regulatory or legal issues
    
    Return a JSON response:
    {{
        "sba_status": "qualified" | "not_qualified" | "undetermined",
        "confidence": 0.0-1.0,
        "evidence": ["specific findings with context"],
        "financial_metrics": {{"sde": "amount if found", "years_operating": "number if found"}},
        "business_characteristics": ["relevant characteristics found"]
    }}
    
    Content to analyze:
    {content}
    """
    
    return analyze_with_openai(pdf_text, prompt)

def check_database_title(listing_id: int) -> Dict:
    """Check if listing title in database indicates SBA status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name 
        FROM listings 
        WHERE id = %s
    """, (listing_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        name = result['name'].lower()
        
        # Check for SBA indicators in title
        if 'sba' in name:
            if 'not sba' in name or 'no sba' in name:
                return {"title_indicates_sba": False, "title": result['name']}
            else:
                return {"title_indicates_sba": True, "title": result['name']}
        
    return {"title_indicates_sba": None, "title": result.get('name', '') if result else ''}

def process_single_cim(cim_path: Path) -> Dict:
    """Process a single CIM file for SBA status."""
    
    # Extract listing ID
    listing_id = extract_listing_id(cim_path.name)
    if not listing_id:
        return {
            "file": cim_path.name,
            "error": "Could not extract listing ID",
            "sba_status": "error"
        }
    
    # Check cache first
    cached = load_from_cache(str(cim_path))
    if cached:
        print(f"Using cached result for {cim_path.name}")
        return cached
    
    print(f"Processing {cim_path.name} (ID: {listing_id})")
    
    # Initialize result
    result = {
        "file": cim_path.name,
        "listing_id": listing_id,
        "timestamp": datetime.now().isoformat(),
        "sba_status": "undetermined",
        "confidence": 0.0,
        "evidence": [],
        "source": "unknown"
    }
    
    try:
        # Step 1: Check database title
        db_info = check_database_title(listing_id)
        result["database_title"] = db_info["title"]
        
        # Step 2: Extract PDF text
        pdf_text, total_pages = extract_pdf_text(str(cim_path), max_pages=15)
        result["total_pages"] = total_pages
        
        if not pdf_text:
            result["error"] = "Could not extract PDF text"
            result["sba_status"] = "error"
            save_to_cache(str(cim_path), result)
            return result
        
        # Step 3: Analyze Executive Summary
        exec_analysis = analyze_executive_summary(pdf_text)
        time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
        
        if exec_analysis.get("confidence", 0) > 0.7:
            # High confidence from executive summary
            result.update(exec_analysis)
            result["source"] = "executive_summary"
        else:
            # Step 4: Analyze full CIM if needed
            print(f"  Analyzing full CIM for {cim_path.name}...")
            full_analysis = analyze_full_cim(pdf_text)
            time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
            
            # Combine evidence from both analyses
            result["sba_status"] = full_analysis.get("sba_status", "undetermined")
            result["confidence"] = max(
                exec_analysis.get("confidence", 0),
                full_analysis.get("confidence", 0)
            )
            result["evidence"] = (
                exec_analysis.get("evidence", []) + 
                full_analysis.get("evidence", [])
            )
            result["source"] = "full_analysis"
            
            # Add additional details if found
            if "financial_metrics" in full_analysis:
                result["financial_metrics"] = full_analysis["financial_metrics"]
            if "business_characteristics" in full_analysis:
                result["business_characteristics"] = full_analysis["business_characteristics"]
        
        # Step 5: Consider database title as supporting evidence
        if db_info["title_indicates_sba"] is not None:
            if db_info["title_indicates_sba"]:
                if result["sba_status"] == "undetermined":
                    result["sba_status"] = "qualified"
                    result["confidence"] = min(0.6, result["confidence"] + 0.2)
                    result["evidence"].append(f"Database title suggests SBA: {db_info['title']}")
            else:
                if result["sba_status"] == "qualified":
                    result["confidence"] = max(0.3, result["confidence"] - 0.3)
                    result["evidence"].append(f"Database title suggests NO SBA: {db_info['title']}")
        
    except Exception as e:
        result["error"] = str(e)
        result["sba_status"] = "error"
        print(f"  Error processing {cim_path.name}: {e}")
    
    # Save to cache
    save_to_cache(str(cim_path), result)
    
    return result

def process_all_cims(limit: int = None) -> pd.DataFrame:
    """Process all CIM files in parallel."""
    
    # Get list of CIM files
    cim_files = list(CIMS_DIR.glob("*.pdf"))
    
    if limit:
        cim_files = cim_files[:limit]
    
    print(f"Found {len(cim_files)} CIM files to process")
    
    results = []
    
    # Process in parallel with rate limiting
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_cim, cim): cim for cim in cim_files}
        
        for future in as_completed(futures):
            cim = futures[future]
            try:
                result = future.result()
                results.append(result)
                
                # Progress update
                status = result.get("sba_status", "unknown")
                confidence = result.get("confidence", 0)
                print(f"  Completed {cim.name}: {status} (confidence: {confidence:.2f})")
                
            except Exception as e:
                print(f"  Failed to process {cim.name}: {e}")
                results.append({
                    "file": cim.name,
                    "error": str(e),
                    "sba_status": "error"
                })
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    
    # Save results
    output_file = 'sba_cim_analysis.json'
    df.to_json(output_file, orient='records', indent=2)
    print(f"\nResults saved to {output_file}")
    
    # Summary statistics
    print("\nSBA Status Summary:")
    print(df['sba_status'].value_counts())
    
    print("\nConfidence Distribution:")
    print(f"High confidence (>0.7): {len(df[df['confidence'] > 0.7])}")
    print(f"Medium confidence (0.4-0.7): {len(df[(df['confidence'] >= 0.4) & (df['confidence'] <= 0.7)])}")
    print(f"Low confidence (<0.4): {len(df[df['confidence'] < 0.4])}")
    
    undetermined = df[df['sba_status'] == 'undetermined']
    if not undetermined.empty:
        print(f"\nUndetermined cases requiring human review: {len(undetermined)}")
        print(undetermined[['file', 'listing_id', 'confidence']].head(10))
    
    return df

if __name__ == "__main__":
    print("SBA Pre-Qualification Analysis from CIMs")
    print("=" * 60)
    
    # Test with a small batch first
    print("\nProcessing CIMs (limiting to 5 for testing)...")
    results_df = process_all_cims(limit=5)
    
    print("\nSample results:")
    print(results_df[['file', 'listing_id', 'sba_status', 'confidence', 'source']].head())
    
    # Uncomment to process all CIMs
    # results_df = process_all_cims()