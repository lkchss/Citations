#!/usr/bin/env python3
"""Build publication-year/topic matched API controls for four author profiles."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from build_openalex_author_hit_profiles import citation_years, get


AUTHORS = {
    "John A. List": ("A5083530241", "W2030360026", 2003),
    "Michael C. Jensen": ("A5068490503", "W2752617332", 1976),
    "Manuel Arellano": ("A5114113233", "W2025610165", 1991),
    "Robert M. Solow": ("A5001761955", "W2070631858", 1956),
}


def slope(values: list[tuple[int, float]]) -> float:
    xbar=sum(x for x,_ in values)/len(values);ybar=sum(y for _,y in values)/len(values)
    return sum((x-xbar)*(y-ybar) for x,y in values)/sum((x-xbar)**2 for x,_ in values)


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def work_details(ids: list[str], cache: Path) -> dict[str, dict]:
    result = {}
    for start in range(0, len(ids), 50):
        batch = [value.rsplit("/", 1)[-1] for value in ids[start:start+50]]
        payload = get("/works", {"filter":"openalex_id:"+"|".join(batch), "per-page":100,
                                  "select":"id,title,publication_year,type,cited_by_count,primary_topic,authorships"}, cache)
        result.update({row["id"]:row for row in payload["results"]})
    return result


def control_for(work: dict, author_id: str, excluded: set[str], cache: Path) -> dict | None:
    year, work_type = work["publication_year"], work.get("type") or "article"
    topic = (work.get("primary_topic") or {}).get("id", "").rsplit("/", 1)[-1]
    filters = [f"publication_year:{year}", f"type:{work_type}"]
    if topic:
        filters.append(f"primary_topic.id:{topic}")
    payload = get("/works", {"filter":",".join(filters), "sample":25, "seed":int(str(year)+str(len(topic))),
                              "select":"id,title,publication_year,type,cited_by_count,primary_topic,authorships"}, cache)
    candidates=[]
    for candidate in payload["results"]:
        candidate_authors={a["author"]["id"].rsplit("/",1)[-1] for a in candidate.get("authorships") or [] if (a.get("author") or {}).get("id")}
        if candidate["id"] not in excluded and author_id not in candidate_authors:
            candidates.append(candidate)
    if not candidates and topic:
        payload = get("/works", {"filter":f"publication_year:{year},type:{work_type}", "sample":25,
                                  "seed":int(str(year)+"17"), "select":"id,title,publication_year,type,cited_by_count,primary_topic,authorships"}, cache)
        candidates=[c for c in payload["results"] if c["id"] not in excluded]
    return candidates[0] if candidates else None


def svg(rows: list[dict], path: Path, author: str) -> None:
    width,height,left,right,top,bottom=980,500,85,35,75,70
    ymax=max(max(float(r["focal_mean_citations"]),float(r["control_mean_citations"])) for r in rows)*1.12 or 1
    sx=lambda x:left+(x+5)*(width-left-right)/10; sy=lambda y:height-bottom-y*(height-top-bottom)/ymax
    grid=[]
    for f in (0,.25,.5,.75,1):
        v=ymax*f;grid.append(f"<line x1='{left}' y1='{sy(v):.1f}' x2='{width-right}' y2='{sy(v):.1f}' stroke='#e4e7ec'/><text x='{left-8}' y='{sy(v)+4:.1f}' text-anchor='end' font-size='12'>{v:.2f}</text>")
    for e in range(-5,6):grid.append(f"<text x='{sx(e):.1f}' y='{height-bottom+24}' text-anchor='middle' font-size='12'>{e:+d}</text>")
    focal=" ".join(f"{sx(int(r['event_time'])):.1f},{sy(float(r['focal_mean_citations'])):.1f}" for r in rows)
    control=" ".join(f"{sx(int(r['event_time'])):.1f},{sy(float(r['control_mean_citations'])):.1f}" for r in rows)
    path.write_text(f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='28' text-anchor='middle' font-size='21' font-weight='700'>{author}: focal papers and matched controls</text><text x='{width/2}' y='49' text-anchor='middle' font-size='13' fill='#475467'>Controls match publication year, work type, and primary topic where available</text>{''.join(grid)}<line x1='{sx(0)}' y1='{top}' x2='{sx(0)}' y2='{height-bottom}' stroke='#b42318' stroke-dasharray='6 5'/><polyline points='{focal}' fill='none' stroke='#175cd3' stroke-width='3'/><polyline points='{control}' fill='none' stroke='#f79009' stroke-width='3'/><line x1='{left}' y1='65' x2='{left+25}' y2='65' stroke='#175cd3' stroke-width='3'/><text x='{left+32}' y='69' font-size='12'>Author focal papers</text><line x1='{left+180}' y1='65' x2='{left+205}' y2='65' stroke='#f79009' stroke-width='3'/><text x='{left+212}' y='69' font-size='12'>Matched controls</text><text x='{width/2}' y='{height-18}' text-anchor='middle' font-size='14'>Event time</text><text transform='translate(18 {height/2}) rotate(-90)' text-anchor='middle' font-size='14'>Mean annual citations</text></svg>""",encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--reports-root",type=Path,default=Path("reports/8.7.26"))
    parser.add_argument("--output-dir",type=Path,default=Path("reports/8.7.26/author_matched_controls"))
    parser.add_argument("--cache-dir",type=Path,default=Path(".cache/openalex_author_controls"))
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)

    source=defaultdict(list)
    for row in read(args.reports_root/"john_list_case_study/author_works.csv"):
        if row["eligible_unrelated_prior"]=="1":source["John A. List"].append(row["work_id"])
    for row in read(args.reports_root/"author_hit_profiles/eligible_prior_works.csv"):
        source[row["author_name"]].append(row["representative_work_id"])
    all_ids=sorted({wid for values in source.values() for wid in values})
    details=work_details(all_ids,args.cache_dir)
    panel=[];matches=[];summary=[]
    for author,(author_id,hit_id,hit_year) in AUTHORS.items():
        focal_ids=[wid for wid in source[author] if wid in details]
        excluded=set(focal_ids)|{f"https://openalex.org/{hit_id}"}
        focal_histories={wid:citation_years(wid.rsplit("/",1)[-1],args.cache_dir) for wid in focal_ids}
        controls=[]
        for index,wid in enumerate(focal_ids,1):
            control=control_for(details[wid],author_id,excluded,args.cache_dir)
            if not control:continue
            excluded.add(control["id"])
            history=citation_years(control["id"].rsplit("/",1)[-1],args.cache_dir)
            controls.append((control,history))
            matches.append({"author_name":author,"focal_work_id":wid,"focal_title":details[wid]["title"],"control_work_id":control["id"],"control_title":control["title"],"publication_year":details[wid]["publication_year"],"focal_type":details[wid]["type"],"focal_topic":((details[wid].get("primary_topic") or {}).get("display_name") or ""),"control_topic":((control.get("primary_topic") or {}).get("display_name") or "")})
            print(f"{author}: matched {index}/{len(focal_ids)}",flush=True)
        rows=[]
        for event in range(-5,6):
            year=hit_year+event
            focal_mean=sum(h.get(year,0) for h in focal_histories.values())/len(focal_histories)
            control_mean=sum(h.get(year,0) for _,h in controls)/len(controls) if controls else 0
            rows.append({"author_name":author,"hit_year":hit_year,"event_time":event,"year":year,"focal_papers":len(focal_histories),"matched_controls":len(controls),"focal_mean_citations":focal_mean,"control_mean_citations":control_mean,"focal_minus_control":focal_mean-control_mean,"causal":0})
        fpre=sum(r["focal_mean_citations"] for r in rows if r["event_time"]<0)/5;cpre=sum(r["control_mean_citations"] for r in rows if r["event_time"]<0)/5
        fpost=sum(r["focal_mean_citations"] for r in rows if 0<=r["event_time"]<=4)/5;cpost=sum(r["control_mean_citations"] for r in rows if 0<=r["event_time"]<=4)/5
        pre_rows=[r for r in rows if r["event_time"]<0]
        fslope=slope([(r["event_time"],r["focal_mean_citations"]) for r in pre_rows]);cslope=slope([(r["event_time"],r["control_mean_citations"]) for r in pre_rows])
        summary.append({"author_name":author,"focal_papers":len(focal_histories),"matched_controls":len(controls),"focal_pre":fpre,"focal_post":fpost,"control_pre":cpre,"control_post":cpost,"focal_change":fpost-fpre,"control_change":cpost-cpre,"difference_in_changes":(fpost-fpre)-(cpost-cpre),"focal_pretrend_slope":fslope,"control_pretrend_slope":cslope,"pretrend_slope_gap":fslope-cslope,"parallel_pretrend_flag":int(abs(fslope-cslope)<.1),"causal":0})
        panel.extend(rows);svg(rows,args.output_dir/(author.lower().replace(" ","_").replace(".","")+"_matched.svg"),author)
    for name,records in (("matched_control_summary.csv",summary),("matched_control_event_time.csv",panel),("matched_pairs.csv",matches)):
        with (args.output_dir/name).open("w",encoding="utf-8",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(records[0]),lineterminator="\n");writer.writeheader();writer.writerows(records)
    table="\n".join(f"| {r['author_name']} | {r['focal_papers']} | {r['focal_change']:+.3f} | {r['control_change']:+.3f} | {r['difference_in_changes']:+.3f} | {r['pretrend_slope_gap']:+.3f} | {'yes' if r['parallel_pretrend_flag'] else 'no'} |" for r in summary)
    figures="\n\n".join(f"![{name} matched-control profile]({name.lower().replace(' ','_').replace('.','')}_matched.svg)" for name in AUTHORS)
    (args.output_dir/"README.md").write_text(f"""# API-derived author matched controls

Each focal paper is paired to one randomly sampled OpenAlex control with the
same publication year and work type, and the same primary topic when available.
Annual outcomes count citing works by publication year. The table compares
event -5:-1 with 0:+4.

| Author | Focal papers | Focal change | Control change | Difference in changes | Pretrend slope gap | Parallel flag |
|---|---:|---:|---:|---:|---:|---|
{table}

> **Exploratory, not causal.** Matching does not yet enforce pre-trend balance;
> OpenAlex identities and work versions remain imperfect, and one control per
> focal paper produces sampling noise.

{figures}
""",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
