# Paper-level normalized economics results

This specification uses the recovered 191-million-row author–paper–year panel.
Expected citations are estimated from deduplicated economics works in the same
calendar year, paper age, and document type.

Two samples are reported:

- **At risk:** a focal paper enters only after publication.
- **Balanced full window:** the focal paper was published before event time -10
  and is observed throughout -10:+10.

| Sample | Excess pre | Excess post | Change | O/E pre | O/E post | O/E change |
|---|---:|---:|---:|---:|---:|---:|
| At risk | 0.137 | 0.252 | +0.114 | 1.260 | 1.406 | +0.146 |
| Balanced -10:+10 | -0.006 | -0.068 | -0.063 | 0.989 | 0.871 | -0.119 |

![Lifecycle-adjusted excess citations](paper_level_excess_citations.svg)

![Observed/expected citation ratio](paper_level_observed_expected_ratio.svg)

> **Descriptive, not causal.** The benchmark absorbs normal paper aging,
> calendar-year citation conditions, and document type. It does not solve
> author selection, identity errors, work versions, or differential pretrends.
