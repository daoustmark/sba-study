#!/usr/bin/env python3
"""
Integrated SBA analysis combining CIM data with database analysis.
Priority: CIM evidence > Title evidence > LOI evidence
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
    # Find the latest CIM results file
    results_files = list(Path('.').glob('cim_analysis_results_*.json'))
    if not results_files:
        print("No CIM analysis results found!")
        return {}
    
    latest_file = sorted(results_files)[-1]
    print(f"Loading CIM results from: {latest_file}")
    
    with open(latest_file, 'r') as f:
        cim_data = json.load(f)
    
    # Create a dict mapping listing_id to SBA status
    cim_map = {}
    for item in cim_data:
        if 'listing_id' in item:
            cim_map[item['listing_id']] = {
                'sba_status': item.get('sba_eligible', 'unknown'),
                'evidence': item.get('sba_evidence', ''),
                'asking_price': item.get('asking_price', 0),
                'sde': item.get('sde', 0)
            }
    
    return cim_map

def run_integrated_analysis(cim_map):
    """Run analysis integrating CIM data with database."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all closed listings with drive links
    query = """
    WITH listing_data AS (
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
            DATEDIFF(l.closed_at, l.created_at) as days_to_close
        FROM listings l
        WHERE l.deleted_at IS NULL
            AND l.google_drive_link IS NOT NULL
            AND l.google_drive_link != ''
            AND l.closed_type IN (1, 2)
    ),
    loi_data AS (
        SELECT 
            listing_id,
            MAX(has_sba) as any_loi_with_sba,
            COUNT(*) as total_lois,
            SUM(has_sba) as sba_lois
        FROM lois
        GROUP BY listing_id
    )
    SELECT 
        ld.*,
        loid.any_loi_with_sba,
        loid.total_lois,
        loid.sba_lois
    FROM listing_data ld
    LEFT JOIN loi_data loid ON ld.id = loid.listing_id
    """
    
    cursor.execute(query)
    listings = cursor.fetchall()
    
    # Classify each listing with priority: CIM > Title > LOI
    results = []
    for listing in listings:
        listing_id = listing['id']
        
        # Default classification
        sba_classification = 'non_sba'
        classification_source = 'default'
        
        # Priority 1: CIM evidence
        if listing_id in cim_map:
            cim_status = cim_map[listing_id]['sba_status']
            if cim_status == 'yes':
                sba_classification = 'sba_eligible'
                classification_source = 'cim'
            elif cim_status == 'no':
                sba_classification = 'not_eligible'
                classification_source = 'cim'
            elif cim_status == 'partial':
                sba_classification = 'sba_possible'
                classification_source = 'cim'
        
        # Priority 2: Title evidence (only if no CIM evidence)
        if classification_source == 'default':
            title_lower = listing['name'].lower()
            if 'sba' in title_lower and 'not sba' not in title_lower and 'no sba' not in title_lower:
                sba_classification = 'sba_likely'
                classification_source = 'title'
        
        # Priority 3: LOI evidence (only if no CIM or title evidence)
        if classification_source == 'default' and listing['any_loi_with_sba']:
            sba_classification = 'sba_possible'
            classification_source = 'loi'
        
        listing['sba_classification'] = sba_classification
        listing['classification_source'] = classification_source
        
        # Add CIM data if available
        if listing_id in cim_map:
            listing['cim_evidence'] = cim_map[listing_id]['evidence'][:100] if cim_map[listing_id]['evidence'] else 'N/A'
        else:
            listing['cim_evidence'] = 'No CIM processed'
        
        results.append(listing)
    
    cursor.close()
    conn.close()
    
    return results

