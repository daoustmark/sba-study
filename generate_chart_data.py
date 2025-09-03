#!/usr/bin/env python3
"""
Generate chart data for the dashboard.
"""

import pandas as pd
import json
from collections import Counter

def generate_chart_data():
    """Generate all chart data needed for the dashboard."""
    
    # Load the launch date analysis
    df = pd.read_csv('launch_date_analysis_v2.csv')
    
    # Generate commission scatter plot data
    commission_data = {
        'sba': [],
        'non_sba': [],
        'unknown': []
    }
    
    # Get sold deals only
    sold_df = df[df['status'] == 'sold'].copy()
    
    for _, row in sold_df.iterrows():
        if pd.notna(row['closed_commission']) and row['closed_commission'] > 0:
            point = {'x': row['closed_commission'], 'y': 1}
            
            if row['sba_status'] == 'yes':
                commission_data['sba'].append(point)
            elif row['sba_status'] == 'no':
                commission_data['non_sba'].append(point)
            else:
                commission_data['unknown'].append(point)
    
    # Count y values for scatter plot
    def count_y_values(data_points):
        """Group points by x value and count them."""
        x_values = {}
        for point in data_points:
            x = point['x']
            if x not in x_values:
                x_values[x] = 0
            x_values[x] += 1
        
        # Convert back to points with proper y values
        result = []
        for x, count in x_values.items():
            for i in range(count):
                result.append({'x': x, 'y': i + 1})
        return result
    
    commission_data['sba'] = count_y_values(commission_data['sba'])
    commission_data['non_sba'] = count_y_values(commission_data['non_sba'])
    commission_data['unknown'] = count_y_values(commission_data['unknown'])
    
    # Generate box plot data for time to close
    time_data = {
        'sba_sold': [],
        'non_sba_sold': [],
        'unknown_sold': []
    }
    
    for _, row in sold_df.iterrows():
        if pd.notna(row['days_on_market']):
            if row['sba_status'] == 'yes':
                time_data['sba_sold'].append(row['days_on_market'])
            elif row['sba_status'] == 'no':
                time_data['non_sba_sold'].append(row['days_on_market'])
            else:
                time_data['unknown_sold'].append(row['days_on_market'])
    
    # Calculate quartiles for box plot
    def calculate_box_plot_data(values):
        """Calculate quartiles for box plot."""
        if not values:
            return [0, 0, 0, 0, 0]
        
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        
        # Min
        min_val = sorted_vals[0]
        # Q1
        q1_idx = int(n * 0.25)
        q1 = sorted_vals[q1_idx]
        # Median
        median_idx = int(n * 0.5)
        median = sorted_vals[median_idx]
        # Q3
        q3_idx = int(n * 0.75)
        q3 = sorted_vals[q3_idx]
        # Max
        max_val = sorted_vals[-1]
        
        return [min_val, q1, median, q3, max_val]
    
    box_plot_data = {
        'sba_sold': calculate_box_plot_data(time_data['sba_sold']),
        'non_sba_sold': calculate_box_plot_data(time_data['non_sba_sold']),
        'unknown_sold': calculate_box_plot_data(time_data['unknown_sold'])
    }
    
    # Write JavaScript file with all chart data
    js_content = f"""// Chart data for SBA dashboard
// Generated: {pd.Timestamp.now().isoformat()}

const commissionDataSBA = {json.dumps(commission_data['sba'], indent=2)};

const commissionDataNonSBA = {json.dumps(commission_data['non_sba'], indent=2)};

const commissionDataUnknown = {json.dumps(commission_data['unknown'], indent=2)};

const boxPlotData = {{
    'sba_sold': {box_plot_data['sba_sold']},
    'non_sba_sold': {box_plot_data['non_sba_sold']},
    'unknown_sold': {box_plot_data['unknown_sold']}
}};
"""
    
    with open('chart_data.js', 'w') as f:
        f.write(js_content)
    
    print(f"Generated chart data:")
    print(f"  - SBA commission points: {len(commission_data['sba'])}")
    print(f"  - Non-SBA commission points: {len(commission_data['non_sba'])}")
    print(f"  - Unknown commission points: {len(commission_data['unknown'])}")
    print(f"  - Box plot data for 3 categories")
    
    return commission_data, box_plot_data

if __name__ == "__main__":
    generate_chart_data()
    print("\n✅ Chart data generated: chart_data.js")