#!/usr/bin/env python3
"""Compare original economics exposure regressions with stronger age controls."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def load(path: Path) -> dict[str, np.ndarray]:
    columns={key:[] for key in ("author_id","work_id","year","age","y","u","r")}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as handle:
        for row in csv.DictReader(handle):
            columns["author_id"].append(row["author_id"]);columns["work_id"].append(row["work_id"])
            columns["year"].append(int(row["year"]));columns["age"].append(int(row["paper_age"]))
            columns["y"].append(float(row["citations_jt"]));columns["u"].append(float(row["accumulated_unrelated_citations_jt"]));columns["r"].append(float(row["accumulated_related_citations_jt"]))
    return {key:np.asarray(value,dtype=object if key in ("author_id","work_id") else np.float64) for key,value in columns.items()}


def encode(values: np.ndarray) -> tuple[np.ndarray,int]:
    _,idx=np.unique(values,return_inverse=True);return idx.astype(np.int32),int(idx.max())+1


def residualize(value: np.ndarray, groups: list[tuple[np.ndarray,int]], tolerance: float=1e-9, max_iter: int=300) -> tuple[np.ndarray,int,float]:
    result=value.astype(np.float64,copy=True);result-=result.mean();iterations=0;gap=math.inf
    counts=[np.bincount(idx,minlength=n) for idx,n in groups]
    for iterations in range(1,max_iter+1):
        gap=0.0
        for (idx,n),count in zip(groups,counts):
            means=np.bincount(idx,weights=result,minlength=n)/count
            result-=means[idx];gap=max(gap,float(np.max(np.abs(means))))
        if gap<tolerance:break
    return result,iterations,gap


def fit(y: np.ndarray, xs: list[np.ndarray], cluster_idx: np.ndarray, clusters: int, absorbed_df: int) -> dict:
    x=np.column_stack(xs);inv=np.linalg.pinv(x.T@x);beta=inv@(x.T@y);error=y-x@beta
    scores=np.zeros((clusters,len(xs)))
    for col in range(len(xs)):scores[:,col]=np.bincount(cluster_idx,weights=x[:,col]*error,minlength=clusters)
    df=max(1,len(y)-absorbed_df-len(xs));correction=(clusters/max(1,clusters-1))*((len(y)-1)/df)
    vcov=correction*inv@(scores.T@scores)@inv;se=np.sqrt(np.maximum(0,np.diag(vcov)))
    p=np.asarray([math.erfc(abs(float(b/s))/math.sqrt(2)) if s else 1 for b,s in zip(beta,se)])
    return {"beta":beta.tolist(),"se":se.tolist(),"p":p.tolist(),"ci_low":(beta-1.96*se).tolist(),"ci_high":(beta+1.96*se).tolist(),"within_r2":1-float(error@error)/float(y@y) if float(y@y) else None}


def differences(data: dict[str,np.ndarray]) -> dict[str,np.ndarray]:
    unit=np.char.add(np.char.add(data["author_id"].astype(str),"|"),data["work_id"].astype(str));order=np.lexsort((data["year"],unit))
    result={key:[] for key in ("work_id","year","age","y","u","r")};previous=None;last={}
    for index in order:
        current=str(unit[index]);year=int(data["year"][index])
        if current==previous and year==last["year"]+1:
            result["work_id"].append(data["work_id"][index]);result["year"].append(year);result["age"].append(int(data["age"][index]))
            for key in ("y","u","r"):result[key].append(float(data[key][index])-last[key])
        previous=current;last={"year":year,**{key:float(data[key][index]) for key in ("y","u","r")}}
    return {key:np.asarray(value,dtype=object if key=="work_id" else np.float64) for key,value in result.items()}


def estimate_variant(name: str,label: str,data: dict[str,np.ndarray],transform: str,group_names: tuple[str,...]) -> dict:
    work_idx,works=encode(data["work_id"]);available={"work":(work_idx,works)}
    for key in ("year","age"):available[key]=encode(data[key])
    groups=[available[key] for key in group_names];absorbed=sum(n for _,n in groups)-max(0,len(groups)-1)
    raw={key:data[key].astype(float) for key in ("y","u","r")}
    if transform=="log1p":raw={key:np.log1p(value) for key,value in raw.items()}
    residuals={};iterations={};gaps={}
    for key,value in raw.items():
        residuals[key],iterations[key],gaps[key]=residualize(value,groups)
    m1=fit(residuals["y"],[residuals["u"]],work_idx,works,absorbed)
    m2=fit(residuals["y"],[residuals["u"],residuals["r"]],work_idx,works,absorbed)
    return {"variant":name,"label":label,"transformation":transform,"absorbed_effects":list(group_names),"rows":len(data["y"]),"works":works,"iterations":iterations,"convergence_gap":gaps,"model1":m1,"model2":m2}


def flatten(results: list[dict]) -> list[dict]:
    rows=[]
    for result in results:
        for model,names in (("model1",("unrelated",)),("model2",("unrelated","related"))):
            estimates=result[model]
            for i,variable in enumerate(names):
                rows.append({"variant":result["variant"],"label":result["label"],"transformation":result["transformation"],"absorbed_effects":"+".join(result["absorbed_effects"]),"model":model,"variable":variable,"coefficient":estimates["beta"][i],"standard_error":estimates["se"][i],"p_value":estimates["p"][i],"ci_low":estimates["ci_low"][i],"ci_high":estimates["ci_high"][i],"within_r2":estimates["within_r2"],"rows":result["rows"],"works":result["works"]})
    return rows


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--input",type=Path,required=True);parser.add_argument("--output-csv",type=Path,required=True);parser.add_argument("--output-json",type=Path,required=True);args=parser.parse_args()
    data=load(args.input);diff=differences(data)
    results=[
        estimate_variant("original_levels","Original: levels with paper and year FE",data,"levels",("work","year")),
        estimate_variant("levels_age_fe","Levels with paper, year, and age FE",data,"levels",("work","year","age")),
        estimate_variant("log1p_age_fe","Log1p outcome/exposures with paper, year, and age FE",data,"log1p",("work","year","age")),
        estimate_variant("first_difference_age_fe","First differences with year and age FE",diff,"levels",("year","age")),
    ]
    rows=flatten(results);args.output_csv.parent.mkdir(parents=True,exist_ok=True)
    with args.output_csv.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
    digest = hashlib.sha256()
    with args.input.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    args.output_json.write_text(
        json.dumps(
            {
                "input_file": args.input.name,
                "input_sha256": digest.hexdigest(),
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"rows":len(data["y"]),"difference_rows":len(diff["y"]),"variants":len(results),"output":str(args.output_csv)},indent=2))


if __name__=="__main__":main()
