#!/usr/bin/env python3
"""
Final comprehensive median multiples analysis using all available data sources.
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
    print("FINAL COMPREHENSIVE SBA vs Non-SBA Median Multiple Analysis")
    print("=" * 80)
    print()
    
    # Load the SBA classification data
    print("Loading SBA classification data...")
    df_classification = pd.read_csv('launch_date_analysis.csv')
    
    # Get listing IDs for each category
    sba_ids = df_classification[df_classification['sba_status'] == 'yes']['id'].tolist()
    non_sba_ids = df_classification[df_classification['sba_status'] == 'no']['id'].tolist()
    unknown_ids = df_classification[df_classification['sba_status'] == 'unknown']['id'].tolist()
    
    print(f"Found {len(sba_ids)} SBA pre-qualified listings")
    print(f"Found {len(non_sba_ids)} non-SBA listings") 
    print(f"Found {len(unknown_ids)} unknown status listings")
    print()
    
    # Connect to database
    print("Connecting to database and fetching financial data...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query for ALL listings, not just the ones in our CSV
    # This will give us maximum data coverage
    query = """
    SELECT 
        l.id,
        l.name,
        l.capsule_expected_value,
        l.asking_at_close,
        l.sde_at_close,
        l.revenue_at_close,
        MAX(CASE WHEN lcf.custom_field_id = 3 THEN lcf.value END) as cashflow,
        MAX(CASE WHEN lcf.custom_field_id = 4 THEN lcf.value END) as asking,
        MAX(CASE WHEN lcf.custom_field_id = 2 THEN lcf.value END) as revenue
    FROM listings l
    LEFT JOIN listing_custom_fields lcf ON l.id = lcf.listing_id
    WHERE lcf.custom_field_id IN (2, 3, 4) OR lcf.custom_field_id IS NULL
    GROUP BY l.id, l.name, l.capsule_expected_value, l.asking_at_close, l.sde_at_close, l.revenue_at_close
    HAVING (cashflow IS NOT NULL OR sde_at_close IS NOT NULL) 
       AND (asking IS NOT NULL OR asking_at_close IS NOT NULL OR capsule_expected_value IS NOT NULL)
    """
    
    cursor.execute(query)
    listings_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convert to DataFrame
    df_all = pd.DataFrame(listings_data)
    print(f"Retrieved {len(df_all)} listings with financial data from database")
    
    # Determine asking price and SDE
    def get_asking_price(row):
        # Priority: custom field 'asking', then asking_at_close, then capsule_expected_value
        if pd.notna(row.get('asking')):
            try:
                val = float(str(row['asking']).replace(',', '').replace('$', ''))
                if val > 0:
                    return val
            except:
                pass
        
        if pd.notna(row.get('asking_at_close')) and row['asking_at_close'] > 0:
            return row['asking_at_close']
        
        if pd.notna(row.get('capsule_expected_value')) and row['capsule_expected_value'] > 0:
            return row['capsule_expected_value']
        
        return None
    
    def get_sde(row):
        # Priority: custom field 'cashflow', then sde_at_close
        if pd.notna(row.get('cashflow')):
            try:
                val = float(str(row['cashflow']).replace(',', '').replace('$', ''))
                if val > 0:
                    return val
            except:
                pass
        
        if pd.notna(row.get('sde_at_close')) and row['sde_at_close'] > 0:
            return row['sde_at_close']
        
        return None
    
    df_all['asking_price'] = df_all.apply(get_asking_price, axis=1)
    df_all['sde'] = df_all.apply(get_sde, axis=1)
    
    # Calculate multiples
    df_all['multiple'] = df_all.apply(
        lambda row: row['asking_price'] / row['sde'] 
        if pd.notna(row['sde']) and row['sde'] > 0 and pd.notna(row['asking_price']) and row['asking_price'] > 0 
        else None,
        axis=1
    )
    
    # Add SBA status - for listings not in our CSV, mark as 'not_classified'
    def get_sba_status(listing_id):
        if listing_id in sba_ids:
            return 'yes'
        elif listing_id in non_sba_ids:
            return 'no'
        elif listing_id in unknown_ids:
            return 'unknown'
        else:
            return 'not_classified'
    
    df_all['sba_status'] = df_all['id'].apply(get_sba_status)
    
    # Show data distribution
    print(f"\nSBA classification coverage:")
    print(df_all['sba_status'].value_counts())
    
    # Filter for valid multiples (reasonable range: 0.5 to 10x)
    df_valid = df_all[
        (df_all['multiple'].notna()) & 
        (df_all['multiple'] > 0.5) & 
        (df_all['multiple'] < 10)
    ].copy()
    
    print(f"\nFiltered to {len(df_valid)} listings with valid multiples (0.5x - 10x)")
    print("By SBA status:")
    print(df_valid['sba_status'].value_counts())
    
    # Separate by SBA status (only classified listings)
    sba_multiples = df_valid[df_valid['sba_status'] == 'yes']['multiple'].values
    non_sba_multiples = df_valid[df_valid['sba_status'] == 'no']['multiple'].values
    unknown_multiples = df_valid[df_valid['sba_status'] == 'unknown']['multiple'].values
    not_classified_multiples = df_valid[df_valid['sba_status'] == 'not_classified']['multiple'].values
    
    # Calculate statistics
    results = {
        'timestamp': datetime.now().isoformat(),
        'data_source': 'comprehensive_database_query',
        'total_listings_with_data': len(df_all),
        'total_valid_multiples': len(df_valid),
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
        },
        'not_classified': {
            'count': len(not_classified_multiples),
            'median': float(np.median(not_classified_multiples)) if len(not_classified_multiples) > 0 else None,
            'mean': float(np.mean(not_classified_multiples)) if len(not_classified_multiples) > 0 else None
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
    print("RESULTS: FINAL MEDIAN MULTIPLES ANALYSIS")
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
    
    # Save results to JSON
    output_file = 'final_multiples_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to {output_file}")
    
    # Save detailed data to CSV
    csv_file = 'final_multiples_details.csv'
    df_valid[df_valid['sba_status'].isin(['yes', 'no', 'unknown'])][
        ['id', 'name', 'asking_price', 'sde', 'multiple', 'sba_status']
    ].to_csv(csv_file, index=False)
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
    print("DATA NOTES:")
    print("=" * 80)
    print(f"• Total database listings with financial data: {len(df_all):,}")
    print(f"• Listings with valid multiples (0.5x-10x): {len(df_valid):,}")
    print(f"• Classified in our SBA analysis: {len(df_valid[df_valid['sba_status'] != 'not_classified']):,}")
    print(f"• Not yet classified: {len(not_classified_multiples):,}")
    print("\nThis represents the most comprehensive analysis possible with available data.")

if __name__ == "__main__":
    main()