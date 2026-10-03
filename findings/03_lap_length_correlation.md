# Finding: Does Circuit Length Predict Undercut Success?

## Question
The undercut rankings (Finding 02) suggested overtaking opportunity, not lap
length, might drive undercut success. Rather than rely on a subjective,
unmeasured concept like "overtaking opportunity," this tests the relationship
against an objective, measurable variable: circuit lap length in kilometers.

## Method
Circuit lap lengths were sourced from official/public circuit specifications
(not present in the Kaggle source dataset) and joined against the undercut
success rates from Finding 02 for all 30 qualifying circuits. Calculated
Pearson correlation coefficient (`CORR()` in Snowflake) between lap length
and undercut success percentage, then tested statistical significance using
a two-tailed t-test (Python/scipy).

## Result
- **r = 0.42** (moderate positive correlation)
- **p = 0.022** (statistically significant at the standard p < 0.05 threshold)
- **r² ≈ 0.17** (lap length accounts for roughly 17% of the variation in
  undercut success across circuits)

Initial visual inspection of the ranked list suggested no clear pattern.
The calculated coefficient revealed a real, moderate relationship that
wasn't apparent by eye alone — a useful reminder that visual scanning of
a list is a poor substitute for an actual statistical test, especially for
moderate-strength relationships.

## Conclusion
**Longer circuits do show a real, statistically significant tendency toward
higher undercut success rates** — but the relationship is far from absolute.
With only ~17% of variation explained, the majority of what determines
undercut success at a given circuit is driven by other factors (track layout,
number of legitimate passing zones, braking zone characteristics) rather than
lap length alone. This refines, rather than confirms or fully rejects, the
original hypothesis: circuit length is a real but minor contributor, not the
primary driver.

## Limitations
- n = 30 circuits is a modest sample for correlation analysis; results should
  be treated as suggestive rather than conclusive.
- Circuit lengths were manually sourced and are current/recent specifications;
  a small number of circuits have had minor layout changes over the dataset's
  2011-2025 span that aren't reflected here.
- Correlation does not establish causation — a third factor (e.g., modern
  circuit design trends favoring both longer layouts and more overtaking
  zones simultaneously) could be driving both variables.