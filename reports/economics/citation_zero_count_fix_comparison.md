# Economics Citation Zero-Count Fix Comparison

This note compares the earlier OpenAlex `counts_by_year` run with the corrected run that recalculates annual citations from OpenAlex reference links.

## What Changed

The earlier run used OpenAlex `counts_by_year` directly. Those data were sparse: if a paper-year was absent, it was ambiguous whether the paper received zero citations or whether OpenAlex omitted the row. The corrected run rebuilds annual citation counts from the snapshot's reference links, then fills missing paper-years as true zeros inside the balanced event window.

## Missingness Fix

| Measure | Earlier `counts_by_year` run | Recalculated-reference run |
|---|---:|---:|
| Balanced event-panel rows | 1,597,554 | 1,597,554 |
| Paper-author-hit pairs | 76,074 | 76,074 |
| Overall missing citation rows | 1,122,628 | 0 |
| Overall missing citation rate | 70.27% | 0.00% |
| Pre-hit missing citation rate | 52.04% | 0.00% |
| Post-hit missing citation rate | 86.85% | 0.00% |
| Observed-only pairs with pre and post observations | 26,092 | 76,074 |

The key improvement is that the observed-only sample is no longer a selected subset. In the corrected run, every paper-author-hit pair has a value for every event year from -10 through +10.

## Estimate Comparison

| Estimate | Earlier `counts_by_year` run | Recalculated-reference run |
|---|---:|---:|
| Mean pre-hit annual citations, zero-filled | 0.1612 | 0.3515 |
| Mean post-hit annual citations, zero-filled | 0.5000 | 0.6688 |
| Mean added annual citations, zero-filled | +0.3388 | +0.3172 |
| Mean added annual citations, observed-only | +2.0412 | +0.3172 |

The old observed-only estimate was much larger because citation rows were missing unevenly, especially after the hit. The corrected run removes that artifact: zero-filled and observed-only estimates are now the same because citation histories are structurally complete.

## Recalculated Citation Coverage

| Recalculated citation build statistic | Value |
|---|---:|
| Snapshot work records scanned | 492,361,307 |
| Records with publication year | 464,803,850 |
| Records with references | 121,673,155 |
| References scanned | 3,041,923,704 |
| Economics target works | 7,924,745 |
| Matched reference citations into economics works | 48,082,940 |
| Annual citation rows produced | 11,869,319 |

## Interpretation

The qualitative result survives the fix: older unrelated papers by hit authors receive more annual citations after the hit. The corrected simple before/after increase is about +0.317 annual citations per paper-author-hit pair. This is still descriptive, not causal, but it is now based on a complete balanced event panel rather than sparse OpenAlex citation-year rows.
