#!/usr/bin/env python3
"""
Generate JSON data for dashboard modal popups with actual listing details.
"""

import pandas as pd
import json
from datetime import datetime
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

# Load the launch date analysis data
df = pd.read_csv('launch_date_analysis.csv')

# Get commission data from database
conn = get_db_connection()
cursor = conn.cursor()

listing_ids = df['id'].tolist()
id_list = ','.join(map(str, listing_ids))

query = f"""
SELECT 
    id,
    closed_commission
FROM listings
WHERE id IN ({id_list})
"""

cursor.execute(query)
commission_data = cursor.fetchall()
cursor.close()
conn.close()

# Create commission lookup
commission_map = {row['id']: row['closed_commission'] for row in commission_data}

# Add commission to dataframe
df['closed_commission'] = df['id'].map(commission_map)

# Prepare data for each category
categories = {
    'sba-sold': df[(df['sba_status'] == 'yes') & (df['status'] == 'sold')],
    'non-sba-sold': df[(df['sba_status'] == 'no') & (df['status'] == 'sold')],
    'sba-lost': df[(df['sba_status'] == 'yes') & (df['status'] == 'lost')],
    'non-sba-lost': df[(df['sba_status'] == 'no') & (df['status'] == 'lost')],
    'unknown-sold': df[(df['sba_status'] == 'unknown') & (df['status'] == 'sold')],
    'unknown-lost': df[(df['sba_status'] == 'unknown') & (df['status'] == 'lost')]
}

listing_data = {}

for category, data in categories.items():
    if len(data) > 0:
        # Sort by days_on_market
        data = data.sort_values('days_on_market', ascending=True)
        
        listings = []
        for _, row in data.iterrows():
            listing = {
                'id': int(row['id']),
                'name': row['name'][:50] + '...' if len(row['name']) > 50 else row['name'],
                'days': int(row['days_on_market']) if pd.notna(row['days_on_market']) else 0,
                'launch': str(row['launch_date'])[:10] if pd.notna(row['launch_date']) else 'N/A',
                'close': str(row['closed_at'])[:10] if pd.notna(row['closed_at']) else 'N/A',
                'commission': float(row.get('closed_commission', 0)) if pd.notna(row.get('closed_commission', 0)) else 0
            }
            listings.append(listing)
        
        listing_data[category] = listings

# Calculate summary statistics for each category
summary_stats = {}
for category, data in categories.items():
    if len(data) > 0:
        summary_stats[category] = {
            'count': len(data),
            'median': int(data['days_on_market'].median()) if data['days_on_market'].notna().any() else 0,
            'mean': int(data['days_on_market'].mean()) if data['days_on_market'].notna().any() else 0
        }
    else:
        summary_stats[category] = {
            'count': 0,
            'median': 0,
            'mean': 0
        }

# Generate JavaScript for dashboard
js_output = f"""
// Generated listing data from launch_date_analysis.csv
// Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}

const listingData = {json.dumps(listing_data, indent=2)};

// Summary statistics
const summaryStats = {json.dumps(summary_stats, indent=2)};
"""

# Save to JavaScript file
with open('listing_data.js', 'w') as f:
    f.write(js_output)

print(f"Generated listing_data.js with {sum(len(v) for v in listing_data.values())} total listings")

# Also generate a summary report
print("\n" + "=" * 60)
print("LISTING DATA SUMMARY")
print("=" * 60)

for category, data in categories.items():
    if len(data) > 0:
        print(f"\n{category.upper()}:")
        print(f"  Count: {len(data)}")
        print(f"  Median days: {data['days_on_market'].median():.0f}")
        print(f"  Mean days: {data['days_on_market'].mean():.0f}")
        print(f"  Range: {data['days_on_market'].min():.0f} - {data['days_on_market'].max():.0f}")
        
        # Show top 3 listings
        print("  Top 3 listings:")
        for i, (_, row) in enumerate(data.head(3).iterrows()):
            print(f"    {i+1}. ID {row['id']}: {row['name'][:40]}... ({row['days_on_market']:.0f} days)")