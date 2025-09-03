import pandas as pd

# Load the CSV and check title analysis
df = pd.read_csv('launch_date_analysis_v2.csv')

# More comprehensive SBA title detection
sba_patterns = [
    r'\bSBA\b',
    r'SBA[- ]?(?:pre)?[- ]?quali',
    r'SBA[- ]?eligible',
    r'SBA[- ]?PQ\b'
]

import re
combined_pattern = '|'.join(sba_patterns)
df['sba_in_title'] = df['name'].str.contains(combined_pattern, case=False, na=False, regex=True)

# Count SBA advertised
sba_advertised = df['sba_in_title'].sum()
print(f'Total listings with SBA in title: {sba_advertised}')

# Check eligible deals that advertised
eligible_deals = df[df['sba_status'].isin(['yes', 'unknown'])]
eligible_count = len(eligible_deals)
eligible_advertised = eligible_deals['sba_in_title'].sum()
print(f'SBA eligible deals: {eligible_count}')
print(f'Eligible deals that advertised: {eligible_advertised}')
print(f'Percentage: {eligible_advertised/eligible_count*100:.1f}%')

# Verify inquiry impact for advertised vs not
sba_advertised_df = df[df['sba_in_title']]
not_advertised_df = df[~df['sba_in_title']]

median_advertised = sba_advertised_df['total_inquiries'].median()
median_not_advertised = not_advertised_df['total_inquiries'].median()

print(f'\nInquiry Impact:')
print(f'Advertised median inquiries: {median_advertised}')
print(f'Not advertised median inquiries: {median_not_advertised}')
print(f'Difference: {median_advertised - median_not_advertised}')
print(f'Percent increase: {(median_advertised - median_not_advertised)/median_not_advertised*100:.1f}%')

# Check within eligible deals only
eligible_advertised_df = eligible_deals[eligible_deals['sba_in_title']]
eligible_not_advertised_df = eligible_deals[~eligible_deals['sba_in_title']]

if len(eligible_advertised_df) > 0 and len(eligible_not_advertised_df) > 0:
    med_elig_adv = eligible_advertised_df['total_inquiries'].median()
    med_elig_not = eligible_not_advertised_df['total_inquiries'].median()
    print(f'\nWithin eligible deals only:')
    print(f'Advertised median: {med_elig_adv}')
    print(f'Not advertised median: {med_elig_not}')
    print(f'Percent increase: {(med_elig_adv - med_elig_not)/med_elig_not*100:.1f}%')
