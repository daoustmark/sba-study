#!/usr/bin/env python3
"""Check data coverage across different sources."""

import pandas as pd
import json

# Load the main dataset
df = pd.read_csv('launch_date_analysis.csv')
print("=" * 60)
print("FULL DATASET (launch_date_analysis.csv)")
print("=" * 60)
print(f"Total listings: {len(df)}")
print("\nSBA Status breakdown:")
print(df['sba_status'].value_counts())
print(f"\nSold listings only:")
sold_df = df[df['status'] == 'sold']
print(f"Total sold: {len(sold_df)}")
print(sold_df['sba_status'].value_counts())

# Load CIM analysis
with open('cim_analysis_results_20250829_154455.json') as f:
    cim_data = json.load(f)

print("\n" + "=" * 60)
print("CIM ANALYSIS DATA (with financials)")
print("=" * 60)
print(f"Total CIMs analyzed: {len(cim_data)}")

# Count by SBA eligibility
sba_yes = sum(1 for d in cim_data if d['sba_eligible'] == 'yes')
sba_no = sum(1 for d in cim_data if d['sba_eligible'] == 'no')
print(f"SBA eligible: {sba_yes}")
print(f"Non-SBA: {sba_no}")

# Check how many have valid financials
valid_financials = 0
for record in cim_data:
    try:
        asking = float(record.get('asking_price', 0))
        sde = float(record.get('sde', 0))
        if asking > 0 and sde > 0:
            multiple = asking / sde
            if 0.5 <= multiple <= 10:
                valid_financials += 1
    except:
        pass

print(f"With valid multiples (0.5x-10x): {valid_financials}")

# Check dashboard JSON
with open('dashboard_listings_full.json') as f:
    dashboard_data = json.load(f)

print("\n" + "=" * 60)
print("DASHBOARD DATA")
print("=" * 60)
print(f"Total listings: {len(dashboard_data)}")
sba_dashboard = sum(1 for d in dashboard_data if d['sba_status'] == 'yes')
print(f"SBA pre-qualified: {sba_dashboard}")

# Cross-reference
cim_ids = set(d['listing_id'] for d in cim_data)
dashboard_ids = set(d['id'] for d in dashboard_data)
csv_ids = set(df['id'].tolist())

print("\n" + "=" * 60)
print("DATA COVERAGE ANALYSIS")
print("=" * 60)
print(f"Listings in CSV: {len(csv_ids)}")
print(f"Listings in Dashboard JSON: {len(dashboard_ids)}")
print(f"Listings with CIM analysis: {len(cim_ids)}")
print(f"CIMs with valid financials for multiples: {valid_financials}")

# Why only 58 SBA deals?
print("\n" + "=" * 60)
print("WHY ONLY 58 SBA DEALS IN MULTIPLES ANALYSIS?")
print("=" * 60)
print("1. We need BOTH asking price AND SDE to calculate multiples")
print("2. CIM analysis extracted financials from 251 listings")
print(f"3. Of these, {sba_yes} were SBA eligible")
print(f"4. After filtering outliers (0.5x-10x range), we had {valid_financials} total")
print("5. This gave us 58 SBA and 147 non-SBA deals with valid multiples")
print("\nNote: The full dataset has more SBA deals, but many lack")
print("      the financial data needed for multiple calculations")