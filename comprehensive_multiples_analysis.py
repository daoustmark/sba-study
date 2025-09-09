#!/usr/bin/env python3
"""
Comprehensive median multiples analysis combining all data sources.
"""

import pandas as pd
import numpy as np
import pymysql
import json
from datetime import datetime

def get_db_connection():
    """Establish connection to MySQL database."""
    return pymysql.connect(
        host='127.0.0.1',
        port=3307,
        user='forge',
        password='mFGaHKEBBYLqpnUV3VUW',
        database='ac_prod',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def main():
    print("=" * 80)
    print("COMPREHENSIVE SBA vs Non-SBA Median Multiple Analysis")
    print("=" * 80)
    print()
    
    # Load the SBA classification data
    print("Loading SBA classification data...")
    df_classification = pd.read_csv('launch_date_analysis.csv')
    
    # Get listing IDs for each category
    sba_ids = df_classification[df_classification['sba_status'] == 'yes']['id'].tolist()
    non_sba_ids = df_classification[df_classification['sba_status'] == 'no']['id'].tolist()
    unknown_ids = df_classification[df_classification['sba_status'] == 'unknown']['id'].tolist()
    
    print(f"Classification from CSV:")
    print(f"  SBA pre-qualified: {len(sba_ids)}")
    print(f"  Non-SBA: {len(non_sba_ids)}")
    print(f"  Unknown: {len(unknown_ids)}")
    
    # 1. Get database data
    print("\n1. Fetching database data...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    all_ids = sba_ids + non_sba_ids + unknown_ids
    id_list = ','.join(map(str, all_ids))
    
    query = f"""
    SELECT 
        l.id,
        l.name,
        l.asking_at_close,
        l.sde_at_close,
        l.revenue_at_close,
        l.capsule_expected_value
    FROM listings l
    WHERE l.id IN ({id_list})
    """
    
    cursor.execute(query)
    db_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    df_db = pd.DataFrame(db_data)
    df_db['source'] = 'database'
    df_db['asking_price'] = df_db.apply(
        lambda row: row['asking_at_close'] if pd.notna(row['asking_at_close']) and row['asking_at_close'] > 0 
        else row['capsule_expected_value'] if pd.notna(row['capsule_expected_value']) and row['capsule_expected_value'] > 0
        else None,
        axis=1
    )
    df_db['sde'] = df_db['sde_at_close']
    
    # 2. Load CIM analysis data
    print("2. Loading CIM analysis data...")
    with open('cim_analysis_results_20250829_154455.json', 'r') as f:
        cim_data = json.load(f)
    
    df_cim = pd.DataFrame(cim_data)
    df_cim['source'] = 'cim'
    df_cim['id'] = df_cim['listing_id']
    df_cim['asking_price'] = pd.to_numeric(df_cim['asking_price'], errors='coerce')
    df_cim['sde'] = pd.to_numeric(df_cim['sde'], errors='coerce')
    
    # Map CIM SBA status to our classification
    df_cim['cim_sba'] = df_cim['sba_eligible']
    
    # 3. Merge data sources, preferring database data when available
    print("3. Merging data sources...")
    
    # Start with all IDs
    all_data = []
    
    for listing_id in all_ids:
        record = {'id': listing_id}
        
        # Get SBA status from CSV
        if listing_id in sba_ids:
            record['sba_status'] = 'yes'
        elif listing_id in non_sba_ids:
            record['sba_status'] = 'no'
        else:
            record['sba_status'] = 'unknown'
        
        # Try to get financials from database first
        db_row = df_db[df_db['id'] == listing_id]
        if not db_row.empty:
            db_asking = db_row.iloc[0]['asking_price']
            db_sde = db_row.iloc[0]['sde']
            if pd.notna(db_asking) and pd.notna(db_sde) and db_asking > 0 and db_sde > 0:
                record['asking_price'] = db_asking
                record['sde'] = db_sde
                record['source'] = 'database'
                record['name'] = db_row.iloc[0]['name']
                all_data.append(record)
                continue
        
        # If no database data, try CIM
        cim_row = df_cim[df_cim['id'] == listing_id]
        if not cim_row.empty:
            cim_asking = cim_row.iloc[0]['asking_price']
            cim_sde = cim_row.iloc[0]['sde']
            if pd.notna(cim_asking) and pd.notna(cim_sde) and cim_asking > 0 and cim_sde > 0:
                record['asking_price'] = cim_asking
                record['sde'] = cim_sde
                record['source'] = 'cim'
                record['name'] = f"Listing {listing_id}"
                all_data.append(record)
    
    df_combined = pd.DataFrame(all_data)
    
    # Calculate multiples
    df_combined['multiple'] = df_combined['asking_price'] / df_combined['sde']
    
    # Filter for valid multiples (reasonable range: 0.5 to 10x)
    df_valid = df_combined[
        (df_combined['multiple'] >= 0.5) & 
        (df_combined['multiple'] <= 10)
    ].copy()
    
    print(f"\nData sources combined:")
    print(f"  Total with financials: {len(df_combined)}")
    print(f"  Valid multiples (0.5x-10x): {len(df_valid)}")
    print(f"  From database: {len(df_valid[df_valid['source'] == 'database'])}")
    print(f"  From CIM: {len(df_valid[df_valid['source'] == 'cim'])}")
    
    # Separate by SBA status
    sba_multiples = df_valid[df_valid['sba_status'] == 'yes']['multiple'].values
    non_sba_multiples = df_valid[df_valid['sba_status'] == 'no']['multiple'].values
    unknown_multiples = df_valid[df_valid['sba_status'] == 'unknown']['multiple'].values
    
    # Calculate statistics
    results = {
        'timestamp': datetime.now().isoformat(),
        'data_sources': 'Combined (Database + CIM)',
        'sba_prequalified': {
            'count': len(sba_multiples),
            'median': float(np.median(sba_multiples)) if len(sba_multiples) > 0 else None,
            'mean': float(np.mean(sba_multiples)) if len(sba_multiples) > 0 else None,
            'std': float(np.std(sba_multiples)) if len(sba_multiples) > 0 else None,
            'min': float(np.min(sba_multiples)) if len(sba_multiples) > 0 else None,
            'max': float(np.max(sba_multiples)) if len(sba_multiples) > 0 else None,
            'q25': float(np.percentile(sba_multiples, 25)) if len(sba_multiples) > 0 else None,
            'q75': float(np.percentile(sba_multiples, 75)) if len(sba_multiples) > 0 else None
        },
        'non_sba': {
            'count': len(non_sba_multiples),
            'median': float(np.median(non_sba_multiples)) if len(non_sba_multiples) > 0 else None,
            'mean': float(np.mean(non_sba_multiples)) if len(non_sba_multiples) > 0 else None,
            'std': float(np.std(non_sba_multiples)) if len(non_sba_multiples) > 0 else None,
            'min': float(np.min(non_sba_multiples)) if len(non_sba_multiples) > 0 else None,
            'max': float(np.max(non_sba_multiples)) if len(non_sba_multiples) > 0 else None,
            'q25': float(np.percentile(non_sba_multiples, 25)) if len(non_sba_multiples) > 0 else None,
            'q75': float(np.percentile(non_sba_multiples, 75)) if len(non_sba_multiples) > 0 else None
        }
    }
    
    # Calculate differences
    if results['sba_prequalified']['median'] and results['non_sba']['median']:
        median_diff = results['sba_prequalified']['median'] - results['non_sba']['median']
        median_diff_pct = (median_diff / results['non_sba']['median']) * 100
        results['comparison'] = {
            'median_difference': median_diff,
            'median_difference_percent': median_diff_pct,
            'sba_premium': median_diff > 0
        }
    
    # Print results
    print("\n" + "=" * 80)
    print("RESULTS: COMPREHENSIVE MEDIAN MULTIPLES ANALYSIS")
    print("=" * 80)
    
    print("\n📊 SBA Pre-qualified Deals:")
    print(f"   Count: {results['sba_prequalified']['count']} listings")
    if results['sba_prequalified']['median']:
        print(f"   Median Multiple: {results['sba_prequalified']['median']:.2f}x")
        print(f"   Mean Multiple: {results['sba_prequalified']['mean']:.2f}x")
        print(f"   Range: {results['sba_prequalified']['min']:.2f}x - {results['sba_prequalified']['max']:.2f}x")
        print(f"   IQR: {results['sba_prequalified']['q25']:.2f}x - {results['sba_prequalified']['q75']:.2f}x")
    
    print("\n📊 Non-SBA Deals:")
    print(f"   Count: {results['non_sba']['count']} listings")
    if results['non_sba']['median']:
        print(f"   Median Multiple: {results['non_sba']['median']:.2f}x")
        print(f"   Mean Multiple: {results['non_sba']['mean']:.2f}x")
        print(f"   Range: {results['non_sba']['min']:.2f}x - {results['non_sba']['max']:.2f}x")
        print(f"   IQR: {results['non_sba']['q25']:.2f}x - {results['non_sba']['q75']:.2f}x")
    
    if 'comparison' in results:
        print("\n" + "=" * 80)
        print("KEY FINDING:")
        print("=" * 80)
        if results['comparison']['sba_premium']:
            print(f"✅ SBA pre-qualified deals have HIGHER median multiples")
            print(f"   Difference: +{results['comparison']['median_difference']:.2f}x")
            print(f"   Percentage: +{results['comparison']['median_difference_percent']:.1f}%")
        else:
            print(f"⚠️  SBA pre-qualified deals have LOWER median multiples")
            print(f"   Difference: {results['comparison']['median_difference']:.2f}x")
            print(f"   Percentage: {results['comparison']['median_difference_percent']:.1f}%")
    
    # Save results
    output_file = 'comprehensive_multiples_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to {output_file}")
    
    # Save detailed data
    csv_file = 'comprehensive_multiples_details.csv'
    df_valid.to_csv(csv_file, index=False)
    print(f"💾 Detailed data saved to {csv_file}")
    
    # Distribution analysis
    print("\n" + "=" * 80)
    print("DISTRIBUTION ANALYSIS:")
    print("=" * 80)
    
    ranges = [(0, 2), (2, 3), (3, 4), (4, 5), (5, 10)]
    
    for status, multiples in [('SBA', sba_multiples), ('Non-SBA', non_sba_multiples)]:
        if len(multiples) > 0:
            print(f"\n{status} Distribution:")
            for low, high in ranges:
                count = np.sum((multiples >= low) & (multiples < high))
                pct = (count / len(multiples)) * 100
                print(f"   {low}x-{high}x: {count} deals ({pct:.1f}%)")
    
    print("\n" + "=" * 80)
    print("DATA LIMITATIONS:")
    print("=" * 80)
    print("This analysis combines all available financial data sources:")
    print("1. Database: asking_at_close and sde_at_close (mostly closed deals)")
    print("2. CIM Analysis: Extracted asking price and SDE from documents")
    print("3. Only ~30% of listings have complete financial data available")
    print("4. Results are based on the best available data")

if __name__ == "__main__":
    main()