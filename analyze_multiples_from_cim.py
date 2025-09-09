#!/usr/bin/env python3
"""
Analyze median multiples (asking price / SDE) for SBA vs non-SBA deals using CIM data.
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime

def main():
    print("=" * 80)
    print("SBA vs Non-SBA Median Multiple Analysis (from CIM data)")
    print("=" * 80)
    print()
    
    # Load CIM analysis data
    print("Loading CIM analysis data...")
    with open('cim_analysis_results_20250829_154455.json', 'r') as f:
        cim_data = json.load(f)
    
    # Convert to DataFrame
    df = pd.DataFrame(cim_data)
    
    # Clean data - convert to numeric and filter valid values
    df['asking_price'] = pd.to_numeric(df['asking_price'], errors='coerce')
    df['sde'] = pd.to_numeric(df['sde'], errors='coerce')
    
    # Calculate multiples
    df['multiple'] = df['asking_price'] / df['sde']
    
    # Filter for valid multiples (reasonable range: 0.5 to 10x)
    df_valid = df[
        (df['multiple'].notna()) & 
        (df['multiple'] > 0.5) & 
        (df['multiple'] < 10) &
        (df['asking_price'] > 0) &
        (df['sde'] > 0)
    ].copy()
    
    print(f"Found {len(df)} total CIM records")
    print(f"Filtered to {len(df_valid)} listings with valid multiples (0.5x - 10x)")
    
    # Separate by SBA eligibility
    sba_eligible = df_valid[df_valid['sba_eligible'] == 'yes']
    non_sba = df_valid[df_valid['sba_eligible'] == 'no']
    
    print(f"\nSBA Eligible: {len(sba_eligible)} listings")
    print(f"Non-SBA: {len(non_sba)} listings")
    
    # Calculate statistics
    results = {
        'timestamp': datetime.now().isoformat(),
        'data_source': 'CIM Analysis Results',
        'sba_eligible': {
            'count': len(sba_eligible),
            'median': float(sba_eligible['multiple'].median()) if len(sba_eligible) > 0 else None,
            'mean': float(sba_eligible['multiple'].mean()) if len(sba_eligible) > 0 else None,
            'std': float(sba_eligible['multiple'].std()) if len(sba_eligible) > 0 else None,
            'min': float(sba_eligible['multiple'].min()) if len(sba_eligible) > 0 else None,
            'max': float(sba_eligible['multiple'].max()) if len(sba_eligible) > 0 else None,
            'q25': float(sba_eligible['multiple'].quantile(0.25)) if len(sba_eligible) > 0 else None,
            'q75': float(sba_eligible['multiple'].quantile(0.75)) if len(sba_eligible) > 0 else None
        },
        'non_sba': {
            'count': len(non_sba),
            'median': float(non_sba['multiple'].median()) if len(non_sba) > 0 else None,
            'mean': float(non_sba['multiple'].mean()) if len(non_sba) > 0 else None,
            'std': float(non_sba['multiple'].std()) if len(non_sba) > 0 else None,
            'min': float(non_sba['multiple'].min()) if len(non_sba) > 0 else None,
            'max': float(non_sba['multiple'].max()) if len(non_sba) > 0 else None,
            'q25': float(non_sba['multiple'].quantile(0.25)) if len(non_sba) > 0 else None,
            'q75': float(non_sba['multiple'].quantile(0.75)) if len(non_sba) > 0 else None
        }
    }
    
    # Calculate differences
    if results['sba_eligible']['median'] and results['non_sba']['median']:
        median_diff = results['sba_eligible']['median'] - results['non_sba']['median']
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
    
    print("\n📊 SBA Eligible Deals:")
    print(f"   Count: {results['sba_eligible']['count']} listings")
    if results['sba_eligible']['median']:
        print(f"   Median Multiple: {results['sba_eligible']['median']:.2f}x")
        print(f"   Mean Multiple: {results['sba_eligible']['mean']:.2f}x")
        print(f"   Range: {results['sba_eligible']['min']:.2f}x - {results['sba_eligible']['max']:.2f}x")
        print(f"   IQR: {results['sba_eligible']['q25']:.2f}x - {results['sba_eligible']['q75']:.2f}x")
    
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
            print(f"✅ SBA eligible deals have HIGHER median multiples")
            print(f"   Difference: +{results['comparison']['median_difference']:.2f}x")
            print(f"   Percentage: +{results['comparison']['median_difference_percent']:.1f}%")
        else:
            print(f"⚠️  SBA eligible deals have LOWER median multiples")
            print(f"   Difference: {results['comparison']['median_difference']:.2f}x")
            print(f"   Percentage: {results['comparison']['median_difference_percent']:.1f}%")
    
    # Save results to JSON
    output_file = 'median_multiples_cim_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to {output_file}")
    
    # Also save detailed data to CSV for verification
    csv_file = 'median_multiples_cim_details.csv'
    df_valid[['listing_id', 'asking_price', 'sde', 'multiple', 'sba_eligible']].to_csv(csv_file, index=False)
    print(f"💾 Detailed data saved to {csv_file}")
    
    # Distribution analysis
    print("\n" + "=" * 80)
    print("DISTRIBUTION ANALYSIS:")
    print("=" * 80)
    
    # Multiple ranges
    ranges = [(0, 2), (2, 3), (3, 4), (4, 5), (5, 10)]
    
    for status, data in [('SBA Eligible', sba_eligible), ('Non-SBA', non_sba)]:
        if len(data) > 0:
            multiples = data['multiple'].values
            print(f"\n{status} Distribution:")
            for low, high in ranges:
                count = np.sum((multiples >= low) & (multiples < high))
                pct = (count / len(multiples)) * 100
                print(f"   {low}x-{high}x: {count} deals ({pct:.1f}%)")
    
    # Top and bottom listings by multiple
    print("\n" + "=" * 80)
    print("SAMPLE LISTINGS:")
    print("=" * 80)
    
    if len(sba_eligible) > 0:
        print("\nTop 5 SBA Eligible by Multiple:")
        top_sba = sba_eligible.nlargest(5, 'multiple')[['listing_id', 'asking_price', 'sde', 'multiple']]
        for _, row in top_sba.iterrows():
            print(f"   ID {row['listing_id']}: {row['multiple']:.2f}x (${row['asking_price']:,.0f} / ${row['sde']:,.0f})")
    
    if len(non_sba) > 0:
        print("\nTop 5 Non-SBA by Multiple:")
        top_non = non_sba.nlargest(5, 'multiple')[['listing_id', 'asking_price', 'sde', 'multiple']]
        for _, row in top_non.iterrows():
            print(f"   ID {row['listing_id']}: {row['multiple']:.2f}x (${row['asking_price']:,.0f} / ${row['sde']:,.0f})")

if __name__ == "__main__":
    main()