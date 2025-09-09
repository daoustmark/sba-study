#!/usr/bin/env python3
"""Check the structure of listing_custom_fields table."""

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

# Check if table exists
cursor.execute("SHOW TABLES LIKE '%custom%'")
tables = cursor.fetchall()
print("Tables with 'custom' in name:")
for t in tables:
    print(f"  - {list(t.values())[0]}")

# Check columns in listing_custom_fields
cursor.execute("""
    SELECT COLUMN_NAME, DATA_TYPE 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'ac_prod' 
    AND TABLE_NAME = 'listing_custom_fields'
    ORDER BY ORDINAL_POSITION
""")
columns = cursor.fetchall()
print("\nColumns in listing_custom_fields:")
for col in columns:
    print(f"  {col['COLUMN_NAME']}: {col['DATA_TYPE']}")

# Check sample data
cursor.execute("""
    SELECT * FROM listing_custom_fields 
    LIMIT 5
""")
samples = cursor.fetchall()
print("\nSample records:")
for i, record in enumerate(samples, 1):
    print(f"\nRecord {i}:")
    for key, value in record.items():
        print(f"  {key}: {value}")

cursor.close()
conn.close()