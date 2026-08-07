#!/usr/bin/env python3
"""Build API-based exploratory hit-author profiles without the local SSD."""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


API = "https://api.openalex.org"


def get(endpoint: str, params: dict, cache: Path) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    key = urllib.parse.urlencode(sorted((key, str(value)) for key, value in params.items()), safe="|,:")
    digest = hashlib.sha256((endpoint + "?" + key).encode()).hexdigest()[:20]
    target = cache / (endpoint.strip("/").replace("/", "_") + "_" + digest + ".json")
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    url = API + endpoint + "?" + urllib.parse.urlencode(params, safe="|,:")
    request = urllib.request.Request(url, headers={"User-Agent":"citations-author-profiles/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
            target.write_text(json.dumps(payload), encoding="utf-8")
            time.sleep(.12)
            return payload
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def works_for_author(author_id: str, cache: Path) -> list[dict]:
    cursor, records = "*", []
    while cursor:
        payload = get("/works", {"filter":f"author.id:{author_id}", "per-page":200, "cursor":cursor,
                                  "select":"id,title,publication_year,type,cited_by_count,doi,authorships"}, cache)
        records.extend(payload["results"])
        cursor = payload["meta"].get("next_cursor") if payload["results"] else None
    return records


def citation_years(work_id: str, cache: Path) -> dict[int, int]:
    payload = get("/works", {"filter":f"cites:{work_id}", "group_by":"publication_year", "per-page":200}, cache)
    return {int(row["key"]):int(row["count"]) for row in payload.get("group_by", []) if row.get("key")}


def normalized_title(value: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").casefold()))


def cluster_works(works: list[dict]) -> list[list[dict]]:
    """Cluster obvious versions conservatively, retaining uncertain variants."""
    clusters: list[list[dict]] = []
    for work in sorted(works, key=lambda row: (-int(row.get("cited_by_count") or 0), row["id"])):
        title = normalized_title(work.get("title"))
        doi = (work.get("doi") or "").casefold()
        match = None
        for cluster in clusters:
            representative = cluster[0]
            rep_title = normalized_title(representative.get("title"))
            rep_doi = (representative.get("doi") or "").casefold()
            same_doi = bool(doi and rep_doi and doi == rep_doi)
            same_year = abs(int(work["publication_year"]) - int(representative["publication_year"])) <= 1
            similar_title = same_year and difflib.SequenceMatcher(None, title, rep_title).ratio() >= .90
            if same_doi or similar_title:
                match = cluster
                break
        (match if match is not None else clusters.append([work]))
        if match is not None:
            match.append(work)
    return clusters


def svg(rows: list[dict], path: Path, name: str, hit_year: int) -> None:
    width, height, left, right, top, bottom = 980, 500, 85, 35, 68, 70
    values = [float(row["mean_citations"]) for row in rows]
    ymax = max(values + [1]) * 1.12
    sx = lambda event: left + (event + 10) * (width-left-right) / 20
    sy = lambda value: height-bottom-value*(height-top-bottom)/ymax
    grid = []
    for value in (0, ymax*.25, ymax*.5, ymax*.75, ymax):
        grid.append(f"<line x1='{left}' y1='{sy(value):.1f}' x2='{width-right}' y2='{sy(value):.1f}' stroke='#e4e7ec'/><text x='{left-10}' y='{sy(value)+4:.1f}' text-anchor='end' font-size='12'>{value:.1f}</text>")
    for event in range(-10, 11, 2):
        grid.append(f"<text x='{sx(event):.1f}' y='{height-bottom+25}' text-anchor='middle' font-size='12'>{event:+d}</text>")
    points = " ".join(f"{sx(int(row['event_time'])):.1f},{sy(float(row['mean_citations'])):.1f}" for row in rows)
    path.write_text(f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' role='img'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='28' text-anchor='middle' font-size='21' font-weight='700'>{name}: citations to older unrelated papers</text><text x='{width/2}' y='50' text-anchor='middle' font-size='13' fill='#475467'>OpenAlex API citing-work years; fixed pre-{hit_year} cohort</text>{''.join(grid)}<line x1='{sx(0)}' y1='{top}' x2='{sx(0)}' y2='{height-bottom}' stroke='#b42318' stroke-dasharray='6 5'/><polyline points='{points}' fill='none' stroke='#175cd3' stroke-width='3'/><text x='{width/2}' y='{height-18}' text-anchor='middle' font-size='14'>Years relative to candidate-hit publication</text><text transform='translate(18 {height/2}) rotate(-90)' text-anchor='middle' font-size='14'>Mean annual citations</text></svg>""", encoding="utf-8")


def comparison_svg(rows: list[dict], path: Path) -> None:
    width, height, left, top = 980, 470, 245, 75
    plot_width, group_height = 650, 110
    items = []
    for index, row in enumerate(rows):
        y = top + index * group_height
        econ = float(row["local_economics_hit_share"])
        live = float(row["live_all_field_hit_share"])
        items.append(f"<text x='{left-14}' y='{y+30}' text-anchor='end' font-size='14'>{html.escape(row['openalex_name'])}</text><rect x='{left}' y='{y+5}' width='{econ*plot_width}' height='24' fill='#175cd3'/><rect x='{left}' y='{y+36}' width='{live*plot_width}' height='24' fill='#f79009'/><text x='{left+econ*plot_width+7}' y='{y+22}' font-size='12'>{econ:.1%}</text><text x='{left+live*plot_width+7}' y='{y+53}' font-size='12'>{live:.1%}</text>")
    threshold = left + .5 * plot_width
    path.write_text(f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' role='img'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='28' text-anchor='middle' font-size='21' font-weight='700'>Candidate-hit share depends on the denominator</text><text x='{width/2}' y='49' text-anchor='middle' font-size='13' fill='#475467'>Economics-only snapshot versus live all-field OpenAlex author total</text><line x1='{threshold}' y1='{top-12}' x2='{threshold}' y2='{top+3*group_height-30}' stroke='#b42318' stroke-dasharray='6 5'/><text x='{threshold+6}' y='{top-18}' fill='#b42318' font-size='12'>50% threshold</text>{''.join(items)}<rect x='{left}' y='{height-55}' width='20' height='14' fill='#175cd3'/><text x='{left+28}' y='{height-43}' font-size='12'>Local economics portfolio</text><rect x='{left+260}' y='{height-55}' width='20' height='14' fill='#f79009'/><text x='{left+288}' y='{height-43}' font-size='12'>Live all-field author entity</text></svg>""", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/openalex_author_profiles"))
    parser.add_argument("--authors", nargs="+", default=["Michael C. Jensen", "Manuel Arellano", "Robert M. Solow"])
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with args.shortlist.open(encoding="utf-8", newline="") as handle:
        candidates = {row["author_name"]:row for row in csv.DictReader(handle) if row["author_name"] in args.authors}
    if set(candidates) != set(args.authors):
        raise SystemExit(f"missing candidates: {set(args.authors)-set(candidates)}")

    summary, all_event, all_works = [], [], []
    for requested_name in args.authors:
        candidate = candidates[requested_name]
        author_short = candidate["author_id"].rsplit("/", 1)[-1]
        hit_short = candidate["hit_work_id"].rsplit("/", 1)[-1]
        author = get(f"/authors/{author_short}", {"select":"id,display_name,works_count,cited_by_count,last_known_institutions"}, args.cache_dir)
        hit = get(f"/works/{hit_short}", {"select":"id,title,publication_year,cited_by_count,referenced_works,authorships"}, args.cache_dir)
        works = works_for_author(author_short, args.cache_dir)
        hit_year = int(hit["publication_year"])
        references = set(hit.get("referenced_works") or [])
        raw_prior = [work for work in works if work.get("publication_year") and int(work["publication_year"]) < hit_year and work["id"] not in references]
        clusters = cluster_works(raw_prior)
        prior = [cluster[0] for cluster in clusters]
        annual = defaultdict(int)
        for index, (work, cluster) in enumerate(zip(prior, clusters), 1):
            years = citation_years(work["id"].rsplit("/", 1)[-1], args.cache_dir)
            for year, count in years.items():
                annual[year] += count
            all_works.append({"author_id":author["id"], "author_name":author["display_name"], "representative_work_id":work["id"], "title":work["title"], "publication_year":work["publication_year"], "current_citations":work["cited_by_count"], "version_cluster_size":len(cluster), "cluster_member_ids":"|".join(item["id"] for item in cluster), "hit_cites_work":0})
            print(f"{requested_name}: citation history {index}/{len(prior)}", flush=True)
        event_rows = []
        for event in range(-10, 11):
            year = hit_year + event
            row = {"author_id":author["id"], "author_name":author["display_name"], "hit_work_id":hit["id"], "hit_year":hit_year, "event_time":event, "year":year, "eligible_prior_papers":len(prior), "total_citations":annual.get(year, 0), "mean_citations":annual.get(year, 0)/len(prior) if prior else 0, "causal":0}
            event_rows.append(row); all_event.append(row)
        pre = sum(row["mean_citations"] for row in event_rows if -5 <= row["event_time"] <= -1)/5
        post = sum(row["mean_citations"] for row in event_rows if 0 <= row["event_time"] <= 4)/5
        live_hit_share = hit["cited_by_count"] / author["cited_by_count"] if author["cited_by_count"] else 0
        summary.append({"author_id":author["id"], "requested_name":requested_name, "openalex_name":author["display_name"], "openalex_works":author["works_count"], "openalex_citations":author["cited_by_count"], "candidate_hit_id":hit["id"], "candidate_hit_title":hit["title"], "hit_year":hit_year, "live_hit_citations":hit["cited_by_count"], "live_all_field_hit_share":live_hit_share, "local_economics_citations":candidate["economics_portfolio_citations"], "local_economics_hit_share":candidate["hit_share"], "raw_prior_unrelated_records":len(raw_prior), "eligible_prior_unrelated_clusters":len(prior), "pre_mean_minus5_minus1":pre, "post_mean_0_4":post, "raw_difference":post-pre, "baseline_big_hit_all_field":int(live_hit_share>.5 and author["cited_by_count"]>=100), "causal":0, "identity_status":"requires_manual_review"})
        slug = requested_name.lower().replace(" ", "_").replace(".", "")
        svg(event_rows, args.output_dir/f"{slug}_event_time.svg", author["display_name"], hit_year)

    for filename, rows in (("author_hit_profiles.csv", summary), ("author_hit_event_time.csv", all_event), ("eligible_prior_works.csv", all_works)):
        with (args.output_dir/filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    comparison_svg(summary, args.output_dir/"hit_share_denominator_comparison.svg")
    table = "".join(f"<tr><td>{html.escape(row['openalex_name'])}</td><td>{row['hit_year']}</td><td>{float(row['local_economics_hit_share']):.1%}</td><td>{row['live_all_field_hit_share']:.1%}</td><td>{row['eligible_prior_unrelated_clusters']}</td><td>{row['pre_mean_minus5_minus1']:.3f}</td><td>{row['post_mean_0_4']:.3f}</td><td>{row['raw_difference']:+.3f}</td></tr>" for row in summary)
    report = f"""<!doctype html><html><head><meta charset='utf-8'><title>Economics author hit profiles</title><style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#182230}}.warning{{background:#fffaeb;padding:14px;border-left:5px solid #f79009}}table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;border-bottom:1px solid #ddd;text-align:right}}th:first-child,td:first-child{{text-align:left}}img{{width:100%}}</style></head><body><h1>Jensen, Arellano, and Solow: exploratory hit profiles</h1><p class='warning'><strong>Descriptive and provisional.</strong> Live OpenAlex author entities contain identity errors and work versions. The event series use fixed, version-clustered cohorts of attributed older works not referenced by the candidate hit. They are not causal estimates.</p><img src='hit_share_denominator_comparison.svg' alt='Hit share denominator comparison'><table><thead><tr><th>Author</th><th>Hit year</th><th>Economics share</th><th>All-field share</th><th>Prior clusters</th><th>Pre mean</th><th>Post mean</th><th>Difference</th></tr></thead><tbody>{table}</tbody></table><h2>Author event figures</h2><img src='michael_c_jensen_event_time.svg'><img src='manuel_arellano_event_time.svg'><img src='robert_m_solow_event_time.svg'><h2>Identity warnings</h2><ul><li>Arellano's entity includes a 1912 geography record, an obvious namesake error.</li><li>Jensen's attributed pre-hit portfolio includes duplicated versions and a likely namesake record.</li><li>Version clustering is conservative and does not establish author identity.</li></ul></body></html>"""
    (args.output_dir/"author_hit_profiles.html").write_text(report, encoding="utf-8")
    (args.output_dir/"README.md").write_text("""# API-based author hit profiles

Exploratory profiles for Michael Jensen, Manuel Arellano, and Robert Solow,
built from the live OpenAlex API without the external SSD. Start with
`author_hit_profiles.csv` for headline results, `author_hit_event_time.csv` for
tidy event series, and `author_hit_profiles.html` for the figures.

The script clusters obvious versions using DOI or highly similar titles within
one publication year. It does not solve OpenAlex author-identity errors. All
pre/post differences are descriptive and must not be interpreted causally.
""", encoding="utf-8")
    provenance = {"generated_at":datetime.now(timezone.utc).isoformat(), "source":"live OpenAlex API", "method":"fixed cohort of all attributed pre-hit works absent from hit references; citing-work counts grouped by publication year", "warning":"Author identities and work versions are not validated. Results are descriptive and API-vintage dependent.", "authors":len(summary), "event_rows":len(all_event), "prior_works":len(all_works)}
    (args.output_dir/"provenance.json").write_text(json.dumps(provenance, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
