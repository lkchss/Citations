#!/usr/bin/env python3
"""Normalize hit-panel citations by economics paper age and calendar year."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import duckdb


def write_csv(path: Path, columns: list[str], rows: list[tuple]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer=csv.writer(handle,lineterminator="\n");writer.writerow(columns);writer.writerows(rows)


def svg(rows: list[dict], path: Path, value: str, title: str, ylabel: str) -> None:
    series={}
    colors={"at_risk":"#175cd3","balanced_full_window":"#039855"}
    for row in rows:series.setdefault(row["sample_name"],[]).append((int(row["event_time"]),float(row[value])))
    width,height,left,right,top,bottom=1020,530,92,35,82,70
    points=[p for values in series.values() for p in values];xmin,xmax=min(x for x,_ in points),max(x for x,_ in points)
    ymin=min(0,min(y for _,y in points));ymax=max(y for _,y in points);margin=max((ymax-ymin)*.1,.03);ymin-=margin;ymax+=margin
    sx=lambda x:left+(x-xmin)*(width-left-right)/(xmax-xmin);sy=lambda y:height-bottom-(y-ymin)*(height-top-bottom)/(ymax-ymin)
    grid=[]
    for f in (0,.25,.5,.75,1):
        v=ymin+(ymax-ymin)*f;grid.append(f"<line x1='{left}' y1='{sy(v):.1f}' x2='{width-right}' y2='{sy(v):.1f}' stroke='#e4e7ec'/><text x='{left-9}' y='{sy(v)+4:.1f}' text-anchor='end' font-size='12'>{v:.2f}</text>")
    for e in range(xmin,xmax+1,2):grid.append(f"<text x='{sx(e):.1f}' y='{height-bottom+24}' text-anchor='middle' font-size='11'>{e:+d}</text>")
    paths=[];legend=[]
    labels={"at_risk":"At-risk panel","balanced_full_window":"Balanced -10:+10 cohort"}
    for i,(name,values) in enumerate(series.items()):
        poly=" ".join(f"{sx(x):.1f},{sy(y):.1f}" for x,y in values);color=colors[name]
        paths.append(f"<polyline points='{poly}' fill='none' stroke='{color}' stroke-width='3'/>")
        legend.append(f"<line x1='{left+i*290}' y1='62' x2='{left+28+i*290}' y2='62' stroke='{color}' stroke-width='3'/><text x='{left+36+i*290}' y='66' font-size='12'>{labels[name]}</text>")
    path.write_text(f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='27' text-anchor='middle' font-size='21' font-weight='700'>{title}</text><text x='{width/2}' y='47' text-anchor='middle' font-size='13' fill='#475467'>Expected citations estimated from deduplicated economics works by calendar year, paper age, and type</text>{''.join(legend)}{''.join(grid)}<line x1='{sx(0)}' y1='{top}' x2='{sx(0)}' y2='{height-bottom}' stroke='#b42318' stroke-dasharray='6 5'/>{''.join(paths)}<text x='{width/2}' y='{height-18}' text-anchor='middle' font-size='14'>Event time</text><text transform='translate(20 {height/2}) rotate(-90)' text-anchor='middle' font-size='14'>{ylabel}</text></svg>""",encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--paper-author-year",type=Path,required=True)
    parser.add_argument("--hit-panel",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--temp-directory",type=Path,default=Path("/tmp/citations-normalized-economics"))
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True);args.temp_directory.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect();con.execute("SET threads=6");con.execute("SET memory_limit='10GB'");con.execute("SET temp_directory=?",[str(args.temp_directory)])
    print("building deduplicated economics work-year benchmark",flush=True)
    con.execute("""
      CREATE TEMP TABLE benchmark AS
      WITH work_year AS (
        SELECT work_id, try_cast(year AS INTEGER) AS citation_year,
               try_cast(paper_age AS INTEGER) AS paper_age, any_value(type) AS work_type,
               max(try_cast(citations AS DOUBLE)) AS citations
        FROM read_csv_auto(?, compression='gzip')
        GROUP BY work_id, citation_year, paper_age
      )
      SELECT citation_year,paper_age,work_type,count(*) benchmark_works,
             avg(citations) expected_citations,
             avg((citations>0)::INTEGER) expected_positive_share
      FROM work_year GROUP BY citation_year,paper_age,work_type
    """,[str(args.paper_author_year)])
    print("loading and deduplicating hit panel",flush=True)
    con.execute("""
      CREATE TEMP TABLE hit AS
      SELECT DISTINCT author_id,focal_work_id,hit_work_id,
             try_cast(focal_publication_year AS INTEGER) focal_publication_year,
             focal_type,try_cast(hit_publication_year AS INTEGER) hit_publication_year,
             try_cast(year AS INTEGER) AS calendar_year,try_cast(event_time AS INTEGER) event_time,
             try_cast(years_since_focal_publication AS INTEGER) paper_age,
             try_cast(citations AS DOUBLE) citations
      FROM read_csv_auto(?,compression='gzip')
      WHERE try_cast(event_time AS INTEGER) BETWEEN -10 AND 10
    """,[str(args.hit_panel)])
    print("joining expected citation lifecycle",flush=True)
    con.execute("""
      CREATE TEMP TABLE normalized_base AS
      SELECT h.*,b.benchmark_works,b.expected_citations,
             h.citations-b.expected_citations excess_citations,
             (h.citations+.1)/(b.expected_citations+.1) smoothed_ratio
      FROM hit h JOIN benchmark b
        ON h.calendar_year=b.citation_year AND h.paper_age=b.paper_age AND h.focal_type=b.work_type
      WHERE h.paper_age>=0
    """)
    con.execute("""
      CREATE TEMP TABLE normalized AS
      SELECT *, CASE WHEN count(*) OVER (
        PARTITION BY author_id,focal_work_id,hit_work_id
      )=21 AND min(event_time) OVER (
        PARTITION BY author_id,focal_work_id,hit_work_id
      )=-10 AND max(event_time) OVER (
        PARTITION BY author_id,focal_work_id,hit_work_id
      )=10 THEN 1 ELSE 0 END balanced_full_window
      FROM normalized_base
    """)
    query="""
      WITH samples AS (
        SELECT 'at_risk' AS sample_name,* FROM normalized
        UNION ALL
        SELECT 'balanced_full_window' AS sample_name,* FROM normalized WHERE balanced_full_window=1
      ), author_event AS (
        SELECT sample_name,event_time,author_id,avg(excess_citations) author_mean_excess
        FROM samples GROUP BY sample_name,event_time,author_id
      ), aggregate AS (
        SELECT sample_name,event_time,count(*) observations,count(DISTINCT author_id) authors,
               count(DISTINCT author_id||'|'||focal_work_id||'|'||hit_work_id) units,
               avg(citations) mean_citations,avg(expected_citations) mean_expected_citations,
               avg(excess_citations) mean_excess_citations,
               sum(citations)/nullif(sum(expected_citations),0) observed_expected_ratio,
               avg(smoothed_ratio) mean_smoothed_ratio
        FROM samples GROUP BY sample_name,event_time
      ), uncertainty AS (
        SELECT sample_name,event_time,stddev_samp(author_mean_excess)/sqrt(count(*)) excess_se
        FROM author_event GROUP BY sample_name,event_time
      )
      SELECT a.*,u.excess_se,a.mean_excess_citations-1.96*u.excess_se excess_ci_low,
             a.mean_excess_citations+1.96*u.excess_se excess_ci_high
      FROM aggregate a JOIN uncertainty u USING(sample_name,event_time)
      ORDER BY sample_name,event_time
    """
    result=con.execute(query);columns=[d[0] for d in result.description];records=result.fetchall()
    write_csv(args.output_dir/"normalized_event_time.csv",columns,records)
    dict_rows=[dict(zip(columns,row)) for row in records]
    summary=[]
    for sample in ("at_risk","balanced_full_window"):
        subset=[r for r in dict_rows if r["sample_name"]==sample]
        for metric in ("mean_citations","mean_expected_citations","mean_excess_citations","observed_expected_ratio"):
            pre=sum(float(r[metric]) for r in subset if -5<=r["event_time"]<=-1)/5
            post=sum(float(r[metric]) for r in subset if 0<=r["event_time"]<=4)/5
            summary.append({"sample":sample,"metric":metric,"pre_mean":pre,"post_mean":post,"difference":post-pre})
    write_csv(args.output_dir/"normalized_pre_post_summary.csv",list(summary[0]),[tuple(r.values()) for r in summary])
    svg(dict_rows,args.output_dir/"paper_level_excess_citations.svg","mean_excess_citations","Economics citation prominence: lifecycle-adjusted excess","Observed minus expected annual citations")
    svg(dict_rows,args.output_dir/"paper_level_observed_expected_ratio.svg","observed_expected_ratio","Economics citation prominence: observed/expected ratio","Observed / expected citations")
    stats=con.execute("""SELECT count(*),count(DISTINCT focal_work_id),count(DISTINCT author_id),
      sum(balanced_full_window),count(DISTINCT CASE WHEN balanced_full_window=1 THEN author_id||'|'||focal_work_id||'|'||hit_work_id END),
      count(DISTINCT CASE WHEN balanced_full_window=1 THEN author_id END) FROM normalized""").fetchone();con.close()
    excess={r["sample"]:r for r in summary if r["metric"]=="mean_excess_citations"};ratio={r["sample"]:r for r in summary if r["metric"]=="observed_expected_ratio"}
    metadata={"normalized_rows":stats[0],"focal_works":stats[1],"authors":stats[2],"balanced_row_count":stats[3],"balanced_units":stats[4],"balanced_authors":stats[5],"balanced_event_years":21,"benchmark":"deduplicated economics works grouped by calendar year, paper age, and document type","warning":"Descriptive normalization; benchmark includes treated works and does not create a causal counterfactual."}
    (args.output_dir/"metadata.json").write_text(json.dumps(metadata,indent=2)+"\n")
    (args.output_dir/"README.md").write_text(f"""# Paper-level normalized economics results

This specification uses the recovered 191-million-row author–paper–year panel.
Expected citations are estimated from deduplicated economics works in the same
calendar year, paper age, and document type.

Two samples are reported:

- **At risk:** a focal paper enters only after publication.
- **Balanced full window:** the focal paper was published before event time -10
  and is observed throughout -10:+10.

| Sample | Excess pre | Excess post | Change | O/E pre | O/E post | O/E change |
|---|---:|---:|---:|---:|---:|---:|
| At risk | {excess['at_risk']['pre_mean']:.3f} | {excess['at_risk']['post_mean']:.3f} | {excess['at_risk']['difference']:+.3f} | {ratio['at_risk']['pre_mean']:.3f} | {ratio['at_risk']['post_mean']:.3f} | {ratio['at_risk']['difference']:+.3f} |
| Balanced -10:+10 | {excess['balanced_full_window']['pre_mean']:.3f} | {excess['balanced_full_window']['post_mean']:.3f} | {excess['balanced_full_window']['difference']:+.3f} | {ratio['balanced_full_window']['pre_mean']:.3f} | {ratio['balanced_full_window']['post_mean']:.3f} | {ratio['balanced_full_window']['difference']:+.3f} |

![Lifecycle-adjusted excess citations](paper_level_excess_citations.svg)

![Observed/expected citation ratio](paper_level_observed_expected_ratio.svg)

> **Descriptive, not causal.** The benchmark absorbs normal paper aging,
> calendar-year citation conditions, and document type. It does not solve
> author selection, identity errors, work versions, or differential pretrends.
""",encoding="utf-8")
    print(json.dumps(metadata,indent=2));print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
