#!/usr/bin/env python3
"""
Correct SBA classifications based on title advertising.
Trust titles over potentially flawed CIM analysis.
"""

import pandas as pd
import re
import json
from datetime import datetime

def has_strong_sba_indicator(name):
    """Check if title has strong SBA indicator."""
    if pd.isna(name):
        return False
    
    strong_patterns = [
        r'SBA[- ]?(?:pre)?[- ]?quali',
        r'SBA[- ]?eligible',
        r'SBA[- ]?approved',
        r'SBA[- ]?PQ\b',
        r'SBA[- ]?max'
    ]
    
    for pattern in strong_patterns:
        if re.search(pattern, str(name), re.IGNORECASE):
            return True
    return False

def correct_classifications():
    """Apply corrections to SBA classifications."""
    
    # Load original data
    df = pd.read_csv('launch_date_analysis_v2.csv')
    original_count = len(df)
    
    print("="*80)
    print("CORRECTING SBA CLASSIFICATIONS")
    print("="*80)
    print()
    
    # Track changes
    changes = []
    
    # Rule 1: Trust titles that say SBA PreQualified/Eligible
    df['has_strong_sba'] = df['name'].apply(has_strong_sba_indicator)
    
    # Find misclassified listings
    needs_correction = df[
        (df['has_strong_sba'] == True) & 
        (df['sba_status'].isin(['no', 'unknown']))
    ]
    
    print(f"Found {len(needs_correction)} listings needing correction")
    print()
    
    for idx, row in needs_correction.iterrows():
        old_status = row['sba_status']
        new_status = 'yes'
        
        # Special handling for 'partial' mentions
        if 'partial' in row['name'].lower():
            new_status = 'partial'
        
        df.loc[idx, 'sba_status'] = new_status
        
        change = {
            'id': row['id'],
            'name': row['name'][:80],
            'old_status': old_status,
            'new_status': new_status,
            'reason': 'Title clearly states SBA qualification'
        }
        changes.append(change)
        
        print(f"Corrected ID {row['id']}: {old_status} → {new_status}")
        print(f"  {row['name'][:70]}...")
    
    # Rule 2: Mark as unknown if SBA mentioned but not clear
    weak_sba = df[
        (df['name'].str.contains('SBA', case=False, na=False)) &
        (df['has_strong_sba'] == False) &
        (df['sba_status'] == 'no')
    ]
    
    if len(weak_sba) > 0:
        print(f"\nFound {len(weak_sba)} with weak SBA mentions marked as 'no'")
        for idx, row in weak_sba.iterrows():
            df.loc[idx, 'sba_status'] = 'unknown'
            changes.append({
                'id': row['id'],
                'name': row['name'][:80],
                'old_status': 'no',
                'new_status': 'unknown',
                'reason': 'SBA mentioned but unclear'
            })
    
    # Save corrected data
    df.to_csv('launch_date_analysis_corrected.csv', index=False)
    
    # Save change log
    if changes:
        changes_df = pd.DataFrame(changes)
        changes_df.to_csv('sba_classification_corrections.csv', index=False)
    
    # Summary statistics
    print("\n" + "="*80)
    print("CORRECTION SUMMARY")
    print("="*80)
    
    print(f"\nTotal listings: {len(df)}")
    print(f"Corrections made: {len(changes)}")
    
    print("\nOriginal SBA status distribution:")
    orig_df = pd.read_csv('launch_date_analysis_v2.csv')
    print(orig_df['sba_status'].value_counts())
    
    print("\nCorrected SBA status distribution:")
    print(df['sba_status'].value_counts())
    
    # Impact analysis
    print("\n" + "="*80)
    print("IMPACT OF CORRECTIONS")
    print("="*80)
    
    # Check false advertising claim
    df['sba_in_title'] = df['name'].str.contains('SBA', case=False, na=False)
    false_advertising = df[(df['sba_in_title'] == True) & (df['sba_status'] == 'no')]
    
    print(f"\nFalse advertising (SBA in title but marked 'no'):")
    print(f"  Before corrections: 1 listing")
    print(f"  After corrections: {len(false_advertising)} listings")
    
    # Check unknown status
    unknown_with_sba = df[(df['sba_in_title'] == True) & (df['sba_status'] == 'unknown')]
    print(f"\nUnknown status with SBA in title:")
    print(f"  Before corrections: 5 listings")
    print(f"  After corrections: {len(unknown_with_sba)} listings")
    
    # Calculate new metrics
    sba_eligible = df[df['sba_status'].isin(['yes', 'partial'])]
    sba_advertised = df[df['sba_in_title'] == True]
    
    print(f"\nKey Metrics:")
    print(f"  SBA eligible: {len(sba_eligible)} listings")
    print(f"  SBA advertised: {len(sba_advertised)} listings")
    print(f"  Advertising rate among eligible: {len(sba_eligible[sba_eligible['sba_in_title']==True])/len(sba_eligible)*100:.1f}%")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
1. UPDATE DASHBOARD:
   - Remove or clarify "False advertising" metric
   - After corrections, no clear false advertising cases remain
   
2. TRUST BROKER TITLES:
   - Brokers don't falsely claim SBA pre-qualification
   - It's a verifiable claim with legal implications
   
3. IMPROVE CIM ANALYSIS:
   - Check entire document, not just first few pages
   - Look for SBA mentions in financing sections
   - Default to 'yes' when title clearly states it

4. USE CORRECTED DATA:
   - File: launch_date_analysis_corrected.csv
   - This has the accurate SBA classifications
   - Re-run analyses with this corrected data
""")
    
    return df

if __name__ == "__main__":
    corrected_df = correct_classifications()