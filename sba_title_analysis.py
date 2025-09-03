#!/usr/bin/env python3
"""
Analyze impact of SBA advertising in listing titles on inquiry rates.
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import re
from datetime import datetime

def analyze_sba_titles():
    """
    Analyze which listings advertised SBA in their titles and the impact on inquiries.
    """
    
    # Load data
    print("Loading data...")
    launch_df = pd.read_csv('launch_date_analysis_v2.csv')
    sba_usage_df = pd.read_csv('sba_actual_usage_analysis.csv')
    
    # Merge datasets
    df = pd.merge(
        launch_df,
        sba_usage_df[['id', 'winning_loi_sba', 'has_sba_loi']],
        on='id',
        how='left'
    )
    
    print("\n" + "="*80)
    print("SBA TITLE ADVERTISING ANALYSIS")
    print("="*80)
    
    # 1. IDENTIFY LISTINGS WITH SBA IN TITLE
    print("\n1. IDENTIFYING SBA ADVERTISING IN TITLES")
    print("-"*50)
    
    # Create patterns to identify SBA mentions in titles
    sba_patterns = [
        r'\bSBA\b',
        r'SBA[- ]?(?:pre)?[- ]?quali',
        r'SBA[- ]?eligible',
        r'SBA[- ]?approved',
        r'SBA[- ]?PQ\b',
        r'Small Business Administration',
        r'Financing Available',  # Sometimes used as proxy
    ]
    
    # Combine patterns
    sba_pattern = '|'.join(sba_patterns)
    
    # Check each listing name
    df['sba_in_title'] = df['name'].str.contains(sba_pattern, case=False, na=False)
    
    # Count results
    total_listings = len(df)
    sba_advertised = df['sba_in_title'].sum()
    
    print(f"Total listings: {total_listings}")
    print(f"Listings advertising SBA in title: {sba_advertised} ({sba_advertised/total_listings*100:.1f}%)")
    
    # Cross-check with our SBA status classification
    print("\nCross-validation with CIM analysis:")
    
    # Create confusion matrix
    sba_eligible_cim = df['sba_status'] == 'yes'
    sba_advertised_title = df['sba_in_title']
    
    both = (sba_eligible_cim & sba_advertised_title).sum()
    cim_only = (sba_eligible_cim & ~sba_advertised_title).sum()
    title_only = (~sba_eligible_cim & sba_advertised_title).sum()
    neither = (~sba_eligible_cim & ~sba_advertised_title).sum()
    
    print(f"  Both CIM + Title: {both}")
    print(f"  CIM says yes, title doesn't mention: {cim_only}")
    print(f"  Title mentions, CIM says no: {title_only}")
    print(f"  Neither: {neither}")
    
    # Show some examples of each category
    print("\nExamples of listings with SBA in title:")
    sba_titles = df[df['sba_in_title'] == True]['name'].head(5)
    for i, title in enumerate(sba_titles, 1):
        print(f"  {i}. {title[:80]}...")
    
    print("\nExamples of SBA-eligible (per CIM) WITHOUT title mention:")
    hidden_sba = df[(df['sba_status'] == 'yes') & (df['sba_in_title'] == False)]['name'].head(5)
    for i, title in enumerate(hidden_sba, 1):
        print(f"  {i}. {title[:80]}...")
    
    # 2. INQUIRY ANALYSIS - ADVERTISED VS NOT
    print("\n2. INQUIRY IMPACT OF SBA ADVERTISING")
    print("-"*50)
    
    # Compare inquiry rates
    advertised = df[df['sba_in_title'] == True]
    not_advertised = df[df['sba_in_title'] == False]
    
    print(f"\nListings WITH SBA in title (n={len(advertised)}):")
    print(f"  Median inquiries: {advertised['total_inquiries'].median():.0f}")
    print(f"  Mean inquiries: {advertised['total_inquiries'].mean():.1f}")
    print(f"  Range: {advertised['total_inquiries'].min()}-{advertised['total_inquiries'].max()}")
    
    print(f"\nListings WITHOUT SBA in title (n={len(not_advertised)}):")
    print(f"  Median inquiries: {not_advertised['total_inquiries'].median():.0f}")
    print(f"  Mean inquiries: {not_advertised['total_inquiries'].mean():.1f}")
    print(f"  Range: {not_advertised['total_inquiries'].min()}-{not_advertised['total_inquiries'].max()}")
    
    # Statistical test
    if len(advertised) > 0 and len(not_advertised) > 0:
        statistic, pvalue = stats.mannwhitneyu(
            advertised['total_inquiries'].dropna(),
            not_advertised['total_inquiries'].dropna(),
            alternative='two-sided'
        )
        print(f"\nStatistical significance (Mann-Whitney U):")
        print(f"  P-value: {pvalue:.4f}")
        print(f"  Significant: {'Yes' if pvalue < 0.05 else 'No'}")
    
    # 3. CONTROLLED COMPARISON - SBA ELIGIBLE ONLY
    print("\n3. CONTROLLED COMPARISON (SBA-eligible deals only)")
    print("-"*50)
    
    # Look only at SBA-eligible deals
    sba_eligible = df[df['sba_status'] == 'yes']
    
    advertised_eligible = sba_eligible[sba_eligible['sba_in_title'] == True]
    not_advertised_eligible = sba_eligible[sba_eligible['sba_in_title'] == False]
    
    print(f"\nAmong {len(sba_eligible)} SBA-eligible deals:")
    print(f"  Advertised SBA: {len(advertised_eligible)} ({len(advertised_eligible)/len(sba_eligible)*100:.1f}%)")
    print(f"  Didn't advertise: {len(not_advertised_eligible)} ({len(not_advertised_eligible)/len(sba_eligible)*100:.1f}%)")
    
    if len(advertised_eligible) > 0 and len(not_advertised_eligible) > 0:
        print(f"\nInquiry comparison (SBA-eligible only):")
        print(f"  Advertised: {advertised_eligible['total_inquiries'].median():.0f} median inquiries")
        print(f"  Not advertised: {not_advertised_eligible['total_inquiries'].median():.0f} median inquiries")
        
        diff = advertised_eligible['total_inquiries'].median() - not_advertised_eligible['total_inquiries'].median()
        pct_diff = (diff / not_advertised_eligible['total_inquiries'].median() * 100)
        print(f"  Difference: {diff:+.0f} ({pct_diff:+.1f}%)")
    
    # 4. OUTCOME ANALYSIS
    print("\n4. OUTCOME ANALYSIS BY TITLE ADVERTISING")
    print("-"*50)
    
    # Success rates
    for status in ['sold', 'lost']:
        advertised_status = advertised[advertised['status'] == status]
        not_advertised_status = not_advertised[not_advertised['status'] == status]
        
        if status == 'sold':
            advertised_rate = len(advertised_status) / len(advertised) * 100 if len(advertised) > 0 else 0
            not_advertised_rate = len(not_advertised_status) / len(not_advertised) * 100 if len(not_advertised) > 0 else 0
            
            print(f"\nSuccess rates:")
            print(f"  SBA advertised: {advertised_rate:.1f}% ({len(advertised_status)}/{len(advertised)})")
            print(f"  Not advertised: {not_advertised_rate:.1f}% ({len(not_advertised_status)}/{len(not_advertised)})")
    
    # Time metrics for sold deals
    advertised_sold = advertised[advertised['status'] == 'sold']
    not_advertised_sold = not_advertised[not_advertised['status'] == 'sold']
    
    print("\nTime metrics (sold deals only):")
    
    metrics = ['days_on_market', 'days_under_loi', 'days_to_loi']
    for metric in metrics:
        if len(advertised_sold) > 0 and len(not_advertised_sold) > 0:
            adv_median = advertised_sold[metric].median()
            not_adv_median = not_advertised_sold[metric].median()
            diff = adv_median - not_adv_median
            
            print(f"  {metric}:")
            print(f"    Advertised: {adv_median:.0f} days")
            print(f"    Not advertised: {not_adv_median:.0f} days")
            print(f"    Difference: {diff:+.0f} days")
    
    # 5. DEAL SIZE ANALYSIS
    print("\n5. DEAL SIZE AND SBA ADVERTISING")
    print("-"*50)
    
    # Check if larger deals are more likely to advertise SBA
    df['estimated_deal_size'] = df['closed_commission'] / 0.10
    
    deals_with_size = df[df['closed_commission'].notna() & (df['closed_commission'] > 0)]
    
    # Group by size ranges
    size_ranges = [
        (0, 500000, '<$500K'),
        (500000, 1000000, '$500K-1M'),
        (1000000, 2000000, '$1-2M'),
        (2000000, float('inf'), '>$2M')
    ]
    
    print("\nSBA advertising by deal size:")
    for min_size, max_size, label in size_ranges:
        range_df = deals_with_size[
            (deals_with_size['estimated_deal_size'] >= min_size) & 
            (deals_with_size['estimated_deal_size'] < max_size)
        ]
        if len(range_df) > 0:
            advertised_count = range_df['sba_in_title'].sum()
            total_count = len(range_df)
            pct = advertised_count / total_count * 100
            
            # Also check inquiries
            advertised_inq = range_df[range_df['sba_in_title'] == True]['total_inquiries'].median()
            not_adv_inq = range_df[range_df['sba_in_title'] == False]['total_inquiries'].median()
            
            print(f"  {label}: {advertised_count}/{total_count} ({pct:.1f}%) advertised")
            if pd.notna(advertised_inq) and pd.notna(not_adv_inq):
                print(f"    Inquiries - Advertised: {advertised_inq:.0f}, Not advertised: {not_adv_inq:.0f}")
    
    # 6. BUYER BEHAVIOR ANALYSIS
    print("\n6. BUYER BEHAVIOR INSIGHTS")
    print("-"*50)
    
    # For SBA-advertised deals that sold, did they use SBA?
    advertised_sold_sba = advertised_sold[advertised_sold['winning_loi_sba'] == True]
    advertised_sold_no_sba = advertised_sold[advertised_sold['winning_loi_sba'] == False]
    
    if len(advertised_sold) > 0:
        sba_usage_when_advertised = len(advertised_sold_sba) / len(advertised_sold) * 100
        print(f"\nWhen SBA is advertised and deal sells:")
        print(f"  Used SBA financing: {len(advertised_sold_sba)} ({sba_usage_when_advertised:.1f}%)")
        print(f"  Used other financing: {len(advertised_sold_no_sba)} ({100-sba_usage_when_advertised:.1f}%)")
    
    # For non-advertised SBA-eligible deals
    not_advertised_eligible_sold = not_advertised_eligible[not_advertised_eligible['status'] == 'sold']
    if len(not_advertised_eligible_sold) > 0:
        not_adv_sba = not_advertised_eligible_sold[not_advertised_eligible_sold['winning_loi_sba'] == True]
        sba_usage_when_not_advertised = len(not_adv_sba) / len(not_advertised_eligible_sold) * 100
        
        print(f"\nWhen SBA-eligible but NOT advertised and deal sells:")
        print(f"  Used SBA financing: {len(not_adv_sba)} ({sba_usage_when_not_advertised:.1f}%)")
    
    # 7. KEY INSIGHTS
    print("\n" + "="*80)
    print("KEY INSIGHTS ON SBA ADVERTISING")
    print("="*80)
    
    # Calculate key metrics for summary
    inquiry_diff_advertised = advertised['total_inquiries'].median() - not_advertised['total_inquiries'].median()
    inquiry_pct_diff = (inquiry_diff_advertised / not_advertised['total_inquiries'].median() * 100)
    
    print(f"""
