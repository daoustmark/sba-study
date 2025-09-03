#!/usr/bin/env python3
"""
Generate enhanced verification data including inquiry counts.
"""

import pandas as pd
import json
from datetime import datetime

def generate_enhanced_verification():
    """Generate comprehensive verification data with inquiry information."""
    
    # Load the enhanced data with inquiries
    df = pd.read_csv('sba_analysis_with_inquiries.csv')
    
    # Filter to sold deals only for verification
    sold_df = df[df['status'] == 'sold'].copy()
    
    # Add financing type for clarity
    sold_df['financing_type'] = sold_df.apply(
        lambda x: 'SBA' if x['winning_loi_sba'] else 'Non-SBA', 
        axis=1
    )
    
    # Prepare JavaScript data
    verification_data = []
    
    for _, row in sold_df.iterrows():
        verification_data.append({
            'id': int(row['id']),
            'name': row['name'],
            'status': row['status'],
            'closed_at': row['closed_at'] if pd.notna(row['closed_at']) else None,
            'closed_commission': float(row['closed_commission']) if pd.notna(row['closed_commission']) else None,
            'total_inquiries': int(row['total_inquiries']) if pd.notna(row['total_inquiries']) else 0,
            'total_lois': int(row['total_lois']) if pd.notna(row['total_lois']) else 0,
            'sba_lois': int(row['sba_lois']) if pd.notna(row['sba_lois']) else 0,
            'has_sba_loi': bool(row['has_sba_loi']),
            'winning_loi_sba': bool(row['winning_loi_sba']),
            'financing_type': row['financing_type'],
            'pct_sba_lois': float(row['pct_sba_lois']) if pd.notna(row['pct_sba_lois']) else 0,
            'days_on_market': int(row['days_on_market']) if pd.notna(row['days_on_market']) else None,
            'days_under_loi': int(row['days_under_loi']) if pd.notna(row['days_under_loi']) else None,
            'days_to_loi': int(row['days_to_loi']) if pd.notna(row['days_to_loi']) else None
        })
    
    # Sort by total inquiries descending for better visualization
    verification_data.sort(key=lambda x: x['total_inquiries'] if x['total_inquiries'] else 0, reverse=True)
    
    # Calculate comprehensive statistics
    sba_deals = sold_df[sold_df['winning_loi_sba'] == True]
    non_sba_deals = sold_df[sold_df['winning_loi_sba'] == False]
    
    stats = {
        'sba': {
            'count': len(sba_deals),
            'median_inquiries': int(sba_deals['total_inquiries'].median()) if len(sba_deals) > 0 else 0,
            'mean_inquiries': float(sba_deals['total_inquiries'].mean()) if len(sba_deals) > 0 else 0,
            'median_days_on_market': int(sba_deals['days_on_market'].median()) if len(sba_deals) > 0 and sba_deals['days_on_market'].notna().any() else None,
            'mean_days_on_market': float(sba_deals['days_on_market'].mean()) if len(sba_deals) > 0 and sba_deals['days_on_market'].notna().any() else None,
            'median_days_under_loi': int(sba_deals['days_under_loi'].median()) if len(sba_deals) > 0 and sba_deals['days_under_loi'].notna().any() else None,
            'median_days_to_loi': int(sba_deals['days_to_loi'].median()) if len(sba_deals) > 0 and sba_deals['days_to_loi'].notna().any() else None,
            'median_commission': float(sba_deals['closed_commission'].median()) if len(sba_deals) > 0 else None,
            'total_commission': float(sba_deals['closed_commission'].sum()) if len(sba_deals) > 0 else 0
        },
        'non_sba': {
            'count': len(non_sba_deals),
            'median_inquiries': int(non_sba_deals['total_inquiries'].median()) if len(non_sba_deals) > 0 else 0,
            'mean_inquiries': float(non_sba_deals['total_inquiries'].mean()) if len(non_sba_deals) > 0 else 0,
            'median_days_on_market': int(non_sba_deals['days_on_market'].median()) if len(non_sba_deals) > 0 and non_sba_deals['days_on_market'].notna().any() else None,
            'mean_days_on_market': float(non_sba_deals['days_on_market'].mean()) if len(non_sba_deals) > 0 and non_sba_deals['days_on_market'].notna().any() else None,
            'median_days_under_loi': int(non_sba_deals['days_under_loi'].median()) if len(non_sba_deals) > 0 and non_sba_deals['days_under_loi'].notna().any() else None,
            'median_days_to_loi': int(non_sba_deals['days_to_loi'].median()) if len(non_sba_deals) > 0 and non_sba_deals['days_to_loi'].notna().any() else None,
            'median_commission': float(non_sba_deals['closed_commission'].median()) if len(non_sba_deals) > 0 else None,
            'total_commission': float(non_sba_deals['closed_commission'].sum()) if len(non_sba_deals) > 0 else 0
        }
    }
    
    # Create JavaScript file
    js_content = f"""// Enhanced SBA Verification Data with Inquiries
// Generated: {datetime.now().isoformat()}

const sbaVerificationData = {json.dumps(verification_data, indent=2)};

const sbaVerificationStats = {json.dumps(stats, indent=2)};

// Export for use in dashboard
if (typeof module !== 'undefined' && module.exports) {{
    module.exports = {{ sbaVerificationData, sbaVerificationStats }};
}}
"""
    
    with open('sba_verification_enhanced.js', 'w') as f:
        f.write(js_content)
    
    print(f"Generated enhanced verification data for {len(verification_data)} sold deals")
    print(f"\nKEY INSIGHTS:")
    print(f"  SBA Financing ({stats['sba']['count']} deals):")
    print(f"    - Median inquiries: {stats['sba']['median_inquiries']}")
    print(f"    - Median days on market: {stats['sba']['median_days_on_market']}")
    print(f"  Non-SBA Financing ({stats['non_sba']['count']} deals):")
    print(f"    - Median inquiries: {stats['non_sba']['median_inquiries']}")
    print(f"    - Median days on market: {stats['non_sba']['median_days_on_market']}")
    
    # Copy to main directory
    import shutil
    shutil.copy('sba_verification_enhanced.js', '../../sba_verification_enhanced.js')
    shutil.copy('inquiry_stats.js', '../../inquiry_stats.js')
    
    return verification_data, stats

if __name__ == "__main__":
    data, stats = generate_enhanced_verification()
    print(f"\n✅ Enhanced verification data generated: sba_verification_enhanced.js")