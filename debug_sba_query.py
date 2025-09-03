#!/usr/bin/env python3
"""
Debug SBA query to understand data issues.
"""

import pymysql
import pandas as pd

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

def debug_query():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First, check basic listing counts
    print("1. Basic listing counts:")
    cursor.execute("""
        SELECT 
            closed_type,
            COUNT(*) as count
        FROM listings 
        WHERE deleted_at IS NULL
            AND google_drive_link IS NOT NULL
            AND google_drive_link != ''
        GROUP BY closed_type
    """)
    for row in cursor.fetchall():
        print(f"  closed_type={row['closed_type']}: {row['count']}")
    
    # Check if we have any SBA in titles
    print("\n2. SBA in titles:")
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN LOWER(name) LIKE '%sba%' THEN 1 ELSE 0 END) as with_sba,
            SUM(CASE WHEN closed_type = 1 THEN 1 ELSE 0 END) as sold,
            SUM(CASE WHEN closed_type = 2 THEN 1 ELSE 0 END) as lost
        FROM listings 
        WHERE deleted_at IS NULL
            AND google_drive_link IS NOT NULL
            AND google_drive_link != ''
            AND closed_type IN (1, 2)
    """)
    result = cursor.fetchone()
    print(f"  Total closed: {result['total']}")
    print(f"  With SBA in title: {result['with_sba']}")
    print(f"  Sold (closed_type=1): {result['sold']}")
    print(f"  Lost (closed_type=2): {result['lost']}")
    
    # Check LOI table
    print("\n3. LOI table check:")
    cursor.execute("""
        SELECT 
            COUNT(*) as total_lois,
            SUM(has_sba) as sba_lois,
            COUNT(DISTINCT listing_id) as listings_with_lois
        FROM lois
    """)
    result = cursor.fetchone()
    print(f"  Total LOIs: {result['total_lois']}")
    print(f"  SBA LOIs: {result['sba_lois']}")
    print(f"  Listings with LOIs: {result['listings_with_lois']}")
    
    # Sample some actual data
    print("\n4. Sample listings with SBA in title:")
    cursor.execute("""
        SELECT 
            id,
            name,
            closed_type,
            CASE 
                WHEN closed_type = 1 THEN 'sold'
                WHEN closed_type = 2 THEN 'lost'
                ELSE 'active'
            END as status
        FROM listings 
        WHERE deleted_at IS NULL
            AND google_drive_link IS NOT NULL
            AND google_drive_link != ''
            AND LOWER(name) LIKE '%sba%'
            AND closed_type IN (1, 2)
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  ID {row['id']}: {row['name'][:50]}... - {row['status']}")
    
    # Check the full query result
    print("\n5. Testing the classification logic:")
    cursor.execute("""
        SELECT 
            CASE 
                WHEN LOWER(l.name) LIKE '%sba%' 
                     AND LOWER(l.name) NOT LIKE '%not sba%' 
                     AND LOWER(l.name) NOT LIKE '%no sba%' 
                THEN 'sba_prequalified'
                WHEN EXISTS(SELECT 1 FROM lois WHERE listing_id = l.id AND has_sba = 1) THEN 'sba_possible'
                ELSE 'non_sba'
            END as sba_classification,
            COUNT(*) as count,
            SUM(CASE WHEN l.closed_type = 1 THEN 1 ELSE 0 END) as sold,
            SUM(CASE WHEN l.closed_type = 2 THEN 1 ELSE 0 END) as lost
        FROM listings l
        WHERE l.deleted_at IS NULL
            AND l.google_drive_link IS NOT NULL
            AND l.google_drive_link != ''
            AND l.closed_type IN (1, 2)
        GROUP BY sba_classification
    """)
    for row in cursor.fetchall():
        success_rate = (row['sold'] / row['count'] * 100) if row['count'] > 0 else 0
        print(f"  {row['sba_classification']}: {row['count']} total, {row['sold']} sold, {row['lost']} lost ({success_rate:.1f}% success)")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    debug_query()