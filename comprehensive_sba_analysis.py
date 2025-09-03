#!/usr/bin/env python3
"""
Comprehensive SBA Impact Analysis
Combines CIM processing, database analysis, and opportunity cost calculations.
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pymysql
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

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

def get_listings_with_sba_data():
    """
    Get all listings with their SBA status from database and LOIs.
    """
    conn = get_db_connection()
    
    query = """
    WITH listing_sba AS (
        SELECT 
            l.id as listing_id,
            l.name as listing_name,
            l.closed_type,
            l.closed_at,
            l.created_at,
            l.milestone_id,
            l.asking_at_close,
            l.sde_at_close,
            l.closed_commission,
            CASE 
                WHEN LOWER(l.name) LIKE '%sba%' AND LOWER(l.name) NOT LIKE '%not sba%' 
                     AND LOWER(l.name) NOT LIKE '%no sba%' THEN 1
                ELSE 0
            END as title_indicates_sba,
            CASE
                WHEN l.closed_type = 1 OR l.milestone_id = 7 THEN 'sold'
                WHEN l.closed_type = 2 OR l.milestone_id = 8 THEN 'lost'
                ELSE 'active'
            END as status
        FROM listings l
        WHERE l.deleted_at IS NULL
            AND l.milestone_id NOT IN (4, 5, 6)  -- Exclude certain milestones
            AND (l.closed_type IN (1, 2) OR l.milestone_id IN (7, 8))
    ),
    winning_lois AS (
        SELECT 
            csr.listing_id,
            loi.has_sba as winning_loi_used_sba,
            loi.cash_at_close,
            loi.offer_type
        FROM closed_sale_reports csr
        JOIN lois loi ON csr.loi_id = loi.id
    ),
    all_lois AS (
        SELECT 
            listing_id,
            MAX(has_sba) as any_loi_mentioned_sba,
            COUNT(*) as total_lois,
            SUM(has_sba) as sba_lois_count
        FROM lois
        GROUP BY listing_id
    )
    SELECT 
        ls.*,
        wl.winning_loi_used_sba,
        wl.cash_at_close,
        al.any_loi_mentioned_sba,
        al.total_lois,
        al.sba_lois_count
    FROM listing_sba ls
    LEFT JOIN winning_lois wl ON ls.listing_id = wl.listing_id
    LEFT JOIN all_lois al ON ls.listing_id = al.listing_id
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    return df

def calculate_inquiry_based_launch_dates():
    """
    Calculate launch dates based on inquiry volume spikes.
    Simplified version that handles data type issues.
    """
    conn = get_db_connection()
    
    # Get daily inquiry counts
    query = """
    SELECT 
        listing_id,
        DATE(created_at) as inquiry_date,
        COUNT(*) as daily_count
    FROM inquiries
    WHERE listing_id IN (
        SELECT id FROM listings 
        WHERE deleted_at IS NULL
        AND (closed_type IN (1, 2) OR milestone_id IN (7, 8))
    )
    GROUP BY listing_id, DATE(created_at)
    """
    
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    
    # Process results to find launch dates
    launch_dates = {}
    listing_data = {}
    
    for row in results:
        lid = row['listing_id']
        if lid not in listing_data:
            listing_data[lid] = []
        listing_data[lid].append({
            'date': row['inquiry_date'],
            'count': row['daily_count']
        })
    
    # Find spikes for each listing
    for lid, data in listing_data.items():
        data_sorted = sorted(data, key=lambda x: x['date'])
        
        # Look for 2-day windows with 20+ inquiries
        for i in range(len(data_sorted)):
            two_day_total = data_sorted[i]['count']
            if i + 1 < len(data_sorted):
                delta = (data_sorted[i+1]['date'] - data_sorted[i]['date']).days
                if delta == 1:
                    two_day_total += data_sorted[i+1]['count']
            
            if two_day_total >= 20:
                launch_dates[lid] = {
                    'launch_date': data_sorted[i]['date'],
                    'spike_volume': two_day_total
                }
                break
    
    # Get listing dates for days on market calculation
    query2 = """
    SELECT 
        id as listing_id,
        created_at,
        closed_at
    FROM listings
    WHERE id IN ({})
    """.format(','.join(map(str, launch_dates.keys())))
    
    if launch_dates:
        cursor.execute(query2)
        listing_info = {row['listing_id']: row for row in cursor.fetchall()}
        
        # Calculate days on market
        for lid, launch_info in launch_dates.items():
            if lid in listing_info:
                info = listing_info[lid]
                if info['closed_at']:
                    # Convert date to datetime for comparison
                    launch_datetime = datetime.combine(launch_info['launch_date'], datetime.min.time())
                    days_on_market = (info['closed_at'] - launch_datetime).days
                    launch_dates[lid]['days_on_market'] = days_on_market
                else:
                    launch_dates[lid]['days_on_market'] = None
    
    conn.close()
    
    return launch_dates

