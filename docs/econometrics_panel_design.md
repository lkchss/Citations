# Econometrics Panel Design

This project is targeting the effect of an author's successful publication on citation levels for that author's other, unrelated papers.

## Starting Estimand

For an author who has a hit paper, compare annual citations to that author's earlier papers before and after the hit year.

The first-pass treatment event is:

```text
author has a hit paper in year t
```

The first-pass outcome is:

```text
annual citations to a pre-hit focal paper in calendar year y
```

## Unit Of Observation

The first panel uses:

```text
paper-author-hit-year
```

This is paper-author-year for a specific hit event. If an author has multiple hit papers, the same focal paper can appear in multiple event panels, one per hit. That is useful for exploration but will need stricter handling before a final causal design.

## Current Hit Rule

The starter script defines a hit as an OpenAlex work with:

```text
type in article, preprint, review
cited_by_count > 100
publication_year >= 1990
```

A stricter author-prevalence rule can require:

```text
hit_cited_by_count_total / author_total_citations >= 0.50
```

In the current script this is enabled with:

```bash
python3 scripts/build_author_paper_year_panel.py --min-hit-author-citation-share 0.5 --min-author-included-works 3 --min-unrelated-focal-works 3
```

`author_total_citations` is computed over the same included OpenAlex work types in the input files being processed. During an incomplete pull, this is a partial-corpus measure; after the full economics pull finishes, it becomes a within-economics-corpus measure.

The `--min-author-included-works` guard is important because an author with only one included paper mechanically has a hit share of 1.0.

The current stricter event-screen also requires at least three prior unrelated focal papers. That can also be controlled directly:

```bash
python3 scripts/build_author_paper_year_panel.py --min-unrelated-focal-works 3
```

This is intentionally simple. Later candidates:

- top percentile within publication year and subfield
- top percentile within topic-year
- cumulative citations within five years after publication
- field-normalized impact, using `fwci` or `citation_normalized_percentile`

## Unrelated Paper Rule

For an author-hit pair, a focal paper is included only when:

```text
focal_publication_year <= hit_publication_year - 1
focal_work_id is not in hit.referenced_works
```

This matches the current idea: measure spillovers onto the author's prior papers that the successful publication did not cite.

## Panel Columns

The generated panel contains:

| Column | Meaning |
|---|---|
| `author_id` | OpenAlex author ID |
| `author_name` | Author display name |
| `author_position_on_focal` | Position on the focal paper, such as first, middle, last, or sole |
| `focal_work_id` | Prior unrelated paper |
| `focal_title` | Focal paper title |
| `focal_publication_year` | Focal paper publication year |
| `focal_type` | OpenAlex work type |
| `focal_cited_by_count_total` | Total current OpenAlex citations to the focal paper |
| `focal_fwci` | Field-weighted citation impact, if available |
| `focal_field` | OpenAlex primary field |
| `focal_subfield` | OpenAlex primary subfield |
| `focal_primary_topic_id` | OpenAlex primary topic ID |
| `focal_primary_topic` | OpenAlex primary topic name |
| `hit_work_id` | Author's hit paper |
| `hit_title` | Hit paper title |
| `hit_publication_year` | Hit paper publication year |
| `hit_type` | OpenAlex work type for the hit |
| `hit_cited_by_count_total` | Total current OpenAlex citations to the hit |
| `hit_author_total_citations` | Total citations across the author's included works in the processed input corpus |
| `hit_author_included_works` | Count of the author's included works in the processed input corpus |
| `hit_author_citation_share` | Hit paper's share of the author's included-work citations |
| `hit_unrelated_focal_works` | Number of prior unrelated focal papers for this author-hit event |
| `hit_fwci` | Hit paper field-weighted citation impact, if available |
| `year` | Calendar year for the outcome |
| `event_time` | `year - hit_publication_year` |
| `post_hit` | 1 when `event_time >= 0`, else 0 |
| `years_since_focal_publication` | Age of the focal paper in that outcome year |
| `citations` | Annual citations to the focal paper in `year` |
| `citations_observed` | 1 when the citation outcome is structurally zero before publication or present in OpenAlex `counts_by_year`; 0 when the balanced row is retained but the annual outcome is not available |

## Important Caveats

The first panel is for exploration, not yet final identification.

- Total `cited_by_count` is measured as of the OpenAlex snapshot, so the simple hit rule can favor older papers.
- Annual citation counts are observed from `counts_by_year`; unavailable years remain in the balanced panel with blank `citations` and `citations_observed = 0`.
- Authors with multiple hits create overlapping event windows.
- OpenAlex author disambiguation is good enough for exploration, but important authors should be audited.
- A final model will likely need author fixed effects, focal paper fixed effects, paper age controls, calendar-year fixed effects, topic-year controls, and a cleaner untreated or not-yet-treated comparison group.
