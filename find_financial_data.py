#!/usr/bin/env python3
"""Find all sources of financial data in the database."""

import pymysql

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

conn = get_db_connection()
cursor = conn.cursor()

print("=" * 60)
print("CHECKING FOR FINANCIAL DATA SOURCES")
print("=" * 60)

# Check what tables exist
cursor.execute("""
    SELECT TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_SCHEMA = 'ac_prod' 
    AND (TABLE_NAME LIKE '%financ%' 
         OR TABLE_NAME LIKE '%sde%'
         OR TABLE_NAME LIKE '%revenue%'
         OR TABLE_NAME LIKE '%pls%'
         OR TABLE_NAME LIKE '%valuation%')
""")
tables = cursor.fetchall()
print("\nRelevant tables found:")
for t in tables:
    print(f"  - {t['TABLE_NAME']}")

# Check PLS tables which often contain financial data
cursor.execute("""
    SELECT TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_SCHEMA = 'ac_prod' 
    AND TABLE_NAME LIKE '%pls%'
""")
pls_tables = cursor.fetchall()
print("\nPLS-related tables:")
for t in pls_tables:
    print(f"  - {t['TABLE_NAME']}")

# Check listings table for how many have financial data
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN asking_at_close > 0 THEN 1 ELSE 0 END) as has_asking,
        SUM(CASE WHEN sde_at_close > 0 THEN 1 ELSE 0 END) as has_sde,
        SUM(CASE WHEN revenue_at_close > 0 THEN 1 ELSE 0 END) as has_revenue,
        SUM(CASE WHEN capsule_expected_value > 0 THEN 1 ELSE 0 END) as has_expected_value,
        SUM(CASE WHEN asking_at_close > 0 AND sde_at_close > 0 THEN 1 ELSE 0 END) as has_both_closed,
        SUM(CASE WHEN (asking_at_close > 0 OR capsule_expected_value > 0) 
            AND sde_at_close > 0 THEN 1 ELSE 0 END) as has_multiples_data
    FROM listings
""")
stats = cursor.fetchone()
print("\nFinancial data availability in listings table:")
print(f"  Total listings: {stats['total']}")
print(f"  Has asking_at_close: {stats['has_asking']}")
print(f"  Has sde_at_close: {stats['has_sde']}")
print(f"  Has revenue_at_close: {stats['has_revenue']}")
print(f"  Has capsule_expected_value: {stats['has_expected_value']}")
print(f"  Has both asking and SDE (closed): {stats['has_both_closed']}")
print(f"  Has data for multiples calculation: {stats['has_multiples_data']}")

# Check if there's a PLS data table
cursor.execute("SHOW TABLES LIKE '%pls%'")
if cursor.fetchone():
    cursor.execute("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'ac_prod' 
        AND TABLE_NAME LIKE '%pls%'
        LIMIT 20
    """)
    cols = cursor.fetchall()
    if cols:
        print("\nPLS table columns found:")
        for c in cols:
            print(f"  - {c['COLUMN_NAME']}")

cursor.close()
conn.close()