def load_cim_sba_analysis():
    """
    Load CIM analysis results if available, otherwise return empty dict.
    """
    sba_file = 'sba_cim_analysis.json'
    if os.path.exists(sba_file):
        with open(sba_file, 'r') as f:
            data = json.load(f)
            # Convert to dict keyed by listing_id
            return {item['listing_id']: item for item in data if 'listing_id' in item}
    return {}

def analyze_sba_impact(listings_df, launch_dates, cim_analysis):
    """
    Perform comprehensive SBA impact analysis.
    """
    # Add launch date data
    listings_df['launch_date'] = listings_df['listing_id'].map(
        lambda x: launch_dates.get(x, {}).get('launch_date')
    )
    listings_df['days_on_market'] = listings_df['listing_id'].map(
        lambda x: launch_dates.get(x, {}).get('days_on_market')
    )
    
    # Add CIM analysis data
    listings_df['cim_sba_status'] = listings_df['listing_id'].map(
        lambda x: cim_analysis.get(x, {}).get('sba_status', 'unknown')
    )
    listings_df['cim_sba_confidence'] = listings_df['listing_id'].map(
        lambda x: cim_analysis.get(x, {}).get('confidence', 0)
    )
    
    # Determine final SBA pre-qualification status
    def determine_sba_status(row):
        # Priority: CIM analysis > Title indication > LOI mentions
        if row['cim_sba_status'] == 'qualified' and row['cim_sba_confidence'] > 0.5:
            return 'sba_prequalified'
        elif row['cim_sba_status'] == 'not_qualified' and row['cim_sba_confidence'] > 0.5:
            return 'not_sba'
        elif row['title_indicates_sba'] == 1:
            return 'sba_prequalified'
        elif pd.notna(row['any_loi_mentioned_sba']):
            try:
                if float(row['any_loi_mentioned_sba']) > 0:
                    return 'likely_sba'
            except (ValueError, TypeError):
                pass
        return 'not_sba'
    
    listings_df['sba_status'] = listings_df.apply(determine_sba_status, axis=1)
    
    # Analysis 1: Success/Failure Rates
    success_rates = {}
    for sba_status in ['sba_prequalified', 'not_sba', 'likely_sba']:
        subset = listings_df[listings_df['sba_status'] == sba_status]
        if len(subset) > 0:
            success_rate = len(subset[subset['status'] == 'sold']) / len(subset)
            success_rates[sba_status] = {
                'total': len(subset),
                'sold': len(subset[subset['status'] == 'sold']),
                'lost': len(subset[subset['status'] == 'lost']),
                'success_rate': success_rate
            }
    
    # Analysis 2: Days on Market
    dom_analysis = {}
    for sba_status in ['sba_prequalified', 'not_sba']:
        subset = listings_df[
            (listings_df['sba_status'] == sba_status) & 
            (listings_df['days_on_market'].notna()) &
            (listings_df['status'] == 'sold')
        ]
        if len(subset) > 0:
            dom_analysis[sba_status] = {
                'mean': subset['days_on_market'].mean(),
                'median': subset['days_on_market'].median(),
                'std': subset['days_on_market'].std(),
                'count': len(subset)
            }
    
    # Analysis 3: SBA Utilization Rate
    sba_prequalified = listings_df[
        (listings_df['sba_status'] == 'sba_prequalified') & 
        (listings_df['status'] == 'sold')
    ]
    
    if len(sba_prequalified) > 0:
        used_sba = len(sba_prequalified[sba_prequalified['winning_loi_used_sba'] == 1])
        utilization_rate = used_sba / len(sba_prequalified)
    else:
        utilization_rate = 0
    
    # Analysis 4: Opportunity Cost
    # Calculate actual revenue
    actual_revenue = {}
    for sba_status in ['sba_prequalified', 'not_sba']:
        subset = listings_df[listings_df['sba_status'] == sba_status]
        actual_revenue[sba_status] = {
            'total_commission': subset['closed_commission'].sum(),
            'avg_commission': subset['closed_commission'].mean(),
            'avg_asking_price': subset['asking_at_close'].mean(),
            'avg_sde': subset['sde_at_close'].mean()
        }
    
    # Fixed revenue scenario (assuming $50k per successful deal)
    FIXED_REVENUE = 50000
    opportunity_cost = {}
    for sba_status in ['sba_prequalified', 'not_sba']:
        if sba_status in success_rates:
            sr = success_rates[sba_status]
            actual_total = actual_revenue[sba_status]['total_commission']
            theoretical_total = sr['sold'] * FIXED_REVENUE
            
            opportunity_cost[sba_status] = {
                'actual_revenue': actual_total,
                'theoretical_fixed_revenue': theoretical_total,
                'difference': theoretical_total - actual_total,
                'deals_count': sr['sold']
            }
    
    # Statistical significance test
    if 'sba_prequalified' in success_rates and 'not_sba' in success_rates:
        # Chi-square test for success rates
        sba_sold = success_rates['sba_prequalified']['sold']
        sba_lost = success_rates['sba_prequalified']['lost']
        non_sba_sold = success_rates['not_sba']['sold']
        non_sba_lost = success_rates['not_sba']['lost']
        
        contingency_table = [[sba_sold, sba_lost], [non_sba_sold, non_sba_lost]]
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        
        statistical_significance = {
            'chi2': chi2,
            'p_value': p_value,
            'significant': p_value < 0.05
        }
    else:
        statistical_significance = {'error': 'Insufficient data for significance test'}
    
    return {
        'success_rates': success_rates,
        'days_on_market': dom_analysis,
        'sba_utilization_rate': utilization_rate,
        'opportunity_cost': opportunity_cost,
        'actual_revenue': actual_revenue,
        'statistical_significance': statistical_significance,
        'summary_df': listings_df
    }

