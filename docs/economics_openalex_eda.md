# OpenAlex Economics EDA

Generated: 2026-05-28 UTC

## Query Definition

Default pull filter:

```text
primary_topic.field.id:20
```

OpenAlex field `20` is `Economics, Econometrics and Finance`.

Output directory:

```text
/root/sdb1/openalex/economics_field20
```

## Corpus Size

Total works matching the filter:

```text
8,836,615
```

## Work Types

| Type | Works |
|---|---:|
| article | 5,784,384 |
| book-chapter | 1,105,157 |
| paratext | 533,045 |
| preprint | 418,063 |
| dissertation | 304,629 |
| book | 266,341 |
| dataset | 129,129 |
| other | 86,621 |
| libguides | 41,376 |
| report | 37,554 |
| review | 34,462 |
| reference-entry | 29,256 |
| letter | 24,931 |
| editorial | 20,746 |
| erratum | 10,596 |
| peer-review | 8,037 |
| standard | 1,259 |
| retraction | 514 |
| supplementary-materials | 510 |

Useful analysis subsets:

| Subset | Works |
|---|---:|
| Articles only | 5,784,384 |
| Articles, reviews, and preprints | 6,236,909 |

## Open Access

| Open access | Works |
|---|---:|
| false | 6,022,450 |
| true | 2,814,165 |

| OA status | Works |
|---|---:|
| closed | 6,022,452 |
| green | 1,340,615 |
| diamond | 469,362 |
| bronze | 464,264 |
| hybrid | 271,951 |
| gold | 267,971 |

## Coverage

| Coverage flag | Works |
|---|---:|
| Has DOI | 5,923,899 |
| Has references | 2,104,071 |
| Has abstract | 4,263,702 |

## Primary Subfields

| Subfield | Works |
|---|---:|
| Economics and Econometrics | 6,821,789 |
| Finance | 1,121,459 |
| General Economics, Econometrics and Finance | 893,367 |

## Top Publication Years

These are sorted by count, not chronologically.

| Year | Works |
|---:|---:|
| 2016 | 357,037 |
| 2023 | 352,965 |
| 2020 | 351,703 |
| 2017 | 337,132 |
| 2018 | 336,355 |
| 2019 | 325,061 |
| 2015 | 314,296 |
| 2024 | 312,710 |
| 2021 | 312,266 |
| 2014 | 306,447 |
| 2025 | 300,845 |
| 2013 | 300,133 |
| 2012 | 284,688 |
| 2022 | 277,347 |
| 2011 | 264,969 |
| 2010 | 247,300 |
| 2009 | 230,889 |
| 2008 | 210,651 |
| 2007 | 199,151 |
| 2006 | 173,978 |

The corpus includes records before 1900 and through 2026. The 2026 count is partial as of 2026-05-28.

## Top Primary Topics

| Topic | Works |
|---|---:|
| Diverse Scientific and Economic Studies | 2,208,248 |
| Healthcare Policy and Management | 260,901 |
| Global trade and economics | 215,043 |
| Economic Theory and Policy | 185,100 |
| Historical Economic and Social Studies | 183,402 |
| Business, Innovation, and Economy | 175,296 |
| Global Financial Crisis and Policies | 164,761 |
| Fiscal Policy and Economic Growth | 162,835 |
| Health Systems, Economic Evaluations, Quality of Life | 161,694 |
| Cinema and Media Studies | 159,852 |
| Banking stability, regulation, efficiency | 146,577 |
| Historical and socio-economic studies of Spain and related regions | 135,294 |
| Monetary Policy and Economic Impact | 135,201 |
| Economic theories and models | 132,522 |
| Housing, Finance, and Neoliberalism | 124,379 |
| Financial Markets and Investment Strategies | 120,789 |
| Regional Development and Management Studies | 120,661 |
| Economic Theory and Institutions | 118,740 |
| Diverse academic and cultural studies | 118,107 |
| Housing Market and Economics | 116,423 |
| Insurance and Financial Risk Management | 116,239 |
| Economic Issues in Ukraine | 108,838 |
| Balkan and Eastern European Studies | 106,433 |
| Stochastic processes and financial applications | 104,657 |
| Climate Change Policy and Economics | 103,748 |
| Economic Growth and Fiscal Policies | 101,357 |
| Financial Crisis of the 21st Century | 98,431 |
| Economic Growth and Productivity | 97,309 |
| Market Dynamics and Volatility | 92,516 |
| Complex Systems and Time Series Analysis | 85,427 |

Some primary topics are broad or noisy. For analysis, keep the broad field pull and tag or exclude noisy topics during cleaning.

## Full-Record Fields Observed

The full-record sample includes these top-level fields:

```text
id
doi
title
display_name
publication_year
publication_date
ids
language
primary_location
type
indexed_in
open_access
authorships
institutions
countries_distinct_count
institutions_distinct_count
corresponding_author_ids
corresponding_institution_ids
apc_list
apc_paid
fwci
has_fulltext
cited_by_count
citation_normalized_percentile
cited_by_percentile_year
biblio
is_retracted
is_paratext
is_xpac
primary_topic
topics
keywords
concepts
mesh
locations_count
locations
best_oa_location
sustainable_development_goals
awards
funders
has_content
content_urls
referenced_works_count
referenced_works
related_works
abstract_inverted_index
counts_by_year
updated_date
created_date
```

## Storage Estimate

The first full-record batch has 100 works and is 241,184 compressed bytes.

Approximate compressed size:

```text
2,412 bytes/work * 8,836,615 works ~= 21.3 GB
```

Average raw JSON size in the sample is about 14,991 characters per work, implying roughly 130 GB of uncompressed JSONL before parsing and normalization.

## Runtime Estimate

The pull uses 100 records per page, so the full corpus requires about:

```text
88,367 API pages
```

At roughly 0.7 to 1.5 seconds per page including network time, JSON writing, and the configured 0.2 second sleep, expected runtime is approximately:

```text
17 to 37 hours
```

This is a rough estimate. The script writes a checkpoint after every page, so it can be stopped and resumed.
