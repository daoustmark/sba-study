#!/usr/bin/env python3
"""
Calculate launch dates based on inquiry surge and analyze true days on market.
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

def calculate_launch_date_detailed(conn, listing_id):
    """Calculate launch date with detailed analysis of inquiry patterns."""
    cursor = conn.cursor()
    
    # Get all inquiries for the listing
    query = """
    SELECT 
        DATE(created_at) as inquiry_date,
        COUNT(*) as daily_inquiries,
        MIN(created_at) as first_inquiry_time,
        MAX(created_at) as last_inquiry_time
    FROM inquiries
    WHERE listing_id = %s
    GROUP BY DATE(created_at)
    ORDER BY inquiry_date
    """
    
    cursor.execute(query, (listing_id,))
    inquiries = cursor.fetchall()
    cursor.close()
    
    if not inquiries:
        return None, "No inquiries", {}
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(inquiries)
    df['inquiry_date'] = pd.to_datetime(df['inquiry_date'])
    
    # Strategy 1: Find first surge of 20+ inquiries in 2 days
    for i in range(len(df)):
        # Look at 2-day window starting from this date
        two_day_window = df.iloc[i:min(i+2, len(df))]
        two_day_total = two_day_window['daily_inquiries'].sum()
        
        if two_day_total >= 20:
            launch_date = df.iloc[i]['inquiry_date'].date()
            return launch_date, "surge_20_in_2days", {
                'surge_start': str(launch_date),
                'surge_inquiries': int(two_day_total),
                'days_in_surge': len(two_day_window)
            }
    
    # Strategy 2: Find first day with 10+ inquiries
    for i in range(len(df)):
        if df.iloc[i]['daily_inquiries'] >= 10:
            launch_date = df.iloc[i]['inquiry_date'].date()
            return launch_date, "single_day_10plus", {
                'launch_date': str(launch_date),
                'first_day_inquiries': int(df.iloc[i]['daily_inquiries'])
            }
    
    # Strategy 3: Find first day with 5+ inquiries
    for i in range(len(df)):
        if df.iloc[i]['daily_inquiries'] >= 5:
            launch_date = df.iloc[i]['inquiry_date'].date()
            return launch_date, "single_day_5plus", {
                'launch_date': str(launch_date),
                'first_day_inquiries': int(df.iloc[i]['daily_inquiries'])
            }
    
    # Strategy 4: Use first inquiry date if all else fails
    launch_date = df.iloc[0]['inquiry_date'].date()
    return launch_date, "first_inquiry", {
        'launch_date': str(launch_date),
        'total_inquiries': int(df['daily_inquiries'].sum())
    }

def analyze_launch_dates_for_cim_listings():
    """Analyze launch dates and days on market for all CIM listings."""
    
    # Load CIM results
    cim_map = load_cim_results()
    listing_ids = list(cim_map.keys())
    
    if not listing_ids:
        print("No CIM data available!")
        return
    
    print(f"\nAnalyzing launch dates for {len(listing_ids)} listings with CIMs")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get listing data
    id_list = ','.join(map(str, listing_ids))
    
    query = f"""
    SELECT 
        l.id,
        l.name,
        l.closed_type,
        l.closed_at,
        l.created_at,
        CASE
            WHEN l.closed_type = 1 THEN 'sold'
            WHEN l.closed_type = 2 THEN 'lost'
            WHEN l.closed_type = 0 THEN 'active'
            ELSE 'unknown'
        END as status,
        (SELECT COUNT(*) FROM inquiries WHERE listing_id = l.id) as total_inquiries,
        (SELECT MIN(created_at) FROM inquiries WHERE listing_id = l.id) as first_inquiry,
        (SELECT MAX(created_at) FROM inquiries WHERE listing_id = l.id) as last_inquiry
    FROM listings l
    WHERE l.id IN ({id_list})
    """
    
    cursor.execute(query)
    listings = cursor.fetchall()
    
    print(f"Processing {len(listings)} listings...")
    
    results = []
    strategy_counts = {}
    
    for listing in listings:
        listing_id = listing['id']
        
        # Add CIM data
        cim_data = cim_map[listing_id]
        listing['sba_status'] = cim_data.get('sba_eligible', 'unknown')
        
        # Calculate launch date
        launch_date, strategy, details = calculate_launch_date_detailed(conn, listing_id)
        
        listing['launch_date'] = launch_date
        listing['launch_strategy'] = strategy
        listing['launch_details'] = details
        
        # Count strategies
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        # Calculate days on market
        if launch_date:
            if listing['status'] in ['sold', 'lost'] and listing['closed_at']:
                closed_date = listing['closed_at'].date() if hasattr(listing['closed_at'], 'date') else listing['closed_at']
                days_on_market = (closed_date - launch_date).days
                listing['days_on_market'] = days_on_market if days_on_market >= 0 else None
            elif listing['status'] == 'active':
                # For active listings, calculate days from launch to today
                days_active = (datetime.now().date() - launch_date).days
                listing['days_on_market'] = days_active if days_active >= 0 else None
            else:
                listing['days_on_market'] = None
        else:
            listing['days_on_market'] = None
        
        results.append(listing)
    
    cursor.close()
    conn.close()
    
    # Print strategy usage
    print("\nLaunch Date Detection Strategies Used:")
    print("-" * 40)
    for strategy, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {strategy}: {count} listings")
    
    return results

def generate_time_on_market_report(listings):
    """Generate comprehensive time on market analysis."""
    
    df = pd.DataFrame(listings)
    
    print("\n" + "=" * 80)
    print("TIME ON MARKET ANALYSIS - BASED ON INQUIRY SURGE")
    print("=" * 80)
    
    # 1. Data Quality
    print("\n1. DATA QUALITY")
    print("-" * 40)
    
    with_launch = df[df['launch_date'].notna()]
    without_launch = df[df['launch_date'].isna()]
    
    print(f"Listings with launch date: {len(with_launch)}/{len(df)} ({len(with_launch)/len(df)*100:.1f}%)")
    print(f"Listings without launch date: {len(without_launch)}")
    
    if len(without_launch) > 0:
        print("\nListings without launch dates (no inquiries):")
        for _, row in without_launch.head(5).iterrows():
            print(f"  ID {row['id']}: {row['name'][:50]}...")
    
    # 2. Days on Market by Status and SBA
    print("\n2. DAYS ON MARKET BY SBA STATUS (CLOSED DEALS ONLY)")
    print("-" * 40)
    
    closed_with_dom = df[(df['status'].isin(['sold', 'lost'])) & (df['days_on_market'].notna())]
    
    for status in ['sold', 'lost']:
        status_df = closed_with_dom[closed_with_dom['status'] == status]
        if len(status_df) > 0:
            print(f"\n{status.upper()} LISTINGS:")
            
            for sba_status in status_df['sba_status'].unique():
                subset = status_df[status_df['sba_status'] == sba_status]
                if len(subset) > 0:
                    median_days = subset['days_on_market'].median()
                    mean_days = subset['days_on_market'].mean()
                    min_days = subset['days_on_market'].min()
                    max_days = subset['days_on_market'].max()
                    
                    print(f"\n  {sba_status.upper()}:")
                    print(f"    Count: {len(subset)}")
                    print(f"    Median: {median_days:.0f} days")
                    print(f"    Mean: {mean_days:.0f} days")
                    print(f"    Range: {min_days:.0f} - {max_days:.0f} days")
    
    # 3. Active Listings Analysis
    print("\n3. ACTIVE LISTINGS - DAYS SINCE LAUNCH")
    print("-" * 40)
    
    active_with_dom = df[(df['status'] == 'active') & (df['days_on_market'].notna())]
    
    if len(active_with_dom) > 0:
        for sba_status in active_with_dom['sba_status'].unique():
            subset = active_with_dom[active_with_dom['sba_status'] == sba_status]
            if len(subset) > 0:
                median_days = subset['days_on_market'].median()
                mean_days = subset['days_on_market'].mean()
                
                print(f"\n  {sba_status.upper()}:")
                print(f"    Count: {len(subset)} active listings")
                print(f"    Median days since launch: {median_days:.0f}")
                print(f"    Mean days since launch: {mean_days:.0f}")
    
    # 4. Comparison: SBA vs Non-SBA (Sold Only)
    print("\n4. SBA IMPACT ON TIME TO CLOSE (SOLD ONLY)")
    print("-" * 40)
    
    sold_df = closed_with_dom[closed_with_dom['status'] == 'sold']
    
    sba_yes = sold_df[sold_df['sba_status'] == 'yes']
    sba_no = sold_df[sold_df['sba_status'] == 'no']
    
    if len(sba_yes) > 0 and len(sba_no) > 0:
        sba_median = sba_yes['days_on_market'].median()
        no_sba_median = sba_no['days_on_market'].median()
        
        sba_mean = sba_yes['days_on_market'].mean()
        no_sba_mean = sba_no['days_on_market'].mean()
        
        print(f"\nSBA ELIGIBLE (n={len(sba_yes)}):")
        print(f"  Median: {sba_median:.0f} days")
        print(f"  Mean: {sba_mean:.0f} days")
        
        print(f"\nNOT ELIGIBLE (n={len(sba_no)}):")
        print(f"  Median: {no_sba_median:.0f} days")
        print(f"  Mean: {no_sba_mean:.0f} days")
        
        print(f"\nDIFFERENCE:")
        print(f"  Median: {sba_median - no_sba_median:+.0f} days")
        print(f"  Mean: {sba_mean - no_sba_mean:+.0f} days")
        
        if sba_median > no_sba_median:
            pct_longer = ((sba_median / no_sba_median) - 1) * 100
            print(f"  SBA deals take {pct_longer:.0f}% longer to close")
    
    # 5. Launch Strategy Effectiveness
    print("\n5. LAUNCH STRATEGY ANALYSIS")
    print("-" * 40)
    
    strategy_df = df[df['launch_strategy'].notna()]
    strategy_success = strategy_df.groupby('launch_strategy').agg({
        'status': lambda x: (x == 'sold').sum() / len(x) * 100,
        'days_on_market': 'median',
        'id': 'count'
    }).round(1)
    strategy_success.columns = ['Success Rate %', 'Median Days', 'Count']
    print(strategy_success)
    
    # Save results
    df.to_csv('launch_date_analysis.csv', index=False)
    print("\n📁 Detailed results saved to launch_date_analysis.csv")
    
    # Create summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_listings': len(df),
        'with_launch_date': len(with_launch),
        'days_on_market': {}
    }
    
    for sba_status in ['yes', 'no', 'unknown']:
        sold_sba = sold_df[sold_df['sba_status'] == sba_status]
        if len(sold_sba) > 0 and sold_sba['days_on_market'].notna().any():
            summary['days_on_market'][f'{sba_status}_sold'] = {
                'count': len(sold_sba),
                'median': float(sold_sba['days_on_market'].median()),
                'mean': float(sold_sba['days_on_market'].mean()),
                'min': float(sold_sba['days_on_market'].min()),
                'max': float(sold_sba['days_on_market'].max())
            }
    
    with open('launch_date_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary

if __name__ == "__main__":
    # Analyze launch dates
    listings = analyze_launch_dates_for_cim_listings()
    
    if listings:
        summary = generate_time_on_market_report(listings)
        print("\n✅ Launch date analysis complete!")
    else:
        print("No data to analyze!")