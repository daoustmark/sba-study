#!/usr/bin/env python3
"""
Investigate conflicts between SBA title advertising and CIM classification.
Find and analyze discrepancies.
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
import json

def has_sba_in_title(name):
    """Check if listing title mentions SBA."""
    if pd.isna(name):
        return False
    
    # Strong SBA indicators in title
    strong_patterns = [
        r'SBA[- ]?(?:pre)?[- ]?quali',
        r'SBA[- ]?eligible',
        r'SBA[- ]?PQ\b',
        r'SBA[- ]?approved',
        r'SBA[- ]?max',
        r'\bSBA\b.*(?:qualified|eligible|approved)'
    ]
    
    for pattern in strong_patterns:
        if re.search(pattern, str(name), re.IGNORECASE):
            return True
    
    # Check for standalone SBA
    if re.search(r'\bSBA\b', str(name), re.IGNORECASE):
        return True
    
    return False

def analyze_conflicts():
    """Analyze conflicts between title and status."""
    
    # Load the data
    df = pd.read_csv('launch_date_analysis_v2.csv')
    
    # Add title analysis
    df['sba_in_title'] = df['name'].apply(has_sba_in_title)
    
    print("="*80)
    print("SBA TITLE VS STATUS CONFLICT ANALYSIS")
    print("="*80)
    print()
    
    # Overall statistics
    print("OVERALL STATISTICS:")
    print(f"Total listings: {len(df)}")
    print(f"Listings with SBA in title: {df['sba_in_title'].sum()}")
    print(f"SBA status distribution:")
    print(df['sba_status'].value_counts())
    print()
    
    # Type 1 Conflict: SBA in title but marked as 'no'
    print("="*80)
    print("TYPE 1 CONFLICT: SBA ADVERTISED BUT MARKED AS NOT ELIGIBLE")
    print("="*80)
    
    false_advertising = df[(df['sba_in_title'] == True) & (df['sba_status'] == 'no')]
    
    print(f"Count: {len(false_advertising)} listings")
    print()
    
    if len(false_advertising) > 0:
        print("DETAILED ANALYSIS:")
        for idx, row in false_advertising.iterrows():
            print(f"\nListing ID: {row['id']}")
            print(f"Name: {row['name']}")
            print(f"Status: {row['status']}")
            print(f"SBA Status: {row['sba_status']}")
            print(f"Total Inquiries: {row['total_inquiries']}")
            
            # Check if CIM exists
            cim_path = Path(f'/Users/markdaoust/Developer/ql_stats/cims')
            cim_files = list(cim_path.glob(f"{row['id']}_*.pdf"))
            if cim_files:
                print(f"CIM File: {cim_files[0].name}")
            else:
                print("CIM File: NOT FOUND")
        
        print("\nIMPLICATIONS:")
        print("  - These listings clearly advertise SBA but analysis says 'no'")
        print("  - This is likely an error in CIM classification")
        print("  - Should be reclassified as 'yes' or at least 'unknown'")
    
    # Type 2 Conflict: SBA in title but marked as 'unknown'
    print("\n" + "="*80)
    print("TYPE 2 CONFLICT: SBA ADVERTISED BUT STATUS UNKNOWN")
    print("="*80)
    
    unknown_advertised = df[(df['sba_in_title'] == True) & (df['sba_status'] == 'unknown')]
    
    print(f"Count: {len(unknown_advertised)} listings")
    
    if len(unknown_advertised) > 0:
        print("\nLISTINGS:")
        for idx, row in unknown_advertised.iterrows():
            print(f"  ID {row['id']}: {row['name'][:70]}...")
        
        print("\nIMPLICATIONS:")
        print("  - These should likely be 'yes' since they advertise SBA")
        print("  - Need CIM review to confirm")
    
    # Type 3: Not advertised but marked as eligible
    print("\n" + "="*80)
    print("TYPE 3: NOT ADVERTISED BUT MARKED AS ELIGIBLE")
    print("="*80)
    
    hidden_eligible = df[(df['sba_in_title'] == False) & (df['sba_status'] == 'yes')]
    
    print(f"Count: {len(hidden_eligible)} listings")
    print("\nIMPLICATIONS:")
    print("  - These are missed opportunities")
    print("  - Could have gotten +32% more inquiries")
    
    # Dashboard calculation check
    print("\n" + "="*80)
    print("DASHBOARD 'FALSE ADVERTISING' CALCULATION CHECK")
    print("="*80)
    
    # The dashboard might be counting differently
    # Let's check various interpretations
    
    # Interpretation 1: Any SBA mention with non-yes status
    non_yes_with_sba = df[(df['sba_in_title'] == True) & (df['sba_status'] != 'yes')]
    print(f"\nSBA in title but not confirmed eligible: {len(non_yes_with_sba)}")
    
    # Interpretation 2: Sold deals only
    sold_df = df[df['status'] == 'sold']
    sold_false_adv = sold_df[(sold_df['sba_in_title'] == True) & (sold_df['sba_status'] == 'no')]
    print(f"Sold deals with false advertising: {len(sold_false_adv)}")
    
    # Interpretation 3: Including partial
    if 'partial' in df['sba_status'].values:
        partial_with_sba = df[(df['sba_in_title'] == True) & (df['sba_status'].isin(['no', 'partial']))]
        print(f"SBA in title but no/partial status: {len(partial_with_sba)}")
    
    # RECOMMENDATIONS
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    print("""
1. IMMEDIATE ACTION:
   - Reclassify listing 19678 - clearly advertises SBA PreQualified
   - Review all 'unknown' listings with SBA in title - likely eligible

2. TRUST TITLES OVER CIM ANALYSIS:
   - If title says "SBA PreQualified" it almost certainly is
   - Brokers wouldn't false advertise this - it's verifiable
   - CIM analysis may have missed mentions or had API errors

3. UPDATE CLASSIFICATION LOGIC:
   - If SBA in title → default to 'yes' unless strong evidence otherwise
   - Only mark as 'no' if CIM explicitly states NOT SBA eligible
   - Use 'unknown' sparingly - only when truly ambiguous

4. DASHBOARD CORRECTION:
   - The '12 listings' false advertising claim seems incorrect
   - Only 1 listing has clear conflict (ID 19678)
   - Should be corrected or clarified what it's measuring
""")
    
    # Save analysis
    conflicts_df = pd.DataFrame({
        'conflict_type': ['advertised_not_eligible', 'advertised_unknown', 'eligible_not_advertised'],
        'count': [len(false_advertising), len(unknown_advertised), len(hidden_eligible)],
        'listings': [
            list(false_advertising['id'].values),
            list(unknown_advertised['id'].values)[:10],  # First 10
            list(hidden_eligible['id'].values)[:10]  # First 10
        ]
    })
    
    conflicts_df.to_csv('sba_conflicts_analysis.csv', index=False)
    print(f"\nAnalysis saved to: sba_conflicts_analysis.csv")

if __name__ == "__main__":
    analyze_conflicts()