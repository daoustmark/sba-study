#!/usr/bin/env python3
"""
SBA analysis using ONLY listings with processed CIMs.
Includes launch date calculation based on inquiry surge.
"""

import pymysql
import pandas as pd
import json
from datetime import datetime, timedelta
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
    """Load the CIM analysis results."""
    results_files = list(Path('.').glob('cim_analysis_results_*.json'))
    if not results_files:
        print("No CIM analysis results found!")
        return {}
    
    latest_file = sorted(results_files)[-1]
    print(f"Loading CIM results from: {latest_file}")
    
    with open(latest_file, 'r') as f:
        cim_data = json.load(f)
    
    # Create a dict mapping listing_id to full CIM data
    cim_map = {}
    for item in cim_data:
        if 'listing_id' in item:
            cim_map[item['listing_id']] = item
    
    return cim_map

def calculate_launch_date(conn, listing_id):
    """Calculate launch date based on inquiry surge."""
    cursor = conn.cursor()
    
    # Get inquiry data for the listing
    query = """
    SELECT 
        DATE(created_at) as inquiry_date,
        COUNT(*) as daily_inquiries
    FROM inquiries
    WHERE listing_id = %s
    GROUP BY DATE(created_at)
    ORDER BY inquiry_date
    """
    
    cursor.execute(query, (listing_id,))
    inquiries = cursor.fetchall()
    cursor.close()
    
    if not inquiries or len(inquiries) < 2:
        return None
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(inquiries)
    df['inquiry_date'] = pd.to_datetime(df['inquiry_date'])
    df = df.set_index('inquiry_date')
    
    # Find the first significant surge (20+ inquiries in 2 days)
    for i in range(len(df) - 1):
        current_date = df.index[i]
        # Look at 2-day window
        two_day_total = df.iloc[i:min(i+2, len(df))]['daily_inquiries'].sum()
        
        if two_day_total >= 20:
            # Found surge - this is likely the launch date
            return current_date.date()
    
    # If no surge found, use first inquiry date with 5+ inquiries
    for i in range(len(df)):
        if df.iloc[i]['daily_inquiries'] >= 5:
            return df.index[i].date()
    
    # Fallback to first inquiry date
    return df.index[0].date() if len(df) > 0 else None

