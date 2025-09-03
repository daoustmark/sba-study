# Section 3: The Deal Size Confound

## 3.1 The Spurious Correlation

Initial analysis of our dataset revealed a striking finding: SBA-financed deals appeared to generate substantially higher commissions than non-SBA deals, with median commissions of $210,000 versus $104,000 respectively—a seemingly impressive 102% premium. This raw comparison suggested that SBA financing might be a powerful driver of broker success, warranting immediate strategic focus.

However, this initial finding exemplifies the classic statistical warning that correlation does not imply causation. A deeper examination revealed that this apparent SBA advantage was entirely spurious, driven by a fundamental confounding variable: deal size.

The mechanism underlying this spurious correlation became clear when we examined the relationship between deal size and SBA eligibility. SBA loans have minimum loan amounts that effectively exclude smaller deals from SBA financing entirely. Simultaneously, larger deals naturally generate higher absolute commissions due to percentage-based fee structures, regardless of financing method.

When we controlled for deal size by restricting our analysis to the $500K-$2M range—where both SBA and non-SBA deals are common—the dramatic commission difference evaporated. Within this controlled comparison, SBA deals showed only a modest 16% commission premium with a p-value of 0.22, indicating no statistically significant difference. This finding fundamentally redirected our analysis from celebrating SBA's apparent benefits to understanding the critical importance of proper statistical controls.

## 3.2 SBA Prevalence by Deal Size

To understand the true relationship between deal size and SBA utilization, we analyzed SBA eligibility and usage patterns across different deal size segments. This analysis revealed distinct patterns that explain the spurious correlation identified in Section 3.1.

### Deal Size Segments and SBA Patterns

**Sub-$500K Deals: The Cash-Only Zone**
- SBA Eligible: 0% of deals
- SBA Usage: Not applicable
- Market Dynamics: Cash buyers dominate this segment, with deals often structured as asset purchases that fall below SBA minimum thresholds

**$500K-$1M Deals: Emerging SBA Market**
- SBA Eligible: 23% of deals
- SBA Usage: 43% of eligible deals (10% of total segment)
- Market Characteristics: Mix of cash buyers and first-time business acquirers beginning to utilize SBA financing

**$1M-$2M Deals: The SBA Sweet Spot**
- SBA Eligible: 36% of deals  
- SBA Usage: 50% of eligible deals (18% of total segment)
- Market Dynamics: Optimal range for SBA financing where loan amounts justify the additional complexity while remaining within comfort zones for lenders

**Above $2M Deals: High Eligibility, Moderate Usage**
- SBA Eligible: 93% of deals
- SBA Usage: 62% of eligible deals (58% of total segment)
- Market Characteristics: Nearly universal eligibility but competing financing options (conventional loans, seller financing) become more viable

### Key Insights from Size Analysis

**Selection Bias in Raw Comparisons**
The data clearly demonstrates why raw comparisons between SBA and non-SBA deals are fundamentally flawed. SBA deals are heavily concentrated in larger size categories (78% of SBA deals are above $1M versus 52% of non-SBA deals), creating an inevitable upward bias in commission comparisons.

**The Eligibility Ceiling Effect**
The dramatic jump in eligibility from 36% to 93% between the $1M-$2M and >$2M categories reveals the SBA program's structural bias toward larger transactions. This creates a natural ceiling effect where smaller deals are systematically excluded from SBA consideration.

**Usage Rates Within Eligible Deals**
When examining usage rates among eligible deals only, we observe relatively consistent adoption rates (43-62%) across size categories. This suggests that deal size itself doesn't dramatically influence buyer preferences for SBA financing once eligibility is established—the primary driver is simply access to the program.

### Implications for Analysis Methodology

This deal size analysis fundamentally changed our analytical approach in three critical ways:

1. **Controlled Comparisons**: All subsequent analyses comparing SBA and non-SBA outcomes are restricted to size ranges where both financing methods are viable ($500K-$2M), eliminating the selection bias that drove our initial spurious findings.

2. **Segmented Analysis**: Rather than treating the market as homogeneous, we now analyze SBA impact within specific deal size segments, recognizing that financing dynamics vary substantially across the value spectrum.

3. **Base Rate Awareness**: Understanding that SBA financing is primarily a phenomenon of mid-to-large deals (concentrated in the $1M+ range) helps contextualize any findings about SBA impact within the appropriate market segments.

The discovery of this confound serves as a crucial methodological lesson: apparent relationships in business data often reflect structural market dynamics rather than true causal relationships. Only through careful consideration of confounding variables can we separate genuine effects from statistical artifacts, ensuring our conclusions provide actionable insights rather than misleading correlations.