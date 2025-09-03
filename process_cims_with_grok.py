#!/usr/bin/env python3
"""
Process CIM PDFs to detect SBA pre-qualification status using Grok API.
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
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import pymysql
import pandas as pd
from datetime import datetime
import time

# Configuration
GROK_API_KEY = os.getenv('GROK_API_KEY')
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
CACHE_DIR = Path('cache/sba_analysis')
CIMS_DIR = Path('/Users/markdaoust/Developer/ql_stats/cims')
MAX_WORKERS = 5  # Can handle more parallel requests with Grok
RATE_LIMIT_DELAY = 0.5  # Grok typically has higher rate limits

# Create cache directory
CACHE_DIR.mkdir(parents=True, exist_ok=True)

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
    cache_file = CACHE_DIR / f"{cache_key}_grok.json"
    
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None

def save_to_cache(file_path: str, result: Dict):
    """Save analysis results to cache."""
    cache_key = get_cache_key(file_path)
    cache_file = CACHE_DIR / f"{cache_key}_grok.json"
    
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

def analyze_with_grok(text: str, prompt_template: str, model: str = "grok-2-1212") -> Dict:
    """Send text to Grok for analysis."""
    try:
        # Limit text length to avoid token limits
        max_chars = 30000  # Grok has higher limits than GPT-4
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[Text truncated for analysis]"
        
        headers = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {
                    "role": "system", 
                    "content": "You are an expert at analyzing business documents for SBA loan qualification indicators. Always respond with valid JSON."
                },
                {
                    "role": "user", 
                    "content": prompt_template.format(content=text)
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}  # Force JSON response
        }
        
        response = requests.post(GROK_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Parse JSON response
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "sba_status": "undetermined",
                    "confidence": 0.0,
                    "evidence": [content],
                    "page_numbers": [],
                    "analysis_note": "Could not parse structured response"
                }
            
    except requests.exceptions.RequestException as e:
        print(f"Grok API error: {e}")
        return {
            "sba_status": "error",
            "confidence": 0.0,
            "evidence": [],
            "error": str(e)
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            "sba_status": "error",
            "confidence": 0.0,
            "evidence": [],
            "error": str(e)
        }

def analyze_executive_summary(pdf_text: str) -> Dict:
    """Analyze Executive Summary for SBA indicators using Grok."""
    
    # Extract first 3-4 pages (usually contains exec summary)
    pages = pdf_text.split('--- Page')[:5]
    exec_summary = ''.join(pages)
    
    prompt = """
    Analyze this Executive Summary section of a business listing to determine SBA pre-qualification status.
    
    IMPORTANT: Return your response as a valid JSON object with this exact structure:
    {
        "sba_status": "qualified" or "not_qualified" or "undetermined",
        "confidence": 0.0 to 1.0,
        "evidence": ["list", "of", "exact", "quotes"],
        "page_numbers": [1, 2, 3],
        "disqualifying_factors": ["any", "factors", "found"]
    }
    
    Look for these PRIMARY indicators of SBA qualification:
    - Explicit text: "SBA Pre-Qualified", "SBA Qualified", "SBA Approved", "SBA Eligible"
    - Tables or sections labeled "Financing Options" that mention SBA
    - Checkmarks, bullets, or "Yes" next to SBA-related items
    - Statements like "Buyer can use SBA loan" or "SBA financing available"
    - "Lender pre-qualified" or "Bank approved"
    
    Look for these SECONDARY indicators:
    - "90% financing available" or "10% down payment" 
    - "Government-backed loan eligible"
    - "Meets SBA requirements"
    - Strong financial metrics: positive cash flow, 2+ years history, SDE > $100k
    - Mentions of "conventional financing" available
    
    Look for DISQUALIFYING factors:
    - "Not SBA eligible" or "No SBA financing"
    - "Cash only" or "All cash transaction required"
    - Real estate heavy (>50% of business value)
    - Less than 2 years operating history
    - Negative cash flow or declining revenue
    - Adult/cannabis/gambling related business
    
    Content to analyze:
    {content}
    """
    
    return analyze_with_grok(exec_summary, prompt)

def analyze_full_cim(pdf_text: str) -> Dict:
    """Analyze full CIM for SBA indicators if Executive Summary is inconclusive."""
    
    prompt = """
    Analyze this full business listing document for SBA loan eligibility indicators.
    The Executive Summary was inconclusive, so search the entire document carefully.
    
    IMPORTANT: Return your response as a valid JSON object with this exact structure:
    {
        "sba_status": "qualified" or "not_qualified" or "undetermined",
        "confidence": 0.0 to 1.0,
        "evidence": ["specific", "findings", "with", "context"],
        "financial_metrics": {"sde": "amount if found", "years_operating": "number if found", "cash_flow": "positive/negative"},
        "business_characteristics": ["relevant", "characteristics", "found"]
    }
    
    Search for FINANCIAL INDICATORS of SBA eligibility:
    - SDE (Seller's Discretionary Earnings) > $100,000
    - Positive cash flow for 2+ consecutive years
    - Debt service coverage ratio > 1.25
    - Business operating for 2+ years
    - Revenue trends (growing or stable)
    
    Search for BUSINESS MODEL INDICATORS:
    - Online/digital business (favorable for SBA)
    - E-commerce or SaaS model
    - Limited physical assets or inventory (<20% of value)
    - Owner working <40 hours/week (absentee friendly)
    - Transferable operations and systems
    - Clean books and records
    
    Search for EXPLICIT MENTIONS anywhere:
    - "SBA", "Small Business Administration"
    - "Government loans", "bank financing", "conventional loan"
    - Down payment structures (10%, 15%, 20%, etc.)
    - Seller financing combined with bank loans
    - "Financing available" or "lending options"
    
    Search for NEGATIVE INDICATORS:
    - Heavy real estate component (>50% of value)
    - Declining revenue trend over 2+ years
    - High customer concentration (>30% from one customer)
    - Regulatory or legal issues mentioned
    - Industry restrictions (adult, cannabis, gambling)
    - International or offshore operations
    
    Content to analyze:
    {content}
    """
    
    return analyze_with_grok(pdf_text, prompt)

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
    """Process a single CIM file for SBA status using Grok."""
    
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
    
    print(f"Processing {cim_path.name} (ID: {listing_id}) with Grok")
    
    # Initialize result
    result = {
        "file": cim_path.name,
        "listing_id": listing_id,
        "timestamp": datetime.now().isoformat(),
        "sba_status": "undetermined",
        "confidence": 0.0,
        "evidence": [],
        "source": "unknown",
        "model": "grok-2-1212"
    }
    
    try:
        # Step 1: Check database title
        db_info = check_database_title(listing_id)
        result["database_title"] = db_info["title"]
        
        # Step 2: Extract PDF text (more pages for Grok's larger context)
        pdf_text, total_pages = extract_pdf_text(str(cim_path), max_pages=20)
        result["total_pages"] = total_pages
        
        if not pdf_text:
            result["error"] = "Could not extract PDF text"
            result["sba_status"] = "error"
            save_to_cache(str(cim_path), result)
            return result
        
        # Step 3: Analyze Executive Summary with Grok
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

def process_all_cims(limit: int = None, start_from: int = 0) -> pd.DataFrame:
    """Process all CIM files in parallel using Grok."""
    
    # Get list of CIM files
    cim_files = sorted(list(CIMS_DIR.glob("*.pdf")))
    
    # Apply start and limit
    if start_from:
        cim_files = cim_files[start_from:]
    if limit:
        cim_files = cim_files[:limit]
    
    print(f"Found {len(cim_files)} CIM files to process (starting from index {start_from})")
    print(f"Using Grok API with model: grok-2-1212")
    
    results = []
    
    # Process in parallel with rate limiting
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_cim, cim): cim for cim in cim_files}
        
        completed = 0
        for future in as_completed(futures):
            cim = futures[future]
            completed += 1
            try:
                result = future.result()
                results.append(result)
                
                # Progress update
                status = result.get("sba_status", "unknown")
                confidence = result.get("confidence", 0)
                print(f"  [{completed}/{len(cim_files)}] {cim.name}: {status} (confidence: {confidence:.2f})")
                
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
    output_file = 'sba_cim_analysis_grok.json'
    df.to_json(output_file, orient='records', indent=2)
    print(f"\nResults saved to {output_file}")
    
    # Summary statistics
    print("\nSBA Status Summary (Grok Analysis):")
    print(df['sba_status'].value_counts())
    
    print("\nConfidence Distribution:")
    if 'confidence' in df.columns:
        print(f"High confidence (>0.7): {len(df[df['confidence'] > 0.7])}")
        print(f"Medium confidence (0.4-0.7): {len(df[(df['confidence'] >= 0.4) & (df['confidence'] <= 0.7)])}")
        print(f"Low confidence (<0.4): {len(df[df['confidence'] < 0.4])}")
    
    undetermined = df[df['sba_status'] == 'undetermined']
    if not undetermined.empty:
        print(f"\nUndetermined cases requiring human review: {len(undetermined)}")
        print(undetermined[['file', 'listing_id', 'confidence']].head(10))
    
    # Calculate estimated cost
    total_processed = len(df[df['sba_status'] != 'error'])
    estimated_cost = total_processed * 0.003  # Grok is typically cheaper than GPT-4
    print(f"\nEstimated API cost: ${estimated_cost:.2f}")
    
    return df

def test_grok_connection():
    """Test Grok API connection with a simple request."""
    print("Testing Grok API connection...")
    
    test_prompt = "Respond with a JSON object containing a single field 'status' with value 'connected'"
    test_result = analyze_with_grok("Test", test_prompt)
    
    if test_result.get('status') == 'connected' or not test_result.get('error'):
        print("✓ Grok API connection successful!")
        return True
    else:
        print(f"✗ Grok API connection failed: {test_result.get('error', 'Unknown error')}")
        return False

if __name__ == "__main__":
    print("SBA Pre-Qualification Analysis from CIMs using Grok")
    print("=" * 60)
    
    # Test API connection first
    if not test_grok_connection():
        print("\nPlease check your Grok API key and try again.")
        exit(1)
    
    print("\nProcessing options:")
    print("1. Test with 5 CIMs")
    print("2. Process first 50 CIMs")
    print("3. Process all CIMs")
    print("4. Resume from specific index")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        print("\nProcessing 5 CIMs for testing...")
        results_df = process_all_cims(limit=5)
    elif choice == "2":
        print("\nProcessing first 50 CIMs...")
        results_df = process_all_cims(limit=50)
    elif choice == "3":
        confirm = input("This will process all 252 CIMs. Estimated cost: ~$0.75. Continue? (yes/no): ")
        if confirm.lower() == "yes":
            results_df = process_all_cims()
        else:
            print("Cancelled.")
    elif choice == "4":
        start_idx = int(input("Enter starting index (0-251): "))
        limit = input("Enter limit (or press Enter for all remaining): ").strip()
        limit = int(limit) if limit else None
        results_df = process_all_cims(limit=limit, start_from=start_idx)
    else:
        print("Invalid choice.")
    
    if 'results_df' in locals():
        print("\nSample results:")
        print(results_df[['file', 'listing_id', 'sba_status', 'confidence', 'source']].head(10))