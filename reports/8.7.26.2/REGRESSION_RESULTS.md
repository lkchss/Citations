# Original economics regressions and paper-age controls

## Bottom line

The original GitHub regressions have been reproduced exactly from the recovered
SSD input. Adding a separate fixed effect for every paper age barely changes
their level estimates. This means that nonlinear average citation aging is not
the main reason for the original coefficients.

The original regressions remain highly sensitive to functional form and the
right tail of citations. They are descriptive exposure regressions, not an
estimate of the effect of an author's big hit.

## Exact reproduction

The recovered input contains 211,825 paper-author-year observations, 14,675
focal works, 2,853 authors, and 14,796 paper-author units. Its SHA-256 hash is:

```text
17c3cb2fd71e9b5a87bf18d18659c8054d14df7db4c7daea67dd818018523869
```

Rerunning the original code produced CSV result files that are byte-for-byte
identical to the files already committed in GitHub.

The outcome is annual citations to focal paper *j*. Unrelated and related
exposures are cumulative citations, through the prior year, to the author's
other economics papers. Related papers have a direct reference edge with the
focal paper in either direction. Standard errors are clustered by focal work.

| Specification | Model 1: unrelated | Model 2: unrelated | Model 2: related |
|---|---:|---:|---:|
| Original: paper + year FE | 0.000344 (0.000215) | -0.000511 (0.000306) | 0.004917 (0.002513) |
| Original p-value | 0.109 | 0.0947 | 0.0504 |

Model 1 shows no precise unrelated association. Once related exposure is
included, unrelated exposure is negative at the 10% level and related exposure
is positive at approximately the 5% boundary.

## What paper age changes

The original paper and calendar-year fixed effects already absorb any *linear*
age profile because paper age equals calendar year minus publication year. They
do not absorb a nonlinear lifecycle—for example, a rapid early peak followed by
a long decline. We therefore added a categorical fixed effect for every paper
age.

| Specification | Model 1: unrelated | Model 2: unrelated | Model 2: related |
|---|---:|---:|---:|
| Original: paper + year FE | 0.000344 (0.000215) | -0.000511 (0.000306) | 0.004917 (0.002513) |
| Add categorical paper-age FE | 0.000346 (0.000212) | -0.000503 (0.000305) | 0.004921 (0.002515) |

The coefficients and standard errors are essentially unchanged. The added age
effects identify nonlinear deviations from the age trend; the linear component
is inseparable from paper and calendar-year effects. This age-period-cohort
identity should be stated explicitly rather than treating all three sets of
effects as independently identified.

## Functional-form sensitivity

Two additional checks deliberately change the estimand and should not be read
as preferred replacements.

| Specification | Model 1: unrelated | Model 2: unrelated | Model 2: related |
|---|---:|---:|---:|
| Log(1+x), paper + year + age FE | 0.00469 (0.00312) | 0.01823 (0.00305) | -0.05229 (0.00516) |
| First differences, year + age FE | 0.000086 (0.000192) | -0.000121 (0.000102) | 0.001181 (0.000943) |

The log specification reverses the Model 2 signs. Because both the outcome and
cumulative exposures are transformed, its coefficients are semi-elasticity-like
associations and are not directly comparable in magnitude with the levels
models. First differencing changes cumulative exposure into the annual change
in exposure; neither Model 2 coefficient is statistically distinguishable from
zero there.

Together with the previously documented winsorization results, these checks
show that the exposure relationship is not distributionally or functionally
stable. The flexible age control itself is stable; the larger problem is the
regression's dependence on extreme observations and its specification.

## Recommended use of age controls

For the hit-centered subject-level work, retain several transparent views:

1. Preserve the original unadjusted event profile for comparability.
2. Make the publication-at-risk restriction mandatory; never encode years
   before a focal paper exists as zero-citation observations.
3. Report paper-level observed-minus-expected citations, where expected
   citations are estimated within calendar year, exact paper age, and document
   type.
4. Report a fully balanced event window separately, because age normalization
   does not fix changing sample composition.
5. In regressions, use focal-paper and calendar-year fixed effects plus flexible
   nonlinear age controls, and state the age-period-cohort limitation.
6. Add non-hit comparison authors and pretrend diagnostics before calling any
   estimate causal.

The recovered 191-million-row paper-author-year panel now allows these controls
to be calculated at the paper level. That is preferable to the earlier
aggregate age-bin reweighting, but it does not eliminate selection into the
balanced sample.

## Scope and reproducibility

These exposure regressions ask whether citations to an author's other papers
predict citations to a focal paper. The hit event study instead asks whether an
author's older unrelated papers change around publication of a dominant paper.
The two analyses should remain separate.

Machine-readable estimates are in
[`economics_age_control_comparison.csv`](../subjects/economics_age_control_comparison.csv).
The comparison is generated by
[`analyze_economics_age_control_comparison.py`](../../scripts/analyze_economics_age_control_comparison.py).
The original estimates remain in
[`two_model_research.csv`](../subjects/two_model_research.csv).
