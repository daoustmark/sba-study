#!/usr/bin/env python3
"""Check available columns in the listings table."""

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

# Get column information
cursor.execute("""
    SELECT COLUMN_NAME, DATA_TYPE 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'ac_prod' 
    AND TABLE_NAME = 'listings'
    AND (COLUMN_NAME LIKE '%price%' 
         OR COLUMN_NAME LIKE '%ask%' 
         OR COLUMN_NAME LIKE '%sde%'
         OR COLUMN_NAME LIKE '%revenue%'
         OR COLUMN_NAME LIKE '%value%'
         OR COLUMN_NAME LIKE '%sale%')
    ORDER BY COLUMN_NAME
""")

columns = cursor.fetchall()
print("Relevant columns in listings table:")
print("-" * 40)
for col in columns:
    print(f"{col['COLUMN_NAME']}: {col['DATA_TYPE']}")

# Check a sample record
cursor.execute("SELECT * FROM listings LIMIT 1")
sample = cursor.fetchone()
print("\nAll columns available:")
print("-" * 40)
for key in sample.keys():
    print(key)

cursor.close()
conn.close()