def analyze_cim_only_listings():
    """Analyze only listings with processed CIMs."""
    
    # Load CIM results
    cim_map = load_cim_results()
    listing_ids = list(cim_map.keys())
    
    if not listing_ids:
        print("No CIM data available!")
        return
    
    print(f"\nAnalyzing {len(listing_ids)} listings with processed CIMs")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get listing data for CIM-processed listings only
    id_list = ','.join(map(str, listing_ids))
    
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
            ELSE 'active'
        END as status,
        (SELECT COUNT(*) FROM inquiries WHERE listing_id = l.id) as total_inquiries
    FROM listings l
    WHERE l.id IN ({id_list})
        AND l.closed_type IN (1, 2)
    """
    
    cursor.execute(query)
    listings = cursor.fetchall()
    
    print(f"Found {len(listings)} closed listings with CIMs")
    
    # Process each listing
    results = []
    for listing in listings:
        listing_id = listing['id']
        
        # Add CIM data
        cim_data = cim_map[listing_id]
        listing['sba_status'] = cim_data.get('sba_eligible', 'unknown')
        listing['sba_evidence'] = cim_data.get('sba_evidence', '')[:200]
        listing['cim_asking_price'] = cim_data.get('asking_price', 0)
        listing['cim_sde'] = cim_data.get('sde', 0)
        
        # Calculate launch date
        launch_date = calculate_launch_date(conn, listing_id)
        listing['launch_date'] = launch_date
        
        # Calculate days on market (launch to close)
        if launch_date and listing['closed_at']:
            closed_date = listing['closed_at'].date() if hasattr(listing['closed_at'], 'date') else listing['closed_at']
            days_on_market = (closed_date - launch_date).days
            listing['days_on_market'] = days_on_market if days_on_market > 0 else None
        else:
            listing['days_on_market'] = None
        
        results.append(listing)
    
    cursor.close()
    conn.close()
    
    return results

def generate_analysis_report(listings):
    """Generate comprehensive analysis report."""
    
    df = pd.DataFrame(listings)
    
    print("\n" + "=" * 80)
    print("CIM-ONLY SBA ANALYSIS REPORT")
    print("=" * 80)
    print(f"Total Listings with CIMs: {len(df)}")
    
    # 1. SBA Status Breakdown
    print("\n1. SBA STATUS BREAKDOWN (CIM-Verified)")
    print("-" * 40)
    
    status_groups = df.groupby('sba_status')
    for status, group in status_groups:
        sold = len(group[group['status'] == 'sold'])
        total = len(group)
        success_rate = (sold / total * 100) if total > 0 else 0
        
        print(f"\n{status.upper()}:")
        print(f"  Total: {total}")
        print(f"  Sold: {sold}")
        print(f"  Lost: {total - sold}")
        print(f"  Success Rate: {success_rate:.1f}%")
    
    # 2. Days on Market Analysis
    print("\n2. DAYS ON MARKET (Launch to Close)")
    print("-" * 40)
    
    # Filter for sold listings with launch dates
    sold_with_launch = df[(df['status'] == 'sold') & (df['days_on_market'].notna())]
    
    if len(sold_with_launch) > 0:
        for status in sold_with_launch['sba_status'].unique():
            subset = sold_with_launch[sold_with_launch['sba_status'] == status]
            if len(subset) > 0:
                median_days = subset['days_on_market'].median()
                mean_days = subset['days_on_market'].mean()
                print(f"\n{status.upper()}:")
                print(f"  Median: {median_days:.0f} days")
                print(f"  Mean: {mean_days:.0f} days")
                print(f"  Sample Size: {len(subset)}")
    
    # 3. Financial Analysis
    print("\n3. FINANCIAL IMPACT")
    print("-" * 40)
    
    for status in df['sba_status'].unique():
        subset = df[df['sba_status'] == status]
        sold_subset = subset[subset['status'] == 'sold']
        
        if len(sold_subset) > 0:
            avg_commission = sold_subset['closed_commission'].mean()
            total_commission = sold_subset['closed_commission'].sum()
            avg_asking = sold_subset['asking_at_close'].mean()
            
            print(f"\n{status.upper()}:")
            print(f"  Avg Commission: ${avg_commission:,.0f}")
            print(f"  Total Commission: ${total_commission:,.0f}")
            print(f"  Avg Asking Price: ${avg_asking:,.0f}")
    
    # 4. Launch Date Coverage
    print("\n4. DATA QUALITY")
    print("-" * 40)
    
    with_launch = len(df[df['launch_date'].notna()])
    print(f"Listings with calculable launch date: {with_launch}/{len(df)} ({with_launch/len(df)*100:.1f}%)")
    
    with_dom = len(df[df['days_on_market'].notna()])
    print(f"Listings with days on market: {with_dom}/{len(df)} ({with_dom/len(df)*100:.1f}%)")
    
    # 5. Statistical Comparison
    print("\n5. STATISTICAL COMPARISON")
    print("-" * 40)
    
    # Compare SBA eligible vs not eligible
    sba_yes = df[df['sba_status'] == 'yes']
    sba_no = df[df['sba_status'] == 'no']
    
    if len(sba_yes) > 0 and len(sba_no) > 0:
        sba_yes_success = len(sba_yes[sba_yes['status'] == 'sold']) / len(sba_yes) * 100
        sba_no_success = len(sba_no[sba_no['status'] == 'sold']) / len(sba_no) * 100
        
        improvement = ((sba_yes_success / sba_no_success) - 1) * 100 if sba_no_success > 0 else 0
        
        print(f"\nSBA Eligible Success Rate: {sba_yes_success:.1f}%")
        print(f"Not Eligible Success Rate: {sba_no_success:.1f}%")
        print(f"Improvement Factor: {improvement:+.0f}%")
        
        # Days on market comparison
        sba_yes_dom = sba_yes[sba_yes['days_on_market'].notna()]['days_on_market'].median()
        sba_no_dom = sba_no[sba_no['days_on_market'].notna()]['days_on_market'].median()
        
        if not pd.isna(sba_yes_dom) and not pd.isna(sba_no_dom):
            print(f"\nMedian Days on Market:")
            print(f"  SBA Eligible: {sba_yes_dom:.0f} days")
            print(f"  Not Eligible: {sba_no_dom:.0f} days")
            print(f"  Difference: {sba_yes_dom - sba_no_dom:+.0f} days")
    
    # Save results
    df.to_csv('cim_only_analysis.csv', index=False)
    
    # Create summary JSON
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_listings': len(df),
        'sba_breakdown': {},
        'days_on_market': {},
        'financial_metrics': {},
        'data_quality': {
            'with_launch_date': with_launch,
            'with_days_on_market': with_dom
        }
    }
    
    for status in df['sba_status'].unique():
        subset = df[df['sba_status'] == status]
        sold = len(subset[subset['status'] == 'sold'])
        total = len(subset)
        
        summary['sba_breakdown'][status] = {
            'total': int(total),
            'sold': int(sold),
            'lost': int(total - sold),
            'success_rate': round(sold / total * 100, 1) if total > 0 else 0
        }
        
        # Days on market
        dom_subset = subset[(subset['status'] == 'sold') & (subset['days_on_market'].notna())]
        if len(dom_subset) > 0:
            summary['days_on_market'][status] = {
                'median': float(dom_subset['days_on_market'].median()),
                'mean': float(dom_subset['days_on_market'].mean()),
                'count': len(dom_subset)
            }
    
    with open('cim_only_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print("\n📁 Detailed results saved to cim_only_analysis.csv")
    print("📁 Summary saved to cim_only_summary.json")
    
    return summary

if __name__ == "__main__":
    # Analyze listings with CIMs only
    listings = analyze_cim_only_listings()
    
    # Generate report
    if listings:
        summary = generate_analysis_report(listings)
        print("\n✅ CIM-only analysis complete!")
    else:
        print("No data to analyze!")