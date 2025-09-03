#!/usr/bin/env python3
"""
Quick SBA analysis based on listing titles and LOI data.
Uses the data we can reliably access without external APIs.
"""

import pymysql
import pandas as pd
import numpy as np
from datetime import datetime
import json

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

def run_sba_analysis():
    """Run comprehensive SBA analysis using database data."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query for comprehensive SBA analysis
    query = """
    WITH sba_listings AS (
        SELECT 
            l.id,
            l.name,
            l.closed_type,
            l.closed_at,
            l.created_at,
            l.asking_at_close,
            l.sde_at_close,
            l.closed_commission,
            -- Identify SBA from title
            CASE 
                WHEN LOWER(l.name) LIKE '%sba%' 
                     AND LOWER(l.name) NOT LIKE '%not sba%' 
                     AND LOWER(l.name) NOT LIKE '%no sba%' 
                THEN 1 ELSE 0 
            END as is_sba_title,
            -- Status
            CASE
                WHEN l.closed_type = 1 THEN 'sold'
                WHEN l.closed_type = 2 THEN 'lost'
                ELSE 'active'
            END as status,
            -- Count inquiries
            (SELECT COUNT(*) FROM inquiries WHERE listing_id = l.id) as inquiry_count,
            -- Days from creation to close
            CASE 
                WHEN l.closed_at IS NOT NULL 
                THEN DATEDIFF(l.closed_at, l.created_at)
                ELSE NULL
            END as days_to_close
        FROM listings l
        WHERE l.deleted_at IS NULL
            AND l.google_drive_link IS NOT NULL
            AND l.google_drive_link != ''
    ),
    loi_data AS (
        SELECT 
            listing_id,
            MAX(has_sba) as any_loi_with_sba,
            COUNT(*) as total_lois,
            SUM(has_sba) as sba_lois
        FROM lois
        GROUP BY listing_id
    ),
    winning_lois AS (
        SELECT 
            csr.listing_id,
            loi.has_sba as winning_loi_used_sba
        FROM closed_sale_reports csr
        JOIN lois loi ON csr.loi_id = loi.id
    )
    SELECT 
        sl.*,
        ld.any_loi_with_sba,
        ld.total_lois,
        ld.sba_lois,
        wl.winning_loi_used_sba,
        -- Final SBA classification
        CASE
            WHEN sl.is_sba_title = 1 THEN 'sba_prequalified'
            WHEN ld.any_loi_with_sba = 1 THEN 'sba_possible'
            ELSE 'non_sba'
        END as sba_classification
    FROM sba_listings sl
    LEFT JOIN loi_data ld ON sl.id = ld.listing_id
    LEFT JOIN winning_lois wl ON sl.id = wl.listing_id
    WHERE sl.status IN ('sold', 'lost')
    """
    
    cursor.execute(query)
    result = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Convert to DataFrame
    if result:
        df = pd.DataFrame(result)
    else:
        df = pd.DataFrame()
    
    return df

def analyze_results(df):
    """Analyze the SBA impact."""
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_listings': len(df),
        'success_rates': {},
        'days_to_close': {},
        'sba_utilization': {},
        'financial_impact': {},
        'key_findings': []
    }
    
    # Handle NaN values in sba_classification
    if df['sba_classification'].isna().any():
        print(f"Warning: {df['sba_classification'].isna().sum()} rows have NaN classification")
        df['sba_classification'] = df['sba_classification'].fillna('non_sba')
    
    # 1. Success Rates by SBA Status
    for sba_class in df['sba_classification'].unique():
        if pd.isna(sba_class):
            continue
        subset = df[df['sba_classification'] == sba_class]
        sold = len(subset[subset['status'] == 'sold'])
        total = len(subset)
        success_rate = (sold / total * 100) if total > 0 else 0
        
        results['success_rates'][sba_class] = {
            'total': int(total),
            'sold': int(sold),
            'lost': int(total - sold),
            'success_rate': round(success_rate, 1)
        }
    
    # 2. Days to Close Analysis
    for sba_class in df['sba_classification'].unique():
        if pd.isna(sba_class):
            continue
        subset = df[(df['sba_classification'] == sba_class) & 
                   (df['status'] == 'sold') & 
                   (df['days_to_close'].notna())]
        
        if len(subset) > 0:
            results['days_to_close'][sba_class] = {
                'mean': round(subset['days_to_close'].mean(), 1),
                'median': round(subset['days_to_close'].median(), 1),
                'count': int(len(subset))
            }
    
    # 3. SBA Utilization Rate
    sba_prequalified_sold = df[(df['sba_classification'] == 'sba_prequalified') & 
                               (df['status'] == 'sold')]
    
    if len(sba_prequalified_sold) > 0:
        used_sba = len(sba_prequalified_sold[sba_prequalified_sold['winning_loi_used_sba'] == 1])
        utilization_rate = (used_sba / len(sba_prequalified_sold) * 100)
        
        results['sba_utilization'] = {
            'prequalified_sold': len(sba_prequalified_sold),
            'actually_used_sba': used_sba,
            'utilization_rate': round(utilization_rate, 1)
        }
    
    # 4. Financial Impact
    for sba_class in df['sba_classification'].unique():
        if pd.isna(sba_class):
            continue
        subset = df[df['sba_classification'] == sba_class]
        sold_subset = subset[subset['status'] == 'sold']
        
        # Handle NaN values in financial columns
        commission_sum = sold_subset['closed_commission'].fillna(0).sum()
        commission_mean = sold_subset['closed_commission'].dropna().mean() if len(sold_subset['closed_commission'].dropna()) > 0 else 0
        asking_mean = sold_subset['asking_at_close'].dropna().mean() if len(sold_subset['asking_at_close'].dropna()) > 0 else 0
        sde_mean = sold_subset['sde_at_close'].dropna().mean() if len(sold_subset['sde_at_close'].dropna()) > 0 else 0
        
        results['financial_impact'][sba_class] = {
            'total_commission': int(commission_sum) if not pd.isna(commission_sum) else 0,
            'avg_commission': int(commission_mean) if not pd.isna(commission_mean) else 0,
            'avg_asking_price': int(asking_mean) if not pd.isna(asking_mean) else 0,
            'avg_sde': int(sde_mean) if not pd.isna(sde_mean) else 0
        }
    
    # 5. Key Findings
    sba_success = results['success_rates'].get('sba_prequalified', {}).get('success_rate', 0)
    non_sba_success = results['success_rates'].get('non_sba', {}).get('success_rate', 0)
    
    if sba_success > 0 and non_sba_success > 0:
        improvement = ((sba_success / non_sba_success) - 1) * 100
        results['key_findings'].append(
            f"SBA pre-qualified listings have {improvement:.0f}% higher success rate"
        )
    
    sba_days = results['days_to_close'].get('sba_prequalified', {}).get('median')
    non_sba_days = results['days_to_close'].get('non_sba', {}).get('median')
    
    if sba_days and non_sba_days:
        day_diff = non_sba_days - sba_days
        if day_diff > 0:
            results['key_findings'].append(
                f"SBA listings close {day_diff:.0f} days faster on average"
            )
        else:
            results['key_findings'].append(
                f"SBA listings take {abs(day_diff):.0f} days longer to close"
            )
    
    return results

def print_report(results):
    """Print a formatted report."""
    
    print("\n" + "="*80)
    print("SBA IMPACT ANALYSIS REPORT")
    print("="*80)
    print(f"Analysis Date: {results['timestamp'][:10]}")
    print(f"Total Listings Analyzed: {results['total_listings']:,}")
    
    # Success Rates
    print("\n📊 SUCCESS RATES BY SBA STATUS")
    print("-"*40)
    for status, data in results['success_rates'].items():
        print(f"\n{status.upper().replace('_', ' ')}:")
        print(f"  Total: {data['total']}")
        print(f"  Sold: {data['sold']} ({data['success_rate']}%)")
        print(f"  Lost: {data['lost']} ({100-data['success_rate']:.1f}%)")
    
    # Days to Close
    print("\n⏱️ DAYS TO CLOSE (Successful Sales Only)")
    print("-"*40)
    for status, data in results['days_to_close'].items():
        print(f"\n{status.upper().replace('_', ' ')}:")
        print(f"  Mean: {data['mean']} days")
        print(f"  Median: {data['median']} days")
        print(f"  Sample Size: {data['count']}")
    
    # SBA Utilization
    if results['sba_utilization']:
        print("\n🎯 SBA UTILIZATION RATE")
        print("-"*40)
        util = results['sba_utilization']
        print(f"  SBA Pre-qualified Sold: {util['prequalified_sold']}")
        print(f"  Actually Used SBA: {util['actually_used_sba']}")
        print(f"  Utilization Rate: {util['utilization_rate']}%")
    
    # Financial Impact
    print("\n💰 FINANCIAL IMPACT")
    print("-"*40)
    for status, data in results['financial_impact'].items():
        print(f"\n{status.upper().replace('_', ' ')}:")
        print(f"  Total Commission: ${data['total_commission']:,}")
        print(f"  Avg Commission: ${data['avg_commission']:,}")
        print(f"  Avg Asking Price: ${data['avg_asking_price']:,}")
        print(f"  Avg SDE: ${data['avg_sde']:,}")
    
    # Key Findings
    print("\n🔑 KEY FINDINGS")
    print("-"*40)
    for finding in results['key_findings']:
        print(f"  • {finding}")
    
    # Save results
    with open('sba_analysis_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n📁 Results saved to sba_analysis_results.json")

if __name__ == "__main__":
    print("Running SBA Impact Analysis...")
    print("Using database titles and LOI data for classification")
    
    # Run analysis
    df = run_sba_analysis()
    
    # Analyze results
    results = analyze_results(df)
    
    # Print report
    print_report(results)
    
    # Save detailed data
    df.to_csv('sba_analysis_detailed.csv', index=False)
    print("📁 Detailed data saved to sba_analysis_detailed.csv")
    
    print("\n✅ Analysis complete!")