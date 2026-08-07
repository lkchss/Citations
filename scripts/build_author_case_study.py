#!/usr/bin/env python3
"""Build a portable exploratory author citation-spillover case study."""

from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import sys
from collections import defaultdict
from pathlib import Path


def rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(path: Path, records: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def line_svg(points: list[tuple[int, float]], event_year: int, title: str,
             secondary_year: int | None = None, band_end: int | None = None) -> str:
    width, height, left, right, top, bottom = 980, 480, 80, 30, 55, 70
    if not points:
        return "<svg xmlns='http://www.w3.org/2000/svg' width='980' height='480'></svg>"
    xs, ys = zip(*points)
    xmin, xmax = min(xs), max(xs)
    ymax = max(max(ys), 1)
    x = lambda value: left + (value - xmin) * (width - left - right) / max(xmax - xmin, 1)
    y = lambda value: height - bottom - value * (height - top - bottom) / ymax
    poly = " ".join(f"{x(a):.1f},{y(b):.1f}" for a, b in points)
    ticks = []
    for year in range((xmin // 5) * 5, xmax + 1, 5):
        ticks.append(f"<line x1='{x(year):.1f}' y1='{height-bottom}' x2='{x(year):.1f}' y2='{height-bottom+6}' stroke='#333'/><text x='{x(year):.1f}' y='{height-bottom+24}' text-anchor='middle' font-size='12'>{year}</text>")
    for frac in (0, .25, .5, .75, 1):
        val = ymax * frac
        ticks.append(f"<line x1='{left}' y1='{y(val):.1f}' x2='{width-right}' y2='{y(val):.1f}' stroke='#ddd'/><text x='{left-10}' y='{y(val)+4:.1f}' text-anchor='end' font-size='12'>{val:.1f}</text>")
    band = "" if band_end is None else f"<rect x='{x(event_year):.1f}' y='{top}' width='{max(x(band_end)-x(event_year),0):.1f}' height='{height-top-bottom}' fill='#fef0c7' opacity='.45'/><text x='{(x(event_year)+x(band_end))/2:.1f}' y='{top+32}' text-anchor='middle' fill='#93370d' font-size='12'>breakthrough cluster</text>"
    event = f"{band}<line x1='{x(event_year):.1f}' y1='{top}' x2='{x(event_year):.1f}' y2='{height-bottom}' stroke='#b42318' stroke-width='2' stroke-dasharray='7 5'/><text x='{x(event_year)+6:.1f}' y='{top+15}' fill='#b42318' font-size='12'>candidate publication</text>"
    if secondary_year is not None:
        event += f"<line x1='{x(secondary_year):.1f}' y1='{top}' x2='{x(secondary_year):.1f}' y2='{height-bottom}' stroke='#6941c6' stroke-width='2' stroke-dasharray='3 4'/><text x='{x(secondary_year)+6:.1f}' y='{height-bottom-10}' fill='#6941c6' font-size='12'>Chicago move</text>"
    return f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' role='img'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='26' text-anchor='middle' font-size='18' font-weight='bold'>{html.escape(title)}</text>{''.join(ticks)}{event}<polyline points='{poly}' fill='none' stroke='#175cd3' stroke-width='3'/><line x1='{left}' y1='{height-bottom}' x2='{width-right}' y2='{height-bottom}' stroke='#333'/><line x1='{left}' y1='{top}' x2='{left}' y2='{height-bottom}' stroke='#333'/><text x='{width/2}' y='{height-18}' text-anchor='middle' font-size='14'>Calendar year</text><text transform='translate(18 {height/2}) rotate(-90)' text-anchor='middle' font-size='14'>Annual citations</text></svg>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-id", required=True)
    parser.add_argument("--author-name", required=True)
    parser.add_argument("--subject-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    def progress(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    table_dir = args.subject_dir / "tables_parts"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    authorships: dict[str, dict] = {}
    author_files = sorted(table_dir.glob("part_*_work_authors.csv.gz"))
    progress(f"scan_authors files={len(author_files)}")
    for index, path in enumerate(author_files, 1):
        for row in rows(path):
            if row["author_id"] == args.author_id:
                authorships[row["work_id"]] = row
        progress(f"scan_authors progress={index}/{len(author_files)} matches={len(authorships)}")
    work_ids = set(authorships)
    if not work_ids:
        raise SystemExit(f"No works found for {args.author_id}")

    works: dict[str, dict] = {}
    work_files = sorted(table_dir.glob("part_*_works.csv.gz"))
    progress(f"scan_works files={len(work_files)} author_works={len(work_ids)}")
    for index, path in enumerate(work_files, 1):
        for row in rows(path):
            if row["work_id"] in work_ids:
                works[row["work_id"]] = row
        progress(f"scan_works progress={index}/{len(work_files)} matches={len(works)}")
    missing_metadata = sorted(work_ids - works.keys())
    total_citations = sum(int(row["cited_by_count"] or 0) for row in works.values())
    ranked = sorted(works.values(), key=lambda row: int(row["cited_by_count"] or 0), reverse=True)
    hit = ranked[0]
    hit_id = hit["work_id"]
    hit_year = int(hit["publication_year"])
    hit_citations = int(hit["cited_by_count"] or 0)
    hit_share = hit_citations / total_citations if total_citations else 0

    cited_by_hit: set[str] = set()
    prior_output = args.output_dir / "author_works.csv"
    prior_provenance = args.output_dir / "provenance.json"
    can_reuse = prior_output.exists() and prior_provenance.exists()
    if can_reuse and json.loads(prior_provenance.read_text(encoding="utf-8")).get("hit_work_id") == hit_id:
        with prior_output.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["hit_cites_focal"] == "1":
                    cited_by_hit.add(row["work_id"])
        progress(f"reuse_author_hit_relations matches={len(cited_by_hit)}")
    else:
        reference_files = sorted(table_dir.glob("part_*_work_references.csv.gz"))
        progress(f"scan_references files={len(reference_files)} hit={hit_id}")
        for index, path in enumerate(reference_files, 1):
            for row in rows(path):
                if row["work_id"] == hit_id:
                    cited_by_hit.add(row["referenced_work_id"])
            progress(f"scan_references progress={index}/{len(reference_files)} matches={len(cited_by_hit)}")

    annual: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    calculated = args.subject_dir / "calculated_citations" / "calculated_citations_by_year.csv.gz"
    progress(f"scan_calculated_citations file={calculated}")
    for row in rows(calculated):
        if row["work_id"] in work_ids:
            annual[row["work_id"]][int(row["year"])] += int(row["calculated_citations"])

    portfolio = []
    eligible_ids = set()
    for rank, row in enumerate(ranked, 1):
        wid = row["work_id"]
        year = int(row["publication_year"])
        citations = int(row["cited_by_count"] or 0)
        prior = year < hit_year
        related = wid in cited_by_hit
        eligible = prior and not related
        if eligible:
            eligible_ids.add(wid)
        portfolio.append({
            "citation_rank": rank, "work_id": wid, "title": row["title"],
            "publication_year": year, "type": row["type"],
            "cited_by_count": citations,
            "portfolio_citation_share": citations / total_citations if total_citations else 0,
            "author_position": authorships[wid]["author_position"],
            "is_top_hit_candidate": int(wid == hit_id), "hit_cites_focal": int(related),
            "eligible_unrelated_prior": int(eligible),
        })

    variants = []
    for share_threshold in (.40, .50, .60):
        for min_total in (50, 100, 250, 500):
            variants.append({"share_threshold": share_threshold, "minimum_author_citations": min_total,
                             "qualifies": int(hit_share > share_threshold and total_citations >= min_total)})

    min_year = min(int(row["publication_year"]) for row in works.values())
    max_citation_year = max((year for wid in annual for year in annual[wid]), default=hit_year)
    start, end = max(min_year, hit_year - 15), min(max_citation_year, hit_year + 15)
    event_rows = []
    paper_year_rows = []
    for year in range(start, end + 1):
        at_risk = [wid for wid in eligible_ids if int(works[wid]["publication_year"]) <= year]
        values = [annual[wid].get(year, 0) for wid in at_risk]
        total = sum(values)
        event_rows.append({"year": year, "event_time": year-hit_year, "eligible_papers": len(values),
                           "total_citations": total, "mean_citations": total/len(values) if values else 0,
                           "median_citations": sorted(values)[len(values)//2] if values else 0,
                           "zero_share": sum(v == 0 for v in values)/len(values) if values else 0})
        for wid in sorted(at_risk):
            paper_year_rows.append({"work_id": wid, "title": works[wid]["title"],
                                    "publication_year": int(works[wid]["publication_year"]),
                                    "year": year, "event_time": year-hit_year,
                                    "citations": annual[wid].get(year, 0)})

    pre_rows = [row for row in event_rows if -5 <= row["event_time"] <= -1]
    post_rows = [row for row in event_rows if 0 <= row["event_time"] <= 4]
    pre_mean = sum(row["mean_citations"] for row in pre_rows) / len(pre_rows) if pre_rows else 0
    post_mean = sum(row["mean_citations"] for row in post_rows) / len(post_rows) if post_rows else 0

    write_csv(args.output_dir / "author_works.csv", portfolio, list(portfolio[0]))
    write_csv(args.output_dir / "hit_variants.csv", variants, list(variants[0]))
    write_csv(args.output_dir / "event_time.csv", event_rows, list(event_rows[0]))
    write_csv(args.output_dir / "paper_year.csv", paper_year_rows, list(paper_year_rows[0]))
    contributions = []
    for wid in eligible_ids:
        baseline = annual[wid].get(2002, 0)
        later_average = sum(annual[wid].get(year, 0) for year in (2007, 2008, 2009)) / 3
        contributions.append({"work_id": wid, "title": works[wid]["title"],
                              "publication_year": int(works[wid]["publication_year"]),
                              "citations_2002": baseline, "mean_citations_2007_2009": later_average,
                              "change": later_average - baseline})
    contributions.sort(key=lambda row: row["change"], reverse=True)
    write_csv(args.output_dir / "paper_contributions.csv", contributions, list(contributions[0]))
    balanced_rows = [r for r in event_rows if hit_year-1 <= r["year"] <= hit_year+10]
    svg = line_svg([(r["year"], r["mean_citations"]) for r in balanced_rows], hit_year,
                   f"{args.author_name}: mean citations to 49 unrelated prior papers",
                   secondary_year=2005 if args.author_id.endswith("A5083530241") else None,
                   band_end=2006 if args.author_id.endswith("A5083530241") else None)
    (args.output_dir / "unrelated_prior_citations.svg").write_text(svg, encoding="utf-8")

    clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
    top_rows = "\n".join(f"| {r['citation_rank']} | {clean(r['title'])} | {r['publication_year']} | {r['cited_by_count']:,} | {r['portfolio_citation_share']:.1%} | {'yes' if r['eligible_unrelated_prior'] else 'no'} |" for r in portfolio[:20])
    warning = "" if hit_share > .5 else "> **Baseline diagnostic:** The top paper does not exceed 50% of this economics-portfolio citation denominator, so this author is not treated under the baseline definition.\n\n"
    fixed = {r["year"]: r["mean_citations"] for r in event_rows if r["eligible_papers"] == len(eligible_ids)}
    initial = sum(fixed.get(y, 0) for y in (2003, 2004))/2
    chicago = sum(fixed.get(y, 0) for y in (2005, 2006))/2
    later = sum(fixed.get(y, 0) for y in (2007, 2008, 2009))/3
    total_growth = sum(row["change"] for row in contributions)
    concentration = {n: sum(row["change"] for row in contributions[:n]) / total_growth
                     if total_growth else 0 for n in (1, 5, 10)}
    contribution_rows = "\n".join(f"| {clean(row['title'])} | {row['publication_year']} | {row['citations_2002']:.1f} | {row['mean_citations_2007_2009']:.1f} | {row['change']:+.1f} |" for row in contributions[:10])
    report = f"""# {args.author_name}: exploratory citation-spillover case study

OpenAlex author: `{args.author_id}`. Descriptive output; not a causal estimate.

{warning}- Economics works: **{len(works)}**
- Economics-portfolio citations: **{total_citations:,}**
- Top-paper share: **{hit_share:.1%}**
- Unrelated prior papers: **{len(eligible_ids)}**

## Fixed-cohort timeline

Using the same 49 papers throughout: 2002 baseline **{fixed.get(2002,0):.2f}**;
2003–04 **{initial:.2f}**; 2005–06 **{chicago:.2f}**; 2007–09
**{later:.2f}** mean annual citations per paper. The pattern is gradual and
cannot separate the publication cluster from the 2005 Chicago move.

![Citation time series](unrelated_prior_citations.svg)

## Where the increase comes from

The top 1, 5, and 10 focal papers account for {concentration[1]:.1%},
{concentration[5]:.1%}, and {concentration[10]:.1%} of the net increase from
2002 to the 2007–09 average.

| Prior paper | Year | 2002 | 2007–09 mean | Change |
|---|---:|---:|---:|---:|
{contribution_rows}

## Candidate hit

**{clean(hit['title'])}** ({hit_year}), {hit_citations:,} citations.
“Unrelated” means this candidate does not cite the prior focal paper.

## Top portfolio works

| Rank | Title | Year | Citations | Share | Eligible focal |
|---:|---|---:|---:|---:|---|
{top_rows}

## Data notes

- Annual outcomes use reconstructed economics citations from OpenAlex reference links.
- Portfolio shares are economics-only, not an all-field career denominator.
- The headline timeline begins in 2002, when all 49 focal papers are published.
- Same-year and post-hit papers are excluded.
- All citations, including later self-citations, are counted.
- OpenAlex may contain article/preprint versions requiring deduplication.
"""
    (args.output_dir / "john_list_case_study.md").write_text(report, encoding="utf-8")
    provenance = {"author_id": args.author_id, "author_name": args.author_name, "subject_dir": str(args.subject_dir),
                  "citation_source": str(calculated), "works": len(works), "missing_work_metadata": missing_metadata,
                  "portfolio_citations": total_citations, "hit_work_id": hit_id, "hit_year": hit_year,
                  "hit_share": hit_share, "eligible_unrelated_prior_papers": len(eligible_ids),
                  "fixed_cohort_mean_2002": fixed.get(2002, 0),
                  "fixed_cohort_mean_2003_2004": initial,
                  "fixed_cohort_mean_2005_2006": chicago,
                  "fixed_cohort_mean_2007_2009": later,
                  "growth_concentration_top_1": concentration[1],
                  "growth_concentration_top_5": concentration[5],
                  "growth_concentration_top_10": concentration[10]}
    (args.output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    progress(f"complete output={args.output_dir}")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
