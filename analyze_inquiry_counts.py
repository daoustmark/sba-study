#!/usr/bin/env python3
"""
Analyze inquiry counts by SBA status and outcomes.
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime

def analyze_inquiry_counts():
    """Analyze inquiry counts across different SBA statuses and outcomes."""
    
    # Load the launch date analysis which has inquiry counts
    df = pd.read_csv('launch_date_analysis_v2.csv')
    
    print("\n" + "="*80)
    print("INQUIRY COUNT ANALYSIS BY SBA STATUS")
    print("="*80)
    
    # 1. Overall inquiry statistics by SBA status
    print("\n1. OVERALL INQUIRY STATISTICS BY SBA STATUS")
    print("-"*50)
    
    for sba_status in ['yes', 'no', 'unknown']:
        status_df = df[df['sba_status'] == sba_status]
        if len(status_df) > 0:
            print(f"\nSBA Status: {sba_status.upper()}")
            print(f"  Total listings: {len(status_df)}")
            print(f"  Median inquiries: {status_df['total_inquiries'].median():.0f}")
            print(f"  Mean inquiries: {status_df['total_inquiries'].mean():.1f}")
            print(f"  Min inquiries: {status_df['total_inquiries'].min()}")
            print(f"  Max inquiries: {status_df['total_inquiries'].max()}")
    
    # 2. Inquiry statistics for SOLD deals
    print("\n2. INQUIRY STATISTICS FOR SOLD DEALS")
    print("-"*50)
    
    sold_df = df[df['status'] == 'sold']
    
    for sba_status in ['yes', 'no', 'unknown']:
        status_df = sold_df[sold_df['sba_status'] == sba_status]
        if len(status_df) > 0:
            print(f"\nSBA Status: {sba_status.upper()} (SOLD)")
            print(f"  Count: {len(status_df)}")
            print(f"  Median inquiries: {status_df['total_inquiries'].median():.0f}")
            print(f"  Mean inquiries: {status_df['total_inquiries'].mean():.1f}")
            print(f"  25th percentile: {status_df['total_inquiries'].quantile(0.25):.0f}")
            print(f"  75th percentile: {status_df['total_inquiries'].quantile(0.75):.0f}")
    
    # 3. Inquiry statistics for LOST deals
    print("\n3. INQUIRY STATISTICS FOR LOST DEALS")
    print("-"*50)
    
    lost_df = df[df['status'] == 'lost']
    
    for sba_status in ['yes', 'no', 'unknown']:
        status_df = lost_df[lost_df['sba_status'] == sba_status]
        if len(status_df) > 0:
            print(f"\nSBA Status: {sba_status.upper()} (LOST)")
            print(f"  Count: {len(status_df)}")
            print(f"  Median inquiries: {status_df['total_inquiries'].median():.0f}")
            print(f"  Mean inquiries: {status_df['total_inquiries'].mean():.1f}")
    
    # 4. Success rate by inquiry volume
    print("\n4. SUCCESS RATE BY INQUIRY VOLUME QUARTILES")
    print("-"*50)
    
    # Calculate quartiles for all deals
    df['inquiry_quartile'] = pd.qcut(df['total_inquiries'], q=4, labels=['Q1 (Low)', 'Q2', 'Q3', 'Q4 (High)'])
    
    for sba_status in ['yes', 'no', 'unknown']:
        status_df = df[df['sba_status'] == sba_status]
        if len(status_df) > 0:
            print(f"\nSBA Status: {sba_status.upper()}")
            for quartile in ['Q1 (Low)', 'Q2', 'Q3', 'Q4 (High)']:
                q_df = status_df[status_df['inquiry_quartile'] == quartile]
                if len(q_df) > 0:
                    success_rate = (q_df['status'] == 'sold').sum() / len(q_df) * 100
                    median_inq = q_df['total_inquiries'].median()
                    print(f"  {quartile}: {success_rate:.1f}% success (median {median_inq:.0f} inquiries)")
    
    # 5. Correlation analysis
    print("\n5. CORRELATION ANALYSIS")
    print("-"*50)
    
    # For sold deals, check correlation between inquiries and days on market
    sold_with_days = sold_df[sold_df['days_on_market'].notna()]
    
    for sba_status in ['yes', 'no', 'unknown']:
        status_df = sold_with_days[sold_with_days['sba_status'] == sba_status]
        if len(status_df) > 5:  # Need enough data for correlation
            corr = status_df['total_inquiries'].corr(status_df['days_on_market'])
            print(f"\nSBA {sba_status.upper()}: Correlation between inquiries and days on market: {corr:.3f}")
            
            # Also check with commission
            comm_df = status_df[status_df['closed_commission'].notna() & (status_df['closed_commission'] > 0)]
            if len(comm_df) > 5:
                corr_comm = comm_df['total_inquiries'].corr(comm_df['closed_commission'])
                print(f"  Correlation between inquiries and commission: {corr_comm:.3f}")
    
    # 6. Generate enhanced verification data with inquiry counts
    print("\n6. GENERATING ENHANCED VERIFICATION DATA")
    print("-"*50)
    
    # Load SBA actual usage data
    sba_usage_df = pd.read_csv('sba_actual_usage_analysis.csv')
    
    # Merge with launch date data to get inquiry counts
    merged_df = pd.merge(
        sba_usage_df,
        df[['id', 'total_inquiries', 'days_on_market', 'days_under_loi', 'days_to_loi']],
        on='id',
        how='left'
    )
    
    # Filter to sold deals only
    sold_merged = merged_df[merged_df['status'] == 'sold'].copy()
    
    # Calculate statistics by actual financing type
    sba_financed = sold_merged[sold_merged['winning_loi_sba'] == True]
    non_sba_financed = sold_merged[sold_merged['winning_loi_sba'] == False]
    
    print(f"\nDEALS USING SBA FINANCING (n={len(sba_financed)}):")
    print(f"  Median inquiries: {sba_financed['total_inquiries'].median():.0f}")
    print(f"  Mean inquiries: {sba_financed['total_inquiries'].mean():.1f}")
    print(f"  Median days on market: {sba_financed['days_on_market'].median():.0f}")
    
    print(f"\nDEALS USING NON-SBA FINANCING (n={len(non_sba_financed)}):")
    print(f"  Median inquiries: {non_sba_financed['total_inquiries'].median():.0f}")
    print(f"  Mean inquiries: {non_sba_financed['total_inquiries'].mean():.1f}")
    print(f"  Median days on market: {non_sba_financed['days_on_market'].median():.0f}")
    
    # Save enhanced data
    enhanced_df = merged_df.copy()
    enhanced_df.to_csv('sba_analysis_with_inquiries.csv', index=False)
    
    # Generate JavaScript data with inquiry information
    js_data = {
        'inquiry_stats': {
            'sba_sold': {
                'median': int(sold_df[sold_df['sba_status'] == 'yes']['total_inquiries'].median()) if len(sold_df[sold_df['sba_status'] == 'yes']) > 0 else 0,
                'mean': float(sold_df[sold_df['sba_status'] == 'yes']['total_inquiries'].mean()) if len(sold_df[sold_df['sba_status'] == 'yes']) > 0 else 0,
                'count': len(sold_df[sold_df['sba_status'] == 'yes'])
            },
            'non_sba_sold': {
                'median': int(sold_df[sold_df['sba_status'] == 'no']['total_inquiries'].median()) if len(sold_df[sold_df['sba_status'] == 'no']) > 0 else 0,
                'mean': float(sold_df[sold_df['sba_status'] == 'no']['total_inquiries'].mean()) if len(sold_df[sold_df['sba_status'] == 'no']) > 0 else 0,
                'count': len(sold_df[sold_df['sba_status'] == 'no'])
            },
            'unknown_sold': {
                'median': int(sold_df[sold_df['sba_status'] == 'unknown']['total_inquiries'].median()) if len(sold_df[sold_df['sba_status'] == 'unknown']) > 0 else 0,
                'mean': float(sold_df[sold_df['sba_status'] == 'unknown']['total_inquiries'].mean()) if len(sold_df[sold_df['sba_status'] == 'unknown']) > 0 else 0,
                'count': len(sold_df[sold_df['sba_status'] == 'unknown'])
            },
            'sba_financed': {
                'median': int(sba_financed['total_inquiries'].median()) if len(sba_financed) > 0 else 0,
                'mean': float(sba_financed['total_inquiries'].mean()) if len(sba_financed) > 0 else 0,
                'count': len(sba_financed)
            },
            'non_sba_financed': {
                'median': int(non_sba_financed['total_inquiries'].median()) if len(non_sba_financed) > 0 else 0,
                'mean': float(non_sba_financed['total_inquiries'].mean()) if len(non_sba_financed) > 0 else 0,
                'count': len(non_sba_financed)
            }
        }
    }
    
    # Write JavaScript file
    js_content = f"""// Inquiry statistics for SBA dashboard
// Generated: {datetime.now().isoformat()}

const inquiryStats = {json.dumps(js_data['inquiry_stats'], indent=2)};
"""
    
    with open('inquiry_stats.js', 'w') as f:
        f.write(js_content)
    
    print(f"\n✅ Enhanced data saved to sba_analysis_with_inquiries.csv")
    print(f"✅ JavaScript data saved to inquiry_stats.js")
    
    return enhanced_df

if __name__ == "__main__":
    analyze_inquiry_counts()