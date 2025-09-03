#!/usr/bin/env python3
"""
Check why only 178 of 251 CIM listings are in the analysis.
"""

import pymysql
import json
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

# Load CIM results
results_files = list(Path('.').glob('cim_analysis_results_*.json'))
latest_file = sorted(results_files)[-1]

with open(latest_file, 'r') as f:
    cim_data = json.load(f)

listing_ids = [item['listing_id'] for item in cim_data if 'listing_id' in item]
print(f"Total CIM listings: {len(listing_ids)}")

# Check database status
conn = get_db_connection()
cursor = conn.cursor()

id_list = ','.join(map(str, listing_ids))

# Check closed_type distribution
query = f"""
SELECT 
    closed_type,
    COUNT(*) as count
FROM listings
WHERE id IN ({id_list})
GROUP BY closed_type
"""

cursor.execute(query)
results = cursor.fetchall()

print("\nClosed Type Distribution:")
print("-" * 40)
for row in results:
    closed_type = row['closed_type']
    if closed_type == 0:
        status = "Active"
    elif closed_type == 1:
        status = "Sold"
    elif closed_type == 2:
        status = "Lost"
    elif closed_type is None:
        status = "NULL"
    else:
        status = f"Unknown ({closed_type})"
    
    print(f"{status}: {row['count']} listings")

# Check if any are missing from database
query = f"""
SELECT COUNT(*) as found_count
FROM listings
WHERE id IN ({id_list})
"""

cursor.execute(query)
result = cursor.fetchone()
found = result['found_count']
missing = len(listing_ids) - found

print(f"\nDatabase Coverage:")
print(f"  Found in database: {found}")
print(f"  Missing from database: {missing}")

if missing > 0:
    # Find which ones are missing
    query = f"""
    SELECT id FROM listings WHERE id IN ({id_list})
    """
    cursor.execute(query)
    found_ids = set(row['id'] for row in cursor.fetchall())
    all_ids = set(listing_ids)
    missing_ids = all_ids - found_ids
    print(f"  Missing IDs: {list(missing_ids)[:10]}...")

# Check for deleted listings
query = f"""
SELECT 
    COUNT(*) as deleted_count
FROM listings
WHERE id IN ({id_list})
    AND deleted_at IS NOT NULL
"""

cursor.execute(query)
result = cursor.fetchone()
print(f"  Deleted listings: {result['deleted_count']}")

cursor.close()
conn.close()