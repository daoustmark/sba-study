#!/usr/bin/env python3
"""
Full SBA analysis including ALL 251 CIM-processed listings.
Shows active, sold, and lost listings.
"""

import pymysql
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

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
    """Load the CIM analysis results."""
    results_files = list(Path('.').glob('cim_analysis_results_*.json'))
    if not results_files:
        return {}
    
    latest_file = sorted(results_files)[-1]
    print(f"Loading CIM results from: {latest_file}")
    
    with open(latest_file, 'r') as f:
        cim_data = json.load(f)
    
    cim_map = {}
    for item in cim_data:
        if 'listing_id' in item:
            cim_map[item['listing_id']] = item
    
    return cim_map

def analyze_all_cim_listings():
    """Analyze ALL listings with processed CIMs, including active ones."""
    
    cim_map = load_cim_results()
    listing_ids = list(cim_map.keys())
    
    if not listing_ids:
        print("No CIM data available!")
        return
    
    print(f"\nAnalyzing ALL {len(listing_ids)} listings with processed CIMs")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    id_list = ','.join(map(str, listing_ids))
    
    # Get ALL listings (including active)
    query = f"""
    SELECT 
        l.id,
        l.name,
        l.closed_type,
        l.closed_at,
        l.created_at,
        l.asking_at_close,
        l.sde_at_close,
        l.closed_commission,
        CASE
            WHEN l.closed_type = 1 THEN 'sold'
            WHEN l.closed_type = 2 THEN 'lost'
            WHEN l.closed_type = 0 THEN 'active'
            ELSE 'unknown'
        END as status,
        DATEDIFF(NOW(), l.created_at) as days_since_creation,
        (SELECT COUNT(*) FROM inquiries WHERE listing_id = l.id) as total_inquiries
    FROM listings l
    WHERE l.id IN ({id_list})
    """
    
    cursor.execute(query)
    listings = cursor.fetchall()
    
    print(f"Found {len(listings)} total listings with CIMs")
    
    # Process each listing
    results = []
    for listing in listings:
        listing_id = listing['id']
        
        # Add CIM data
        cim_data = cim_map[listing_id]
        listing['sba_status'] = cim_data.get('sba_eligible', 'unknown')
        listing['sba_evidence'] = cim_data.get('sba_evidence', '')[:100]
        
        # Use CIM values or database values
        listing['display_asking'] = cim_data.get('asking_price', 0) or listing.get('asking_at_close', 0)
        listing['display_sde'] = cim_data.get('sde', 0) or listing.get('sde_at_close', 0)
        
        results.append(listing)
    
    cursor.close()
    conn.close()
    
    return results

def generate_full_report(listings):
    """Generate comprehensive report including active listings."""
    
    df = pd.DataFrame(listings)
    
    print("\n" + "=" * 80)
    print("COMPLETE CIM ANALYSIS - ALL 251 LISTINGS")
    print("=" * 80)
    
    # 1. Overall Status Breakdown
    print("\n1. LISTING STATUS OVERVIEW")
    print("-" * 40)
    
    status_counts = df['status'].value_counts()
    for status, count in status_counts.items():
        pct = count / len(df) * 100
        print(f"{status.upper()}: {count} ({pct:.1f}%)")
    
    # 2. SBA Status by Listing Status
    print("\n2. SBA STATUS BREAKDOWN")
    print("-" * 40)
    
    # Create crosstab
    crosstab = pd.crosstab(df['sba_status'], df['status'], margins=True)
    print(crosstab)
    
    # 3. Success Rates (Closed Deals Only)
    print("\n3. SUCCESS RATES (CLOSED DEALS ONLY)")
    print("-" * 40)
    
    closed_df = df[df['status'].isin(['sold', 'lost'])]
    
    for sba_status in closed_df['sba_status'].unique():
        subset = closed_df[closed_df['sba_status'] == sba_status]
        sold = len(subset[subset['status'] == 'sold'])
        total = len(subset)
        success_rate = (sold / total * 100) if total > 0 else 0
        
        print(f"\n{sba_status.upper()}:")
        print(f"  Closed Deals: {total}")
        print(f"  Sold: {sold}")
        print(f"  Lost: {total - sold}")
        print(f"  Success Rate: {success_rate:.1f}%")
    
    # 4. Active Listings Analysis
    print("\n4. ACTIVE LISTINGS (STILL ON MARKET)")
    print("-" * 40)
    
    active_df = df[df['status'] == 'active']
    
    if len(active_df) > 0:
        sba_active = active_df.groupby('sba_status').size()
        print("\nSBA Status of Active Listings:")
        for status, count in sba_active.items():
            print(f"  {status}: {count}")
        
        # Average time on market for active listings
        avg_days = active_df['days_since_creation'].mean()
        print(f"\nAverage days since creation: {avg_days:.0f}")
        
        # Inquiry analysis
        avg_inquiries = active_df['total_inquiries'].mean()
        print(f"Average inquiries per active listing: {avg_inquiries:.1f}")
    
    # 5. Financial Summary by SBA Status
    print("\n5. FINANCIAL METRICS")
    print("-" * 40)
    
    for status in ['sold', 'active', 'lost']:
        subset = df[df['status'] == status]
        if len(subset) > 0:
            print(f"\n{status.upper()} LISTINGS:")
            for sba_status in subset['sba_status'].unique():
                sba_subset = subset[subset['sba_status'] == sba_status]
                if len(sba_subset) > 0:
                    if status == 'sold':
                        avg_commission = sba_subset['closed_commission'].mean()
                        print(f"  {sba_status}: ${avg_commission:,.0f} avg commission ({len(sba_subset)} listings)")
                    else:
                        avg_asking = sba_subset['display_asking'].mean()
                        if avg_asking > 0:
                            print(f"  {sba_status}: ${avg_asking:,.0f} avg asking ({len(sba_subset)} listings)")
    
    # 6. Key Insights
    print("\n6. KEY INSIGHTS")
    print("-" * 40)
    
    # Active vs Closed ratio
    active_count = len(df[df['status'] == 'active'])
    closed_count = len(df[df['status'].isin(['sold', 'lost'])])
    print(f"• {active_count} listings still active ({active_count/len(df)*100:.1f}%)")
    print(f"• {closed_count} listings closed ({closed_count/len(df)*100:.1f}%)")
    
    # SBA distribution in active listings
    active_sba = len(active_df[active_df['sba_status'] == 'yes']) if len(active_df) > 0 else 0
    if active_sba > 0:
        print(f"• {active_sba} SBA-eligible listings currently active")
    
    # Save detailed results
    df.to_csv('full_cim_analysis.csv', index=False)
    
    print("\n📁 Full results saved to full_cim_analysis.csv")
    
    return df

if __name__ == "__main__":
    # Analyze ALL listings with CIMs
    listings = analyze_all_cim_listings()
    
    if listings:
        df = generate_full_report(listings)
        print("\n✅ Complete CIM analysis done!")
    else:
        print("No data to analyze!")