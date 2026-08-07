# Citation prominence: current results

This folder contains the current research-facing results, rewritten as concise
Markdown reports. It intentionally contains no scripts, raw data, JSON, HTML,
or image files.

## Reports

- [Author-level results](AUTHOR_LEVEL_RESULTS.md): John List, Michael Jensen,
  Manuel Arellano, Robert Solow, denominator sensitivity, and matched controls.
- [Economics subject-level results](SUBJECT_LEVEL_RESULTS.md): original event
  pattern, panel-balance diagnosis, paper-age normalization, and the fully
  balanced specification.

## Main result

The raw economics event profile shows citations to older, unrelated papers
rising around an author's candidate hit. That result weakens as the comparison
becomes more credible:

| Specification | Pre/post change |
|---|---:|
| Original citation mean | +0.348 citations |
| Aggregate mature-paper age standardization | +0.213 citations |
| Paper-level at-risk excess over expected | +0.114 citations |
| Fully balanced paper-level excess over expected | **−0.063 citations** |

The positive aggregate pattern is therefore not robust to requiring every
author–paper–hit unit to be observed throughout the complete −10:+10 window.
This does not prove that prominence has no spillover effect. It shows that the
current positive headline is highly sensitive to risk-set composition and
normal citation aging.

## Status

All estimates remain exploratory and descriptive. The project does not yet
have a preferred causal estimate.
