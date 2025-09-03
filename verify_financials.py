import json

# Check cost benefit analysis
with open('sba_cost_benefit_analysis.json', 'r') as f:
    cost_benefit = json.load(f)
    
print(f'LOI extension: {cost_benefit["key_metrics"]["extra_loi_days"]} days')
print(f'Commission analysis (raw):')
print(f'  SBA median: ${cost_benefit["key_metrics"]["sba_median_commission"]:,.0f}')
print(f'  Non-SBA median: ${cost_benefit["key_metrics"]["non_sba_median_commission"]:,.0f}')
print(f'  Difference: {cost_benefit["key_metrics"]["commission_increase_pct"]:.1f}%')

# Check specific scenario for $1.5M deal
for scenario in cost_benefit['scenarios']:
    if scenario['purchase_price'] == 1750000:
        print(f'\nMedium deal ($1.75M) analysis:')
        print(f'  Purchase price: ${scenario["purchase_price"]:,.0f}')
        print(f'  Commission difference assumed: ${scenario["commission_difference"]:,.0f}')
        
        # Find 10% opportunity cost
        for seller_cost in scenario['seller_costs']:
            if seller_cost['return_rate'] == '10%':
                print(f'  Opportunity cost at 10%: ${seller_cost["opportunity_cost"]:,.0f}')
                print(f'  Net benefit: ${seller_cost["net_benefit"]:,.0f}')
                
    if scenario['purchase_price'] == 1500000:
        print(f'\n$1.5M deal analysis (if exists):')
        print(f'  Purchase price: ${scenario["purchase_price"]:,.0f}')
