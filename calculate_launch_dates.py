#!/usr/bin/env python3
"""
Calculate launch dates for listings based on inquiry volume spikes.
A listing is considered "launched" when it experiences a surge in inquiries 
(typically 20+ inquiries in a 24-48 hour period).
"""

import pymysql
import pandas as pd
from datetime import datetime, timedelta
import json
import numpy as np

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

def calculate_launch_dates(min_spike_threshold=20, window_days=2):
    """
    Calculate launch dates based on inquiry volume spikes.
    
    Args:
        min_spike_threshold: Minimum inquiries to consider a spike
        window_days: Window size for detecting spikes (default 2 days)
    
    Returns:
        DataFrame with listing_id, launch_date, spike_volume, confidence
    """
    conn = get_db_connection()
    
    # Get inquiry data aggregated by day
    query = """
    SELECT 
        listing_id,
        DATE(created_at) as inquiry_date,
        COUNT(*) as daily_inquiries,
        MIN(created_at) as first_inquiry_time
    FROM inquiries
    WHERE listing_id IN (
        SELECT id FROM listings 
        WHERE deleted_at IS NULL
        AND (closed_type IN (1, 2) OR milestone_id IN (7, 8))
    )
    GROUP BY listing_id, DATE(created_at)
    ORDER BY listing_id, inquiry_date
    """
    
    df = pd.read_sql(query, conn)
    
    # Ensure numeric type for daily_inquiries
    df['daily_inquiries'] = pd.to_numeric(df['daily_inquiries'], errors='coerce')
    
    # Calculate rolling window sums for spike detection
    launch_dates = []
    
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id].copy()
        listing_data = listing_data.sort_values('inquiry_date')
        
        # Ensure daily_inquiries is numeric
        listing_data['daily_inquiries'] = pd.to_numeric(listing_data['daily_inquiries'], errors='coerce').fillna(0)
        
        # Calculate rolling sum for window
        listing_data['rolling_sum'] = listing_data['daily_inquiries'].rolling(
            window=window_days, min_periods=1
        ).sum()
        
        # Find first spike above threshold
        spikes = listing_data[listing_data['rolling_sum'] >= min_spike_threshold]
        
        if not spikes.empty:
            # Get the first spike
            first_spike = spikes.iloc[0]
            
            # Calculate confidence based on spike magnitude
            confidence = min(1.0, first_spike['rolling_sum'] / (min_spike_threshold * 3))
            
            # Look back to find the actual start of the spike
            spike_idx = listing_data[listing_data['inquiry_date'] == first_spike['inquiry_date']].index[0]
            start_idx = max(0, spike_idx - window_days + 1)
            launch_date = listing_data.iloc[start_idx]['inquiry_date']
            
            launch_dates.append({
                'listing_id': listing_id,
                'launch_date': launch_date,
                'spike_volume': first_spike['rolling_sum'],
                'spike_date': first_spike['inquiry_date'],
                'confidence': confidence,
                'daily_inquiries_at_spike': first_spike['daily_inquiries']
            })
        else:
            # No clear spike - use first significant activity
            if len(listing_data) > 0:
                # Use date with most inquiries as fallback
                max_day = listing_data.loc[listing_data['daily_inquiries'].idxmax()]
                launch_dates.append({
                    'listing_id': listing_id,
                    'launch_date': max_day['inquiry_date'],
                    'spike_volume': max_day['daily_inquiries'],
                    'spike_date': max_day['inquiry_date'],
                    'confidence': 0.3,  # Low confidence
                    'daily_inquiries_at_spike': max_day['daily_inquiries']
                })
    
    conn.close()
    
    return pd.DataFrame(launch_dates)

def validate_launch_dates(launch_dates_df):
    """
    Validate launch dates against listing creation dates and other milestones.
    """
    conn = get_db_connection()
    
    # Get listing dates for validation
    query = """
    SELECT 
        id as listing_id,
        created_at,
        closed_at,
        closed_type,
        milestone_id
    FROM listings
    WHERE id IN ({})
    """.format(','.join(map(str, launch_dates_df['listing_id'].tolist())))
    
    listings_df = pd.read_sql(query, conn)
    conn.close()
    
    # Merge with launch dates
    validated = launch_dates_df.merge(listings_df, on='listing_id', how='left')
    
    # Calculate days from creation to launch
    validated['days_to_launch'] = (
        pd.to_datetime(validated['launch_date']) - 
        pd.to_datetime(validated['created_at'])
    ).dt.days
    
    # Calculate days on market (launch to close)
    validated['days_on_market'] = None
    closed_mask = validated['closed_at'].notna()
    validated.loc[closed_mask, 'days_on_market'] = (
        pd.to_datetime(validated.loc[closed_mask, 'closed_at']) - 
        pd.to_datetime(validated.loc[closed_mask, 'launch_date'])
    ).dt.days
    
    # Flag potential issues
    validated['validation_notes'] = ''
    validated.loc[validated['days_to_launch'] < 0, 'validation_notes'] = 'Launch before creation'
    validated.loc[validated['days_to_launch'] > 365, 'validation_notes'] += ' Very late launch'
    validated.loc[
        (validated['days_on_market'].notna()) & (validated['days_on_market'] < 0), 
        'validation_notes'
    ] += ' Closed before launch'
    
    return validated

def save_launch_dates(validated_df, output_file='launch_dates.json'):
    """
    Save launch dates to JSON file for later use.
    """
    # Convert to JSON-serializable format
    output_data = validated_df.to_dict('records')
    
    # Convert datetime objects to strings
    for record in output_data:
        for key, value in record.items():
            if pd.api.types.is_datetime64_any_dtype(type(value)) or isinstance(value, pd.Timestamp):
                record[key] = value.isoformat() if pd.notna(value) else None
            elif isinstance(value, (np.int64, np.float64)):
                record[key] = float(value) if pd.notna(value) else None
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Launch dates saved to {output_file}")
    
    # Summary statistics
    print("\nLaunch Date Statistics:")
    print(f"Total listings analyzed: {len(validated_df)}")
    print(f"High confidence launches (>0.7): {len(validated_df[validated_df['confidence'] > 0.7])}")
    print(f"Medium confidence launches (0.4-0.7): {len(validated_df[(validated_df['confidence'] >= 0.4) & (validated_df['confidence'] <= 0.7)])}")
    print(f"Low confidence launches (<0.4): {len(validated_df[validated_df['confidence'] < 0.4])}")
    
    if 'validation_notes' in validated_df.columns:
        issues = validated_df[validated_df['validation_notes'] != '']
        if not issues.empty:
            print(f"\nValidation issues found: {len(issues)}")
            print(issues[['listing_id', 'validation_notes']].head(10))
    
    return validated_df

if __name__ == "__main__":
    print("Calculating launch dates based on inquiry volume spikes...")
    print("=" * 60)
    
    # Calculate launch dates
    launch_dates = calculate_launch_dates(min_spike_threshold=20, window_days=2)
    
    if not launch_dates.empty:
        print(f"Found launch dates for {len(launch_dates)} listings")
        
        # Validate launch dates
        print("\nValidating launch dates...")
        validated = validate_launch_dates(launch_dates)
        
        # Save results
        save_launch_dates(validated)
        
        # Display sample
        print("\nSample launch dates:")
        print(validated[['listing_id', 'launch_date', 'spike_volume', 'confidence', 'days_on_market']].head(10))
    else:
        print("No launch dates could be calculated")