def analyze_results(listings):
    """Analyze the integrated results."""
    
    df = pd.DataFrame(listings)
    
    print("\n" + "=" * 80)
    print("INTEGRATED SBA ANALYSIS RESULTS")
    print("=" * 80)
    print(f"Total Listings: {len(df)}")
    
    # Classification breakdown
    print("\n1. CLASSIFICATION BREAKDOWN")
    print("-" * 40)
    for classification in df['sba_classification'].unique():
        subset = df[df['sba_classification'] == classification]
        sold = len(subset[subset['status'] == 'sold'])
        total = len(subset)
        success_rate = (sold / total * 100) if total > 0 else 0
        
        print(f"\n{classification.upper()}:")
        print(f"  Total: {total}")
        print(f"  Sold: {sold}")
        print(f"  Lost: {total - sold}")
        print(f"  Success Rate: {success_rate:.1f}%")
    
    # Source breakdown
    print("\n2. CLASSIFICATION SOURCE")
    print("-" * 40)
    source_counts = df['classification_source'].value_counts()
    for source, count in source_counts.items():
        print(f"  {source}: {count} ({count/len(df)*100:.1f}%)")
    
    # Success rates comparison
    print("\n3. SUCCESS RATE COMPARISON")
    print("-" * 40)
    
    # SBA Eligible (from CIM) vs Others
    sba_eligible = df[df['sba_classification'] == 'sba_eligible']
    not_eligible = df[df['sba_classification'].isin(['not_eligible', 'non_sba'])]
    
    if len(sba_eligible) > 0:
        sba_success = len(sba_eligible[sba_eligible['status'] == 'sold']) / len(sba_eligible) * 100
        print(f"SBA Eligible (CIM verified): {sba_success:.1f}% success ({len(sba_eligible)} listings)")
    
    if len(not_eligible) > 0:
        non_sba_success = len(not_eligible[not_eligible['status'] == 'sold']) / len(not_eligible) * 100
        print(f"Not Eligible/Non-SBA: {non_sba_success:.1f}% success ({len(not_eligible)} listings)")
    
    # Financial analysis
    print("\n4. FINANCIAL IMPACT")
    print("-" * 40)
    
    for classification in ['sba_eligible', 'sba_likely', 'not_eligible', 'non_sba']:
        subset = df[(df['sba_classification'] == classification) & (df['status'] == 'sold')]
        if len(subset) > 0:
            avg_commission = subset['closed_commission'].mean()
            total_commission = subset['closed_commission'].sum()
            print(f"\n{classification.upper()}:")
            print(f"  Avg Commission: ${avg_commission:,.0f}")
            print(f"  Total Commission: ${total_commission:,.0f}")
    
    # Days to close
    print("\n5. DAYS TO CLOSE (Sold Only)")
    print("-" * 40)
    
    for classification in df['sba_classification'].unique():
        subset = df[(df['sba_classification'] == classification) & 
                   (df['status'] == 'sold') & 
                   (df['days_to_close'].notna())]
        if len(subset) > 0:
            median_days = subset['days_to_close'].median()
            print(f"  {classification}: {median_days:.0f} days (n={len(subset)})")
    
    # Save detailed results
    df.to_csv('integrated_sba_analysis.csv', index=False)
    
    # Create summary for dashboard
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_listings': len(df),
        'cim_processed': len(df[df['classification_source'] == 'cim']),
        'classifications': {},
        'success_rates': {},
        'financial_impact': {}
    }
    
    for classification in df['sba_classification'].unique():
        subset = df[df['sba_classification'] == classification]
        sold = len(subset[subset['status'] == 'sold'])
        total = len(subset)
        
        summary['classifications'][classification] = {
            'total': int(total),
            'sold': int(sold),
            'lost': int(total - sold)
        }
        
        if total > 0:
            summary['success_rates'][classification] = round(sold / total * 100, 1)
        
        sold_subset = subset[subset['status'] == 'sold']
        if len(sold_subset) > 0:
            summary['financial_impact'][classification] = {
                'avg_commission': int(sold_subset['closed_commission'].mean()),
                'total_commission': int(sold_subset['closed_commission'].sum())
            }
    
    with open('integrated_sba_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print("\n📁 Detailed results saved to integrated_sba_analysis.csv")
    print("📁 Summary saved to integrated_sba_summary.json")
    
    return summary

if __name__ == "__main__":
    # Load CIM results
    cim_map = load_cim_results()
    print(f"Loaded {len(cim_map)} CIM results")
    
    # Run integrated analysis
    listings = run_integrated_analysis(cim_map)
    
    # Analyze and save results
    summary = analyze_results(listings)
    
    print("\n✅ Integrated analysis complete!")