#!/usr/bin/env python3
"""
Generate verification data combining SBA actual usage with timing metrics.
"""

import pandas as pd
import json
from datetime import datetime

def generate_verification_data():
    """Generate comprehensive verification data for the dashboard."""
    
    # Load the datasets
    sba_usage_df = pd.read_csv('sba_actual_usage_analysis.csv')
    launch_df = pd.read_csv('launch_date_analysis_v2.csv')
    
    # Merge the datasets
    merged_df = pd.merge(
        sba_usage_df,
        launch_df[['id', 'days_on_market', 'days_under_loi', 'days_to_loi', 
                   'first_loi_date', 'last_loi_date', 'num_lois', 'launch_date']],
        on='id',
        how='left',
        suffixes=('', '_launch')
    )
    
    # Clean up the merge - prefer num_lois from launch_df if available
    merged_df['num_lois_final'] = merged_df['num_lois'].fillna(merged_df['total_lois'])
    
    # Create verification data for sold deals only
    sold_df = merged_df[merged_df['status'] == 'sold'].copy()
    
    # Add financing type column for clarity
    sold_df['financing_type'] = sold_df.apply(
        lambda x: 'SBA' if x['winning_loi_sba'] else 'Non-SBA', 
        axis=1
    )
    
    # Create separate DataFrames for analysis
    sba_deals = sold_df[sold_df['winning_loi_sba'] == True].copy()
    non_sba_deals = sold_df[sold_df['winning_loi_sba'] == False].copy()
    
    # Calculate statistics
    stats = {
        'sba': {
            'count': len(sba_deals),
            'median_days_on_market': sba_deals['days_on_market'].median() if len(sba_deals) > 0 else None,
            'mean_days_on_market': sba_deals['days_on_market'].mean() if len(sba_deals) > 0 else None,
            'median_days_under_loi': sba_deals['days_under_loi'].median() if len(sba_deals) > 0 else None,
            'mean_days_under_loi': sba_deals['days_under_loi'].mean() if len(sba_deals) > 0 else None,
            'median_days_to_loi': sba_deals['days_to_loi'].median() if len(sba_deals) > 0 else None,
            'mean_days_to_loi': sba_deals['days_to_loi'].mean() if len(sba_deals) > 0 else None,
            'median_commission': sba_deals['closed_commission'].median() if len(sba_deals) > 0 else None,
            'mean_commission': sba_deals['closed_commission'].mean() if len(sba_deals) > 0 else None
        },
        'non_sba': {
            'count': len(non_sba_deals),
            'median_days_on_market': non_sba_deals['days_on_market'].median() if len(non_sba_deals) > 0 else None,
            'mean_days_on_market': non_sba_deals['days_on_market'].mean() if len(non_sba_deals) > 0 else None,
            'median_days_under_loi': non_sba_deals['days_under_loi'].median() if len(non_sba_deals) > 0 else None,
            'mean_days_under_loi': non_sba_deals['days_under_loi'].mean() if len(non_sba_deals) > 0 else None,
            'median_days_to_loi': non_sba_deals['days_to_loi'].median() if len(non_sba_deals) > 0 else None,
            'mean_days_to_loi': non_sba_deals['days_to_loi'].mean() if len(non_sba_deals) > 0 else None,
            'median_commission': non_sba_deals['closed_commission'].median() if len(non_sba_deals) > 0 else None,
            'mean_commission': non_sba_deals['closed_commission'].mean() if len(non_sba_deals) > 0 else None
        }
    }
    
    # Prepare data for JavaScript
    verification_data = []
    
    for _, row in sold_df.iterrows():
        verification_data.append({
            'id': int(row['id']),
            'name': row['name'],
            'status': row['status'],
            'closed_at': row['closed_at'] if pd.notna(row['closed_at']) else None,
            'closed_commission': float(row['closed_commission']) if pd.notna(row['closed_commission']) else None,
            'total_lois': int(row['total_lois']) if pd.notna(row['total_lois']) else 0,
            'sba_lois': int(row['sba_lois']) if pd.notna(row['sba_lois']) else 0,
            'has_sba_loi': bool(row['has_sba_loi']),
            'winning_loi_sba': bool(row['winning_loi_sba']),
            'financing_type': row['financing_type'],
            'pct_sba_lois': float(row['pct_sba_lois']) if pd.notna(row['pct_sba_lois']) else 0,
            'days_on_market': int(row['days_on_market']) if pd.notna(row['days_on_market']) else None,
            'days_under_loi': int(row['days_under_loi']) if pd.notna(row['days_under_loi']) else None,
            'days_to_loi': int(row['days_to_loi']) if pd.notna(row['days_to_loi']) else None,
            'launch_date': row['launch_date'] if pd.notna(row['launch_date']) else None,
            'first_loi_date': row['first_loi_date'] if pd.notna(row['first_loi_date']) else None,
            'last_loi_date': row['last_loi_date'] if pd.notna(row['last_loi_date']) else None
        })
    
    # Sort by days_on_market for better visualization
    verification_data.sort(key=lambda x: x['days_on_market'] if x['days_on_market'] is not None else 999999)
    
    # Create JavaScript file
    js_content = f"""// SBA Verification Data
// Generated: {datetime.now().isoformat()}

const sbaVerificationData = {json.dumps(verification_data, indent=2)};

const sbaVerificationStats = {json.dumps(stats, indent=2)};

// Export for use in dashboard
if (typeof module !== 'undefined' && module.exports) {{
    module.exports = {{ sbaVerificationData, sbaVerificationStats }};
}}
"""
    
    with open('sba_verification_data.js', 'w') as f:
        f.write(js_content)
    
    print(f"Generated verification data for {len(verification_data)} sold deals")
    print(f"  - SBA financing: {stats['sba']['count']} deals")
    print(f"  - Non-SBA financing: {stats['non_sba']['count']} deals")
    
    if stats['sba']['median_days_on_market'] and stats['non_sba']['median_days_on_market']:
        diff = stats['non_sba']['median_days_on_market'] - stats['sba']['median_days_on_market']
        print(f"\nMedian days on market difference: {diff:.0f} days")
        print(f"  - SBA: {stats['sba']['median_days_on_market']:.0f} days")
        print(f"  - Non-SBA: {stats['non_sba']['median_days_on_market']:.0f} days")
    
    if stats['sba']['median_days_under_loi'] and stats['non_sba']['median_days_under_loi']:
        diff = stats['sba']['median_days_under_loi'] - stats['non_sba']['median_days_under_loi']
        print(f"\nMedian days under LOI difference: {diff:.0f} days")
        print(f"  - SBA: {stats['sba']['median_days_under_loi']:.0f} days")
        print(f"  - Non-SBA: {stats['non_sba']['median_days_under_loi']:.0f} days")
    
    return verification_data, stats

if __name__ == "__main__":
    data, stats = generate_verification_data()
    print(f"\n✅ Verification data generated: sba_verification_data.js")