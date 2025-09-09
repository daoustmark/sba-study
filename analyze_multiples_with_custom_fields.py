#!/usr/bin/env python3
"""
Analyze median multiples using listing_custom_fields table for financial data.
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
    print("SBA vs Non-SBA Median Multiple Analysis (Using Custom Fields)")
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
    print("Connecting to database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First, check what fields are available in listing_custom_fields
    cursor.execute("""
        SELECT DISTINCT field_name 
        FROM listing_custom_fields 
        WHERE field_name LIKE '%sde%' 
           OR field_name LIKE '%cash%' 
           OR field_name LIKE '%ask%'
           OR field_name LIKE '%price%'
           OR field_name LIKE '%revenue%'
        ORDER BY field_name
    """)
    
    fields = cursor.fetchall()
    print("Available financial fields in listing_custom_fields:")
    for f in fields:
        print(f"  - {f['field_name']}")
    print()
    
    # Query for financial data joining with custom fields
    all_ids = sba_ids + non_sba_ids + unknown_ids
    id_list = ','.join(map(str, all_ids))
    
    query = f"""
    SELECT 
        l.id,
        l.name,
        l.capsule_expected_value,
        l.asking_at_close,
        l.sde_at_close,
        MAX(CASE WHEN cf.field_name = 'sde' THEN cf.field_value END) as sde_custom,
        MAX(CASE WHEN cf.field_name = 'cashflow' THEN cf.field_value END) as cashflow,
        MAX(CASE WHEN cf.field_name = 'asking_price' THEN cf.field_value END) as asking_price_custom,
        MAX(CASE WHEN cf.field_name = 'asking' THEN cf.field_value END) as asking_custom,
        MAX(CASE WHEN cf.field_name = 'revenue' THEN cf.field_value END) as revenue_custom
    FROM listings l
    LEFT JOIN listing_custom_fields cf ON l.id = cf.listing_id
    WHERE l.id IN ({id_list})
    GROUP BY l.id, l.name, l.capsule_expected_value, l.asking_at_close, l.sde_at_close
    """
    
    print("Fetching listing data from database...")
    cursor.execute(query)
    listings_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convert to DataFrame
    df_listings = pd.DataFrame(listings_data)
    
    print(f"Retrieved {len(df_listings)} listings from database")
    
    # Determine asking price (prioritize custom fields, then at_close, then expected_value)
    def get_asking_price(row):
        # Try custom fields first
        for field in ['asking_price_custom', 'asking_custom']:
            if pd.notna(row.get(field)):
                try:
                    val = float(str(row[field]).replace(',', '').replace('$', ''))
                    if val > 0:
                        return val
                except:
                    pass
        
        # Then try asking_at_close
        if pd.notna(row.get('asking_at_close')) and row['asking_at_close'] > 0:
            return row['asking_at_close']
        
        # Finally try capsule_expected_value
        if pd.notna(row.get('capsule_expected_value')) and row['capsule_expected_value'] > 0:
            return row['capsule_expected_value']
        
        return None
    
    # Determine SDE (prioritize custom fields, then at_close)
    def get_sde(row):
        # Try custom fields first
        for field in ['sde_custom', 'cashflow']:
            if pd.notna(row.get(field)):
                try:
                    val = float(str(row[field]).replace(',', '').replace('$', ''))
                    if val > 0:
                        return val
                except:
                    pass
        
        # Then try sde_at_close
        if pd.notna(row.get('sde_at_close')) and row['sde_at_close'] > 0:
            return row['sde_at_close']
        
        return None
    
    df_listings['asking_price'] = df_listings.apply(get_asking_price, axis=1)
    df_listings['sde'] = df_listings.apply(get_sde, axis=1)
    
    # Check how many have data
    has_asking = df_listings['asking_price'].notna().sum()
    has_sde = df_listings['sde'].notna().sum()
    has_both = ((df_listings['asking_price'].notna()) & (df_listings['sde'].notna())).sum()
    
    print(f"\nData availability:")
    print(f"  Has asking price: {has_asking}/{len(df_listings)}")
    print(f"  Has SDE/cashflow: {has_sde}/{len(df_listings)}")
    print(f"  Has both (can calculate multiple): {has_both}/{len(df_listings)}")
    
    # Calculate multiples
    df_listings['multiple'] = df_listings.apply(
        lambda row: row['asking_price'] / row['sde'] if pd.notna(row['sde']) and row['sde'] > 0 and pd.notna(row['asking_price']) and row['asking_price'] > 0 else None,
        axis=1
    )
    
    # Add SBA status
    def get_sba_status(listing_id):
        if listing_id in sba_ids:
            return 'yes'
        elif listing_id in non_sba_ids:
            return 'no'
        else:
            return 'unknown'
    
    df_listings['sba_status'] = df_listings['id'].apply(get_sba_status)
    
    # Filter for valid multiples (reasonable range: 0.5 to 10x)
    df_valid = df_listings[
        (df_listings['multiple'].notna()) & 
        (df_listings['multiple'] > 0.5) & 
        (df_listings['multiple'] < 10)
    ].copy()
    
    print(f"\nFiltered to {len(df_valid)} listings with valid multiples (0.5x - 10x)")
    
    # Separate by SBA status
    sba_multiples = df_valid[df_valid['sba_status'] == 'yes']['multiple'].values
    non_sba_multiples = df_valid[df_valid['sba_status'] == 'no']['multiple'].values
    unknown_multiples = df_valid[df_valid['sba_status'] == 'unknown']['multiple'].values
    
    # Calculate statistics
    results = {
        'timestamp': datetime.now().isoformat(),
        'data_source': 'listing_custom_fields',
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
        'unknown': {
            'count': len(unknown_multiples),
            'median': float(np.median(unknown_multiples)) if len(unknown_multiples) > 0 else None,
            'mean': float(np.mean(unknown_multiples)) if len(unknown_multiples) > 0 else None
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
    print("RESULTS: MEDIAN MULTIPLES ANALYSIS")
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
    
    print("\n📊 Unknown Status Deals:")
    print(f"   Count: {results['unknown']['count']} listings")
    if results['unknown']['median']:
        print(f"   Median Multiple: {results['unknown']['median']:.2f}x")
    
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
    output_file = 'median_multiples_custom_fields.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to {output_file}")
    
    # Also save detailed data to CSV for verification
    csv_file = 'median_multiples_custom_fields.csv'
    df_valid[['id', 'name', 'asking_price', 'sde', 'multiple', 'sba_status']].to_csv(csv_file, index=False)
    print(f"💾 Detailed data saved to {csv_file}")
    
    # Distribution analysis
    print("\n" + "=" * 80)
    print("DISTRIBUTION ANALYSIS:")
    print("=" * 80)
    
    # Multiple ranges
    ranges = [(0, 2), (2, 3), (3, 4), (4, 5), (5, 10)]
    
    for status, multiples in [('SBA', sba_multiples), ('Non-SBA', non_sba_multiples)]:
        if len(multiples) > 0:
            print(f"\n{status} Distribution:")
            for low, high in ranges:
                count = np.sum((multiples >= low) & (multiples < high))
                pct = (count / len(multiples)) * 100
                print(f"   {low}x-{high}x: {count} deals ({pct:.1f}%)")

if __name__ == "__main__":
    main()