1. ADVERTISING PREVALENCE:
   - {sba_advertised}/{total_listings} ({sba_advertised/total_listings*100:.1f}%) listings advertise SBA in title
   - {both}/{len(sba_eligible)} ({both/len(sba_eligible)*100:.1f}%) of SBA-eligible deals advertise it
   - {cim_only} SBA-eligible deals DON'T advertise it

2. INQUIRY IMPACT:
   - Overall: Advertising SBA {'+' if inquiry_diff_advertised > 0 else ''}{inquiry_pct_diff:.1f}% inquiries
   - Median: {advertised['total_inquiries'].median():.0f} (advertised) vs {not_advertised['total_inquiries'].median():.0f} (not advertised)

3. SELECTION EFFECTS:
   - Larger deals more likely to advertise SBA
   - This may confound the inquiry analysis

4. BUYER BEHAVIOR:
   - When advertised, buyers know what they're getting into
   - May attract more serious, financing-ready buyers
   - May deter cash buyers

5. RECOMMENDATIONS:
   - Need to control for deal size when comparing inquiries
   - Consider A/B testing SBA advertising on similar deals
   - Track buyer quality, not just quantity
    """)
    
    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_listings': int(total_listings),
        'sba_advertised': int(sba_advertised),
        'sba_advertised_pct': float(sba_advertised/total_listings*100),
        'inquiry_impact': {
            'advertised_median': float(advertised['total_inquiries'].median()),
            'not_advertised_median': float(not_advertised['total_inquiries'].median()),
            'difference': float(inquiry_diff_advertised),
            'pct_difference': float(inquiry_pct_diff)
        }
    }
    
    # Save detailed data for further analysis
    df[['id', 'name', 'sba_in_title', 'sba_status', 'total_inquiries', 'status']].to_csv(
        'sba_title_analysis.csv', index=False
    )
    
    with open('sba_title_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    return df, results

if __name__ == "__main__":
    df, results = analyze_sba_titles()
    print("\n✅ Title analysis complete! Results saved to sba_title_analysis.csv")