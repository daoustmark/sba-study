#!/usr/bin/env python3
"""
Generate a plain-spoken, actionable report from the fact-check analysis using Grok 4 API.
"""
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/markdaoust/Developer/ql_stats/.env')

def call_grok_api(prompt, api_key):
    """Call Grok 4 API to process the fact-check report."""
    url = "https://api.x.ai/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "grok-2-1212",
        "messages": [
            {
                "role": "system",
                "content": """You are an academic researcher writing a fact-checking report for internal use at a business brokerage.

CRITICAL INSTRUCTIONS:
- Write in plain, direct language - NO business jargon or corporate speak
- Be brutally honest about what we found - no sugar-coating
- Focus on what actually matters for making decisions
- Skip the self-congratulation - we're checking our own work, not patting ourselves on the back
- Be specific with numbers and findings
- Explain things clearly without dumbing them down
- Write like you're explaining to a smart colleague, not selling to a client

The goal is academic rigor with plain English. Think more like a research paper abstract than a consulting report."""
            },
            {
                "role": "user", 
                "content": f"""Take this technical fact-check and turn it into a clear, actionable report. 

Remember:
- NO phrases like "underscores the strategic importance" or "comprehensive fact-checking analysis" 
- YES to phrases like "we found that" and "this means we should"
- Don't celebrate the verification process - just report what we found
- Be direct about problems and discrepancies
- Focus on what this means for actual business decisions

Technical Fact-Check Report:
{prompt}

Write a report that:
1. Starts with what we were checking and why it matters
2. States clearly what we found - both good and bad
3. Explains the discrepancies without excuses
4. Tells us what we should actually DO based on these findings
5. Ends with confidence level and key takeaways

Write it like you're talking to someone who needs to make decisions, not someone you're trying to impress."""
            }
        ],
        "temperature": 0.6,
        "max_tokens": 4000
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
    
    except requests.exceptions.RequestException as e:
        print(f"Error calling Grok API: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response content: {e.response.text}")
        raise

def main():
    """Main execution function."""
    print("Loading fact-check report...")
    
    # Read the fact-check report
    fact_check_path = Path('/Users/markdaoust/Developer/ql_stats/scripts/sba_analysis/fact_check_report_detailed.md')
    with open(fact_check_path, 'r') as f:
        fact_check_content = f.read()
    
    # Get Grok API key
    api_key = os.getenv('GROK_API_KEY')
    if not api_key:
        raise ValueError("GROK_API_KEY not found in environment variables")
    
    print("Calling Grok 4 API to generate plain-spoken report...")
    
    # Generate the report using Grok
    written_report = call_grok_api(fact_check_content, api_key)
    
    # Save the written report
    output_path = Path('/Users/markdaoust/Developer/ql_stats/scripts/sba_analysis/SBA_Fact_Check_Plain_Report.md')
    with open(output_path, 'w') as f:
        f.write("# Fact-Checking the SBA Impact Analysis: What We Actually Found\n\n")
        f.write("*Internal verification report for Quiet Light Brokerage*\n\n")
        f.write("---\n\n")
        f.write(written_report)
    
    print(f"Plain-spoken report saved to: {output_path}")
    
    # Also save a copy with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f'/Users/markdaoust/Developer/ql_stats/scripts/sba_analysis/reports/SBA_Plain_Report_{timestamp}.md')
    backup_path.parent.mkdir(exist_ok=True)
    
    with open(backup_path, 'w') as f:
        f.write("# Fact-Checking the SBA Impact Analysis: What We Actually Found\n\n")
        f.write("*Internal verification report for Quiet Light Brokerage*\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n")
        f.write("---\n\n")
        f.write(written_report)
    
    print(f"Backup saved to: {backup_path}")
    
    return written_report

if __name__ == "__main__":
    main()