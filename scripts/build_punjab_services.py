"""Rebuild checksum-pinned Punjab health and DHA budget observations from official PDFs.

Requires pdfplumber. Run from repository root with python -m scripts.build_punjab_services.
"""
import hashlib
import json
import re
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/curated/punjab_services.json"
NORTH_PAGES = [21,32,44,53,65,74,85,100,127,137,149,166,187,202,225,247,268,276,291]
KINDS = ["hospitals", "dispensaries", "rhcs", "bhus", "tb_clinics", "sh_centers", "mch_centers", "trauma_centers"]
ALIASES = {"bahawalnagar":"bahawalnagar",
 "r.y.khan":"rahim-yar-khan", "rahim yar khan":"rahim-yar-khan", "d.g.khan":"dera-ghazi-khan",
 "d.g. khan":"dera-ghazi-khan", "t. t. singh":"toba-tek-singh", "m. b. din":"mandi-bahauddin"}

def slug(name):
    value = name.strip().lower()
    return ALIASES.get(value, value.replace(" ", "-"))

def number(value):
    value = value.replace(",", "").replace(" ", "")
    if value == "-": return None
    if not re.fullmatch(r"\d+(?:\.\d+)?", value): raise ValueError(value)
    return float(value) if "." in value else int(value)

def main():
    pilot = json.loads((ROOT / "data/curated/districts.json").read_text())
    census = json.loads((ROOT / "data/curated/punjab_census.json").read_text())
    names = {d["slug"]: d["name"] for d in pilot["districts"] + census["districts"]}
    health = json.loads((ROOT / "data/curated/health_capacity_periods.json").read_text())
    h = health["sources"]["punjab_health_statistics_2024"]
    sources = {
      "punjab_health_statistics_2024": dict(publisher=h["publisher"], title=h["title"], period=h["period_label"], url=h["official_url"], local_file=h["local_file"], sha256=h["sha256"]),
      "agp_dha_south_budget_2023_24": {**pilot["sources"]["agp_dha"], "period":"FY 2023-24"},
      "agp_dha_north_budget_2022_23": dict(publisher="Auditor-General of Pakistan", title="Audit Report on District Health Authorities of 19 Districts of Punjab (North), Audit Year 2023-24", period="FY 2022-23", url="https://agp.gov.pk/SiteImage/Policy/03-Comp.%20Audit-DHA%20AY%20(2023-24)-Approved%20by%20AGP.pdf", local_file="data/raw/agp_punjab_north_dha_2023-24.pdf")}
    pinned = json.loads(OUT.read_text())["sources"] if OUT.exists() else {}
    for sid, source in sources.items():
        digest = hashlib.sha256((ROOT/source["local_file"]).read_bytes()).hexdigest()
        expected = pinned.get(sid, source).get("sha256")
        if expected and digest != expected: raise ValueError(f"Checksum mismatch: {sid}")
        source["sha256"] = digest
    records = {s:dict(slug=s,name=n,observations=[]) for s,n in sorted(names.items())}
    def add(s,metric,value,category,sid,page,locator):
        if s not in records: raise ValueError(f"Unknown district {s}")
        records[s]["observations"].append(dict(metric_key=metric,value=value,category=category,
          unit="million_pkr" if metric.endswith("million_pkr") else "count", period="2023-12-31" if category=="health" else sources[sid]["period"],
          source_id=sid,locator=f"{locator}; PDF page {page}; sha256={sources[sid]['sha256']}"))
    sid="punjab_health_statistics_2024"
    # Fixed Table 3 column boundaries; character grouping preserves spaced digits (e.g. 9 9).
    bounds=[172,198,230,260,281,305,334,363,391,413,433,455,476,497,518,540,560]
    seen=set()
    with pdfplumber.open(ROOT/sources[sid]["local_file"]) as pdf:
      for n in range(18,23):
        page=pdf.pages[n]
        if "Table 3" not in page.extract_text(): raise ValueError("Unexpected health table")
        for w in page.extract_words():
          if w["text"] != "District" or w["x0"]>=172 or w["top"]<145: continue
          chars=[c for c in page.chars if abs(c["top"]-w["top"])<1]
          name="".join(c["text"] for c in sorted(chars,key=lambda c:c["x0"]) if c["x0"]<172).replace(" District", "").strip()
          s=slug(name)
          if s in seen: raise ValueError(f"Duplicate district {s}")
          seen.add(s)
          values=[]
          for left,right in zip(bounds,bounds[1:]):
            raw="".join(c["text"] for c in sorted(chars,key=lambda c:c["x0"]) if left<=(c["x0"]+c["x1"])/2<right)
            values.append(number(raw))
          for k,(count,beds) in zip(KINDS,zip(values[::2],values[1::2])):
            for measure,value in [("count",count),("beds",beds)]:
              add(s,f"phs_{k}_{measure}",value,"health",sid,n+1,f"Table 3, {name} District row, {k} {measure}, printed page {n-14}")
    if seen != names.keys(): raise ValueError(f"Incomplete health coverage {names.keys()-seen}")
    for d in health["districts"]:
      period=d["periods"][-1]
      for k,v in period["facilities"].items():
        for m,value in v.items():
          found=next(o["value"] for o in records[d["slug"]]["observations"] if o["metric_key"]==f"phs_{k}_{m}")
          if found!=value: raise ValueError(f"Pilot health mismatch: {d['slug']} {k} {m}: {found} != {value}")
    sid="agp_dha_north_budget_2022_23"
    north=set()
    with pdfplumber.open(ROOT/sources[sid]["local_file"]) as pdf:
      for page in NORTH_PAGES:
        text=pdf.pages[page-1].extract_text()
        name=re.search(r"DISTRICT HEALTH AUTHORITY ([A-Z ]+)",text)[1].strip()
        s=slug(name); north.add(s)
        if "2022-23" not in text or "Final" not in text: raise ValueError("Unexpected budget period/header")
        for label,key in [("Total","total"),("Development","development")]:
          line=next(line for line in text.splitlines() if line.startswith(label+" ") and re.match(r"[\d,]+\.",line.split()[1]))
          cells=line.split()[1:]
          if len(cells)!=6: raise ValueError(line)
          for measure,index in [("budget",3),("expenditure",4)]:
            add(s,f"dha_{key}_{measure}_million_pkr",number(cells[index]),"accountability",sid,page,f"Comments on Budget and Accounts, {name}, {label} row, {measure}, printed page {page-12}")
    sid="agp_dha_south_budget_2023_24"
    south=["bahawalnagar","bahawalpur","chiniot","dera-ghazi-khan","faisalabad","jhang","khanewal","layyah","lodhran","multan","muzaffargarh","pakpattan","rahim-yar-khan","rajanpur","sahiwal","toba-tek-singh","vehari"]
    with pdfplumber.open(ROOT/sources[sid]["local_file"]) as pdf:
      rows=[]
      for n in range(301,304):
        for line in pdf.pages[n].extract_text().splitlines():
          match=re.search(r"(?:^| )(Development|Total) ([\d,]+\.\d+) ([\d,]+\.\d+)",line)
          if match: rows.append((n+1,match))
      for i,s in enumerate(south):
        for j,key in enumerate(["development","total"]):
          page,m=rows[i*2+j]
          if m[1].lower()!=key: raise ValueError("Unexpected South table row order")
          for measure,index in [("budget",2),("expenditure",3)]:
            add(s,f"dha_{key}_{measure}_million_pkr",number(m[index]),"accountability",sid,page,f"Annexure D, {names[s]}, {key} row, {measure}, printed page {page-11}")
    if north & set(south) or north | set(south) != names.keys(): raise ValueError("Budget geography mismatch")
    result=dict(version="punjab-services-v1",sources=sources,limitations=[
      "Health capacity is reported as at 31 December 2023; institutions and beds are not measures of care quality or health outcomes.",
      "Printed health dashes mean nil or insignificant and remain null, not zero.",
      "Budgets cover District Health Authorities only, not all district spending. North: FY 2022-23; South: FY 2023-24. Do not rank these as a common-year series.",
      "Source arithmetic discrepancies and expenditure above budget are preserved; these facts do not extend the fixed ten-district GPIS score cohort."],districts=list(records.values()))
    OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(f"Verified {len(records)} districts, {sum(len(d['observations']) for d in records.values())} observations (including explicit nulls)")

if __name__ == "__main__": main()