def generate_report(analysis_results):
    """
    Generate a comprehensive report of the SBA analysis.
    """
    print("\n" + "="*80)
    print("SBA IMPACT ANALYSIS REPORT")
    print("="*80)
    
    # Success Rates
    print("\n1. SUCCESS/FAILURE RATES BY SBA STATUS")
    print("-" * 40)
    for status, data in analysis_results['success_rates'].items():
        print(f"\n{status.upper()}:")
        print(f"  Total Listings: {data['total']}")
        print(f"  Sold: {data['sold']} ({data['success_rate']*100:.1f}%)")
        print(f"  Lost: {data['lost']} ({(1-data['success_rate'])*100:.1f}%)")
    
    # Days on Market
    print("\n2. DAYS ON MARKET ANALYSIS")
    print("-" * 40)
    for status, data in analysis_results['days_on_market'].items():
        print(f"\n{status.upper()}:")
        print(f"  Mean: {data['mean']:.1f} days")
        print(f"  Median: {data['median']:.1f} days")
        print(f"  Std Dev: {data['std']:.1f} days")
        print(f"  Sample Size: {data['count']} listings")
    
    # SBA Utilization
    print("\n3. SBA UTILIZATION RATE")
    print("-" * 40)
    print(f"  Of SBA pre-qualified listings that sold:")
    print(f"  {analysis_results['sba_utilization_rate']*100:.1f}% actually used SBA financing")
    
    # Opportunity Cost
    print("\n4. OPPORTUNITY COST ANALYSIS")
    print("-" * 40)
    for status, data in analysis_results['opportunity_cost'].items():
        print(f"\n{status.upper()}:")
        print(f"  Actual Revenue: ${data['actual_revenue']:,.0f}")
        print(f"  Theoretical Fixed Revenue: ${data['theoretical_fixed_revenue']:,.0f}")
        print(f"  Difference: ${data['difference']:+,.0f}")
        print(f"  Number of Deals: {data['deals_count']}")
    
    # Statistical Significance
    print("\n5. STATISTICAL SIGNIFICANCE")
    print("-" * 40)
    sig = analysis_results['statistical_significance']
    if 'p_value' in sig:
        print(f"  Chi-square statistic: {sig['chi2']:.3f}")
        print(f"  P-value: {sig['p_value']:.4f}")
        print(f"  Statistically significant: {'YES' if sig['significant'] else 'NO'}")
    else:
        print(f"  {sig.get('error', 'Unable to calculate')}")
    
    # Save detailed results
    output_file = 'sba_analysis_results.json'
    
    # Convert numpy types for JSON serialization
    def convert_types(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return obj
    
    # Deep copy and convert
    json_safe = json.loads(json.dumps(analysis_results, default=convert_types))
    
    with open(output_file, 'w') as f:
        json.dump(json_safe, f, indent=2)
    
    print(f"\n\nDetailed results saved to {output_file}")
    
    # Save summary CSV
    summary_df = analysis_results['summary_df']
    summary_df.to_csv('sba_analysis_summary.csv', index=False)
    print(f"Summary data saved to sba_analysis_summary.csv")

if __name__ == "__main__":
    print("Starting Comprehensive SBA Impact Analysis")
    print("=" * 60)
    
    # Step 1: Get listings data
    print("\n1. Loading listings data from database...")
    listings_df = get_listings_with_sba_data()
    print(f"   Loaded {len(listings_df)} listings")
    
    # Step 2: Calculate launch dates
    print("\n2. Calculating launch dates based on inquiry spikes...")
    launch_dates = calculate_inquiry_based_launch_dates()
    print(f"   Calculated launch dates for {len(launch_dates)} listings")
    
    # Step 3: Load CIM analysis (if available)
    print("\n3. Loading CIM analysis results...")
    cim_analysis = load_cim_sba_analysis()
    if cim_analysis:
        print(f"   Loaded CIM analysis for {len(cim_analysis)} listings")
    else:
        print("   No CIM analysis found - using database indicators only")
    
    # Step 4: Perform comprehensive analysis
    print("\n4. Performing comprehensive SBA impact analysis...")
    analysis_results = analyze_sba_impact(listings_df, launch_dates, cim_analysis)
    
    # Step 5: Generate report
    generate_report(analysis_results)
    
    print("\n" + "="*60)
    print("Analysis complete!")
    
    # Display data quality notes
    print("\nDATA QUALITY NOTES:")
    print("-" * 40)
    print(f"- Listings with launch dates: {len(launch_dates)}/{len(listings_df)}")
    print(f"- Listings with CIM analysis: {len(cim_analysis)}/{len(listings_df)}")
    
    undetermined = listings_df[listings_df['sba_status'] == 'unknown']
    if len(undetermined) > 0:
        print(f"- Listings with undetermined SBA status: {len(undetermined)}")
        print("  These require manual review in the dashboard")