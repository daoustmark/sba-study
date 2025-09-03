#!/usr/bin/env python3
"""
Generate a polished written report from the fact-check analysis using Grok 4 API.
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
                "content": """You are a professional business analyst writing for executive leadership at Quiet Light Brokerage. 
                Your task is to transform a technical fact-checking report into a polished, narrative-driven written report.
                
                The report should:
                1. Be written in clear, professional business language
                2. Focus on the implications and insights rather than technical details
                3. Maintain a balanced, objective tone while acknowledging both strengths and limitations
                4. Be structured as a cohesive narrative, not a checklist
                5. Emphasize strategic value and actionable insights
                6. Use specific examples and data points to support conclusions
                7. Be suitable for presentation to board members and senior leadership
                
                Do not use bullet points excessively. Write in full paragraphs with smooth transitions.
                The report should read like a professional consulting deliverable."""
            },
            {
                "role": "user", 
                "content": f"""Please transform the following technical fact-checking analysis into a polished written report 
                suitable for Quiet Light Brokerage leadership. Focus on the business implications and strategic insights 
                while maintaining accuracy about the verification findings.
                
                Technical Fact-Check Report:
                {prompt}
                
                Create a professional written report that:
                1. Opens with an executive overview of the verification process and key findings
                2. Discusses the methodological rigor and data integrity
                3. Addresses the discrepancies found in a balanced way
                4. Emphasizes the strategic implications for the business
                5. Concludes with confidence assessment and recommendations
                
                Write this as a flowing narrative document, not a technical checklist."""
            }
        ],
        "temperature": 0.7,
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
    
    print("Calling Grok 4 API to generate written report...")
    
    # Generate the report using Grok
    written_report = call_grok_api(fact_check_content, api_key)
    
    # Save the written report
    output_path = Path('/Users/markdaoust/Developer/ql_stats/scripts/sba_analysis/SBA_Verification_Written_Report.md')
    with open(output_path, 'w') as f:
        f.write("# SBA Pre-Qualification Impact Analysis: Verification Report\n\n")
        f.write("*A Data Integrity Assessment for Quiet Light Brokerage Leadership*\n\n")
        f.write("---\n\n")
        f.write(written_report)
    
    print(f"Written report saved to: {output_path}")
    
    # Also save a copy with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f'/Users/markdaoust/Developer/ql_stats/scripts/sba_analysis/reports/SBA_Verification_Report_{timestamp}.md')
    backup_path.parent.mkdir(exist_ok=True)
    
    with open(backup_path, 'w') as f:
        f.write("# SBA Pre-Qualification Impact Analysis: Verification Report\n\n")
        f.write("*A Data Integrity Assessment for Quiet Light Brokerage Leadership*\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n")
        f.write("---\n\n")
        f.write(written_report)
    
    print(f"Backup saved to: {backup_path}")
    
    return written_report

if __name__ == "__main__":
    main()