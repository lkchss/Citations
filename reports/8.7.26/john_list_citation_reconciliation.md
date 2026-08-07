# John List Citation Reconciliation

Date checked: 2026-08-07 UTC

## Current OpenAlex Author Record

OpenAlex author ID `A5083530241` currently reports 900 works, 46,684
citations, an h-index of 102, and last-known affiliations at both the
University of Chicago and Australian National University. The record also
reports a work in 1903. These features are incompatible with a clean John A.
List profile and strongly indicate that OpenAlex has merged or contaminated
this author entity.

Official API endpoint:
<https://api.openalex.org/authors/A5083530241>

## Local Economics Slice

The local economics subject tables contain:

- 187 work IDs attributed to `A5083530241`;
- 11,977 citations from current work-level `cited_by_count`; and
- 12,030 citations reconstructed from incoming OpenAlex reference links.

The reconstructed and work-level economics totals differ by 53 citations, or
0.44%, so they reconcile closely with each other. The local economics total is
25.7% of the current 46,684-citation OpenAlex author total. This is not evidence
of missing citations in the reconstruction: the values use different and
currently unreliable work universes.

## Conclusion

The local citation reconstruction tracks the local economics work set well.
It does not reproduce the current OpenAlex author total because the local
database is restricted to economics-classified works, the API profile appears
merged, the local portfolio has version duplication, and the two sources may
represent different update vintages.

Before an all-field John List analysis, construct a curated identity crosswalk
using DOI, title, coauthors, affiliations, ORCID, and verified CV records. Do
not use the 900-work author entity as a clean career denominator.
