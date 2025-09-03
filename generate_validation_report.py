#!/usr/bin/env python3
"""
Generate detailed validation report for SBA analysis.
Shows sample data, edge cases, and verification points.
"""

import pymysql
import pandas as pd
import json
from datetime import datetime

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

def generate_validation_report():
    """Generate comprehensive validation report."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'validation_checks': {},
        'sample_data': {},
        'edge_cases': {},
        'statistical_tests': {}
    }
    
    print("=" * 80)
    print("SBA ANALYSIS VALIDATION REPORT")
    print("=" * 80)
    
    # 1. Data Completeness Check
    print("\n1. DATA COMPLETENESS CHECKS")
    print("-" * 40)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_listings,
            SUM(CASE WHEN google_drive_link IS NOT NULL AND google_drive_link != '' THEN 1 ELSE 0 END) as with_drive_link,
            SUM(CASE WHEN closed_type IN (1,2) THEN 1 ELSE 0 END) as closed_listings,
            SUM(CASE WHEN closed_type = 1 THEN 1 ELSE 0 END) as sold,
            SUM(CASE WHEN closed_type = 2 THEN 1 ELSE 0 END) as lost
        FROM listings
        WHERE deleted_at IS NULL
    """)
    
    result = cursor.fetchone()
    print(f"Total listings (not deleted): {result['total_listings']}")
    print(f"With Google Drive links: {result['with_drive_link']}")
    print(f"Closed listings: {result['closed_listings']}")
    print(f"  - Sold: {result['sold']}")
    print(f"  - Lost: {result['lost']}")
    
    report['validation_checks']['data_completeness'] = result
    
    # 2. SBA Classification Samples
    print("\n2. SBA CLASSIFICATION EXAMPLES")
    print("-" * 40)
    
    # Sample SBA pre-qualified listings
    print("\nSBA Pre-qualified (title contains 'SBA'):")
    cursor.execute("""
        SELECT id, name, closed_type,
               CASE WHEN closed_type = 1 THEN 'sold' ELSE 'lost' END as status
        FROM listings
        WHERE deleted_at IS NULL
            AND google_drive_link IS NOT NULL
            AND google_drive_link != ''
            AND LOWER(name) LIKE '%sba%'
            AND LOWER(name) NOT LIKE '%not sba%'
            AND LOWER(name) NOT LIKE '%no sba%'
            AND closed_type IN (1,2)
        ORDER BY closed_type, id DESC
        LIMIT 5
    """)
    
    sba_samples = cursor.fetchall()
    for row in sba_samples:
        print(f"  ID {row['id']}: {row['name'][:60]}... [{row['status'].upper()}]")
    
    report['sample_data']['sba_prequalified'] = sba_samples
    
    # Sample SBA possible (has LOI with SBA)
    print("\nSBA Possible (LOI with SBA but not in title):")
    cursor.execute("""
        SELECT DISTINCT l.id, l.name, 
               CASE WHEN l.closed_type = 1 THEN 'sold' ELSE 'lost' END as status,
               loi_counts.sba_lois, loi_counts.total_lois
        FROM listings l
        JOIN (
            SELECT listing_id, 
                   SUM(has_sba) as sba_lois,
                   COUNT(*) as total_lois
            FROM lois
            GROUP BY listing_id
            HAVING SUM(has_sba) > 0
        ) loi_counts ON l.id = loi_counts.listing_id
        WHERE l.deleted_at IS NULL
            AND l.google_drive_link IS NOT NULL
            AND l.google_drive_link != ''
            AND l.closed_type IN (1,2)
            AND NOT (LOWER(l.name) LIKE '%sba%')
        LIMIT 5
    """)
    
    sba_possible_samples = cursor.fetchall()
    for row in sba_possible_samples:
        print(f"  ID {row['id']}: {row['name'][:50]}... [{row['status'].upper()}]")
        print(f"    -> {row['sba_lois']}/{row['total_lois']} LOIs with SBA")
    
    report['sample_data']['sba_possible'] = sba_possible_samples
    
    # 3. Edge Cases
    print("\n3. EDGE CASES & SPECIAL SCENARIOS")
    print("-" * 40)
    
    # Check for 'not sba' or 'no sba' mentions
    cursor.execute("""
        SELECT id, name
        FROM listings
        WHERE deleted_at IS NULL
            AND google_drive_link IS NOT NULL
            AND (LOWER(name) LIKE '%not sba%' OR LOWER(name) LIKE '%no sba%')
        LIMIT 3
    """)
    
    negative_sba = cursor.fetchall()
    if negative_sba:
        print("\nListings with negative SBA mentions (excluded from SBA classification):")
        for row in negative_sba:
            print(f"  ID {row['id']}: {row['name'][:60]}...")
    else:
        print("\nNo listings found with 'not sba' or 'no sba' in title")
    
    report['edge_cases']['negative_sba'] = negative_sba
    
    # 4. LOI Analysis
    print("\n4. LOI DATA ANALYSIS")
    print("-" * 40)
    
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT listing_id) as listings_with_lois,
            COUNT(*) as total_lois,
            SUM(has_sba) as sba_lois,
            AVG(has_sba) * 100 as pct_sba_lois
        FROM lois
    """)
    
    loi_stats = cursor.fetchone()
    print(f"Listings with LOIs: {loi_stats['listings_with_lois']}")
    print(f"Total LOIs: {loi_stats['total_lois']}")
    print(f"LOIs with SBA: {loi_stats['sba_lois']} ({loi_stats['pct_sba_lois']:.1f}%)")
    
    report['validation_checks']['loi_stats'] = loi_stats
    
    # 5. Winning LOI Analysis
    print("\n5. WINNING LOI ANALYSIS (Sold Listings)")
    print("-" * 40)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_sold,
            SUM(CASE WHEN loi.has_sba = 1 THEN 1 ELSE 0 END) as won_with_sba,
            SUM(CASE WHEN loi.has_sba = 0 THEN 1 ELSE 0 END) as won_without_sba,
            SUM(CASE WHEN loi.has_sba IS NULL THEN 1 ELSE 0 END) as no_loi_data
        FROM listings l
        LEFT JOIN closed_sale_reports csr ON l.id = csr.listing_id
        LEFT JOIN lois loi ON csr.loi_id = loi.id
        WHERE l.deleted_at IS NULL
            AND l.closed_type = 1
            AND l.google_drive_link IS NOT NULL
            AND l.google_drive_link != ''
    """)
    
    winning_loi_stats = cursor.fetchone()
    print(f"Total sold listings: {winning_loi_stats['total_sold']}")
    print(f"Won with SBA financing: {winning_loi_stats['won_with_sba']}")
    print(f"Won without SBA financing: {winning_loi_stats['won_without_sba']}")
    print(f"No LOI data available: {winning_loi_stats['no_loi_data']}")
    
    report['validation_checks']['winning_loi_stats'] = winning_loi_stats
    
    # 6. Financial Validation
    print("\n6. FINANCIAL DATA VALIDATION")
    print("-" * 40)
    
    cursor.execute("""
        SELECT 
            sba_class,
            COUNT(*) as count,
            AVG(closed_commission) as avg_commission,
            MIN(closed_commission) as min_commission,
            MAX(closed_commission) as max_commission,
            SUM(closed_commission) as total_commission
        FROM (
            SELECT 
                CASE 
                    WHEN LOWER(name) LIKE '%sba%' 
                         AND LOWER(name) NOT LIKE '%not sba%' 
                         AND LOWER(name) NOT LIKE '%no sba%' 
                    THEN 'sba_prequalified'
                    ELSE 'non_sba'
                END as sba_class,
                closed_commission
            FROM listings
            WHERE deleted_at IS NULL
                AND google_drive_link IS NOT NULL
                AND google_drive_link != ''
                AND closed_type = 1
                AND closed_commission IS NOT NULL
        ) classified
        GROUP BY sba_class
    """)
    
    financial_validation = cursor.fetchall()
    for row in financial_validation:
        print(f"\n{row['sba_class'].upper()}:")
        print(f"  Count: {row['count']}")
        print(f"  Avg Commission: ${row['avg_commission']:,.0f}")
        print(f"  Range: ${row['min_commission']:,.0f} - ${row['max_commission']:,.0f}")
        print(f"  Total: ${row['total_commission']:,.0f}")
    
    report['validation_checks']['financial'] = financial_validation
    
    # 7. Cross-validation with CIM files
    print("\n7. CIM FILE CROSS-VALIDATION")
    print("-" * 40)
    
    # Check how many listings have CIM files
    import os
    cim_dir = '/Users/markdaoust/Developer/ql_stats/cims'
    if os.path.exists(cim_dir):
        cim_files = [f for f in os.listdir(cim_dir) if f.endswith('.pdf')]
        
        # Extract listing IDs from filenames
        cim_listing_ids = set()
        for filename in cim_files:
            try:
                # Extract ID from filename pattern like "listing_12345_..."
                if 'listing_' in filename:
                    listing_id = filename.split('listing_')[1].split('_')[0]
                    cim_listing_ids.add(int(listing_id))
            except:
                pass
        
        print(f"CIM files found: {len(cim_files)}")
        print(f"Unique listing IDs in CIMs: {len(cim_listing_ids)}")
        
        if cim_listing_ids:
            # Check overlap with database
            id_list = ','.join(map(str, list(cim_listing_ids)[:10]))
            cursor.execute(f"""
                SELECT COUNT(*) as count
                FROM listings
                WHERE id IN ({id_list})
                    AND deleted_at IS NULL
                    AND google_drive_link IS NOT NULL
            """)
            overlap = cursor.fetchone()
            print(f"Sample overlap check (first 10): {overlap['count']} found in database")
    
    # Save detailed report
    with open('sba_validation_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print("\n" + "=" * 80)
    print("📁 Full validation report saved to sba_validation_report.json")
    
    cursor.close()
    conn.close()
    
    return report

if __name__ == "__main__":
    generate_validation_report()