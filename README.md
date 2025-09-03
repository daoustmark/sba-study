# SBA Pre-Qualification Impact Study

## Overview
This repository contains a comprehensive analysis of SBA pre-qualification impact on business listings at Quiet Light Brokerage. The study examines 251 business listings from 2021-2024 to understand how SBA financing affects buyer behavior and deal outcomes.

## Key Findings
- **Higher Buyer Interest**: SBA-advertised listings receive 24-30% more inquiries
- **Better Success Rates**: 83.3% success rate for SBA-eligible deals vs 75.5% for non-eligible
- **Market Inefficiency**: Only 43% of eligible deals use SBA despite clear benefits
- **Time Trade-offs**: 38 extra days under LOI but 54 days faster overall closing

## Repository Structure

### Analysis Scripts
- `sba_controlled_analysis.py` - Controlled comparison of SBA vs non-SBA deals
- `sba_title_analysis.py` - Analysis of SBA advertising in listing titles
- `sba_cost_benefit_analysis.py` - Financial impact calculations
- `sba_verification_enhanced.js` - Data verification scripts

### Data Files
- `launch_date_analysis_v2.csv` - Core dataset with 251 listings
- `sba_controlled_analysis.json` - Controlled analysis results
- `sba_title_analysis.json` - Title analysis results
- `sba_cost_benefit_analysis.json` - Cost-benefit calculations

### Reports
- `SBA_Impact_Analysis_Paper.md` - Main research paper
- `fact_check_report_detailed.md` - Detailed verification of all claims
- `SBA_Fact_Check_Plain_Report.md` - Plain-language fact-check summary

### Dashboards
- `sba_dashboard_revised.html` - Interactive visualization dashboard
- `sba_cost_benefit_dashboard.html` - Financial analysis dashboard

## Methodology
The analysis uses multiple approaches to ensure accuracy:
1. **CIM Processing**: Automated classification of SBA eligibility using Gemini API
2. **Launch Date Detection**: Identifying listing launch through inquiry surge patterns
3. **Controlled Comparisons**: Comparing within deal size ranges to eliminate confounds
4. **Statistical Testing**: Chi-square tests and bootstrap confidence intervals

## Data Integrity
- 85% of claims directly verified against source data
- Minor discrepancies documented and explained
- Conservative reporting approach used throughout

## Usage
The analysis files can be run independently or as part of a larger analysis pipeline. Most scripts output both JSON (for programmatic use) and HTML dashboards (for visualization).

### Requirements
- Python 3.8+
- pandas, numpy, scipy
- MySQL database access (for live data)
- Gemini API key (for CIM processing)

## Contact
For questions about this analysis, contact Quiet Light Brokerage research team.

## License
Internal use only - Quiet Light Brokerage proprietary analysis.