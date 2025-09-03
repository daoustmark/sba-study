#!/usr/bin/env python3
"""
Analyze SBA-prequalified deals to see what percentage actually used SBA financing
and how that affected outcomes.
"""

import pymysql
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import numpy as np

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

def load_cim_results():
    """Load the CIM analysis results to identify SBA-prequalified listings."""
    results_files = list(Path('.').glob('cim_analysis_results_*.json'))
    if not results_files:
        return {}
    
    latest_file = sorted(results_files)[-1]
    print(f"Loading CIM results from: {latest_file}")
    
    with open(latest_file, 'r') as f:
        cim_data = json.load(f)
    
    # Get only SBA-prequalified listings
    sba_prequalified = {}
    for item in cim_data:
        if 'listing_id' in item and item.get('sba_eligible') == 'yes':
            sba_prequalified[item['listing_id']] = item
    
    return sba_prequalified

def analyze_sba_actual_usage():
    """Analyze which SBA-prequalified deals actually used SBA financing."""
    
    # Load SBA-prequalified listings
    sba_prequalified = load_cim_results()
    
    if not sba_prequalified:
        print("No SBA-prequalified listings found!")
        return
    
    print(f"\nAnalyzing {len(sba_prequalified)} SBA-prequalified listings")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get listing data for SBA-prequalified deals
    listing_ids = list(sba_prequalified.keys())
    id_list = ','.join(map(str, listing_ids))
    
    # First, get listing details
    query = f"""
    SELECT 
        l.id,
        l.name,
        l.closed_type,
        l.closed_at,
        l.closed_commission,
        l.created_at,
        CASE
            WHEN l.closed_type = 1 THEN 'sold'
            WHEN l.closed_type = 2 THEN 'lost'
            WHEN l.closed_type = 0 THEN 'active'
            ELSE 'unknown'
        END as status
    FROM listings l
    WHERE l.id IN ({id_list})
    """
    
    cursor.execute(query)
    listings = cursor.fetchall()
    
    # Now get LOI data for each listing
    results = []
    
    for listing in listings:
        listing_id = listing['id']
        
        # Get all LOIs for this listing
        loi_query = """
        SELECT 
            id as loi_id,
            signed_date,
            has_sba,
            cash_at_close,
            has_seller_financing,
            seller_financing_value,
            created_at
        FROM lois
        WHERE listing_id = %s
        ORDER BY signed_date DESC
        """
        
        cursor.execute(loi_query, (listing_id,))
        lois = cursor.fetchall()
        
        # Analyze LOIs
        total_lois = len(lois)
        sba_lois = sum(1 for loi in lois if loi['has_sba'] == 1)
        has_sba_loi = sba_lois > 0
        
        # Get the winning LOI (last signed LOI for sold deals)
        winning_loi_sba = False
        if listing['status'] == 'sold' and lois:
            # For sold deals, check if the last LOI had SBA
            winning_loi = lois[0]  # Most recent LOI
            winning_loi_sba = winning_loi['has_sba'] == 1
        
        listing_result = {
            'id': listing_id,
            'name': listing['name'],
            'status': listing['status'],
            'closed_at': listing['closed_at'],
            'closed_commission': listing['closed_commission'],
            'total_lois': total_lois,
            'sba_lois': sba_lois,
            'has_sba_loi': has_sba_loi,
            'winning_loi_sba': winning_loi_sba,
            'pct_sba_lois': (sba_lois / total_lois * 100) if total_lois > 0 else 0
        }
        
        results.append(listing_result)
    
    cursor.close()
    conn.close()
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(results)
    
    # Generate report
    print("\n" + "=" * 80)
    print("SBA PREQUALIFIED DEALS - ACTUAL SBA USAGE ANALYSIS")
    print("=" * 80)
    
    # 1. Overall SBA LOI Usage
    print("\n1. SBA LOI USAGE IN PREQUALIFIED DEALS")
    print("-" * 40)
    
    total_prequalified = len(df)
    had_lois = df[df['total_lois'] > 0]
    had_sba_lois = df[df['has_sba_loi'] == True]
    
    print(f"Total SBA-prequalified listings: {total_prequalified}")
    print(f"Had at least one LOI: {len(had_lois)} ({len(had_lois)/total_prequalified*100:.1f}%)")
    print(f"Had at least one SBA LOI: {len(had_sba_lois)} ({len(had_sba_lois)/total_prequalified*100:.1f}%)")
    
    # 2. Sold Deals Analysis
    print("\n2. SOLD DEALS - SBA FINANCING USAGE")
    print("-" * 40)
    
    sold_df = df[df['status'] == 'sold']
    sold_with_sba = sold_df[sold_df['winning_loi_sba'] == True]
    sold_without_sba = sold_df[sold_df['winning_loi_sba'] == False]
    
    print(f"\nSBA-prequalified deals that SOLD: {len(sold_df)}")
    print(f"  Used SBA financing: {len(sold_with_sba)} ({len(sold_with_sba)/len(sold_df)*100:.1f}%)")
    print(f"  Used other financing: {len(sold_without_sba)} ({len(sold_without_sba)/len(sold_df)*100:.1f}%)")
    
    # 3. Success Rates Comparison
    print("\n3. SUCCESS RATES BY ACTUAL FINANCING")
    print("-" * 40)
    
    # For deals that had LOIs
    deals_with_lois = df[df['total_lois'] > 0]
    
    # Split by whether they had SBA LOIs
    with_sba_lois = deals_with_lois[deals_with_lois['has_sba_loi'] == True]
    without_sba_lois = deals_with_lois[deals_with_lois['has_sba_loi'] == False]
    
    if len(with_sba_lois) > 0:
        sba_loi_success = (with_sba_lois['status'] == 'sold').sum() / len(with_sba_lois) * 100
        print(f"\nDeals with SBA LOIs: {len(with_sba_lois)}")
        print(f"  Success rate: {sba_loi_success:.1f}%")
    
    if len(without_sba_lois) > 0:
        no_sba_loi_success = (without_sba_lois['status'] == 'sold').sum() / len(without_sba_lois) * 100
        print(f"\nDeals without SBA LOIs: {len(without_sba_lois)}")
        print(f"  Success rate: {no_sba_loi_success:.1f}%")
    
    # 4. Commission Analysis
    print("\n4. COMMISSION ANALYSIS")
    print("-" * 40)
    
    if len(sold_with_sba) > 0:
        avg_comm_sba = sold_with_sba['closed_commission'].mean()
        median_comm_sba = sold_with_sba['closed_commission'].median()
        print(f"\nSold with SBA financing:")
        print(f"  Average commission: ${avg_comm_sba:,.0f}")
        print(f"  Median commission: ${median_comm_sba:,.0f}")
    
    if len(sold_without_sba) > 0:
        avg_comm_no_sba = sold_without_sba['closed_commission'].mean()
        median_comm_no_sba = sold_without_sba['closed_commission'].median()
        print(f"\nSold without SBA financing:")
        print(f"  Average commission: ${avg_comm_no_sba:,.0f}")
        print(f"  Median commission: ${median_comm_no_sba:,.0f}")
    
    # 5. Time Analysis (need to load from our previous analysis)
    print("\n5. TIME TO CLOSE ANALYSIS")
    print("-" * 40)
    
    # Load the launch date analysis to get time metrics
    try:
        launch_df = pd.read_csv('launch_date_analysis_v2.csv')
        
        # Merge with our SBA usage data
        merged = pd.merge(df[df['status'] == 'sold'], 
                         launch_df[['id', 'days_on_market', 'days_under_loi', 'days_to_loi']], 
                         on='id', 
                         how='left')
        
        # Split by actual SBA usage
        with_sba_time = merged[merged['winning_loi_sba'] == True]
        without_sba_time = merged[merged['winning_loi_sba'] == False]
        
        if len(with_sba_time) > 0 and with_sba_time['days_on_market'].notna().any():
            print(f"\nSold with SBA financing (n={len(with_sba_time)}):")
            print(f"  Median days on market: {with_sba_time['days_on_market'].median():.0f}")
            print(f"  Mean days on market: {with_sba_time['days_on_market'].mean():.0f}")
            
            if with_sba_time['days_under_loi'].notna().any():
                print(f"  Median days under LOI: {with_sba_time['days_under_loi'].median():.0f}")
        
        if len(without_sba_time) > 0 and without_sba_time['days_on_market'].notna().any():
            print(f"\nSold without SBA financing (n={len(without_sba_time)}):")
            print(f"  Median days on market: {without_sba_time['days_on_market'].median():.0f}")
            print(f"  Mean days on market: {without_sba_time['days_on_market'].mean():.0f}")
            
            if without_sba_time['days_under_loi'].notna().any():
                print(f"  Median days under LOI: {without_sba_time['days_under_loi'].median():.0f}")
    
    except FileNotFoundError:
        print("\nNote: Could not load time analysis data")
    
    # 6. Key Insights
    print("\n6. KEY INSIGHTS")
    print("-" * 40)
    
    print(f"\n• Of {total_prequalified} SBA-prequalified listings:")
    print(f"  - {len(had_sba_lois)} ({len(had_sba_lois)/total_prequalified*100:.0f}%) received at least one SBA LOI")
    
    if len(sold_df) > 0:
        print(f"\n• Of {len(sold_df)} SBA-prequalified deals that sold:")
        print(f"  - {len(sold_with_sba)} ({len(sold_with_sba)/len(sold_df)*100:.0f}%) actually used SBA financing")
        print(f"  - {len(sold_without_sba)} ({len(sold_without_sba)/len(sold_df)*100:.0f}%) used alternative financing")
    
    # Save results
    df.to_csv('sba_actual_usage_analysis.csv', index=False)
    print("\n📁 Detailed results saved to sba_actual_usage_analysis.csv")
    
    # Create summary JSON
    summary = {
        'timestamp': datetime.now().isoformat(),
        'sba_prequalified_total': total_prequalified,
        'had_sba_lois': len(had_sba_lois),
        'pct_with_sba_lois': len(had_sba_lois)/total_prequalified*100 if total_prequalified > 0 else 0,
        'sold_deals': {
            'total': len(sold_df),
            'used_sba': len(sold_with_sba),
            'used_other': len(sold_without_sba),
            'pct_used_sba': len(sold_with_sba)/len(sold_df)*100 if len(sold_df) > 0 else 0
        }
    }
    
    with open('sba_usage_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    return df

if __name__ == "__main__":
    df = analyze_sba_actual_usage()
    print("\n✅ SBA actual usage analysis complete!")