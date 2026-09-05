"""Source-scoped health capacity and DHA budget facts; never input to prototype scores."""
import json
from pathlib import Path
from app.schemas import Citation, RetrievedEvidence

FILE_NAME = "punjab_services.json"
VERSION = "punjab-services-v1"
NOTICE = "Census, health-capacity and DHA budget facts are available. GPIS scores still use the fixed ten-district pilot; no score is calculated for this district."
LABELS = {"hospitals":"Hospitals", "dispensaries":"Dispensaries", "rhcs":"Rural Health Centres (RHCs)", "bhus":"Basic Health Units (BHUs)", "tb_clinics":"TB clinics", "sh_centers":"Sub-health centres", "mch_centers":"Maternal and child health centres", "trauma_centers":"Trauma centres"}


def load_services(path):
    file = Path(path).with_name(FILE_NAME)
    return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else None


def profile(observations, sources):
    result = {}
    for category,key in [("health","official_health"),("accountability","official_budget")]:
        rows = [o for o in observations if o["category"] == category]
        if not rows: continue
        latest = max(o["period"] for o in rows)
        rows = [o for o in rows if o["period"] == latest]
        result[key] = dict(period=latest, observations=rows, sources={o["source_id"]:sources[o["source_id"]] for o in rows})
    return result


def label(metric):
    if metric.startswith("phs_"):
        kind,measure = metric[4:].rsplit("_",1)
        return LABELS[kind] + (" beds" if measure == "beds" else "")
    return {"dha_total_budget_million_pkr":"DHA total budget", "dha_total_expenditure_million_pkr":"DHA total expenditure", "dha_development_budget_million_pkr":"DHA development budget", "dha_development_expenditure_million_pkr":"DHA development expenditure"}[metric]


def passage(name, row):
    value = row["value"]
    rendered = "not reported separately (printed dash: nil or insignificant)" if value is None else (f"Rs {value:,.3f} million" if row["unit"]=="million_pkr" else f"{value:,.0f}")
    return f"{label(row['metric_key'])} for {name}: {rendered}; reporting period {row['period']}."


def evidence(record):
    chunks=[]
    for category in ("health","accountability"):
        rows=[o for o in record["observations"] if o["category"]==category]
        if rows:
            chunks.append(dict(id=f"{record['slug']}-services-{category}", category=category, source_id=rows[0]["source_id"], period=rows[0]["period"],
              locator="; ".join(dict.fromkeys(o["locator"] for o in rows)),
              text=" ".join(passage(record["name"],o) for o in rows)+(" Budgets cover the District Health Authority only, not all district spending." if category=="accountability" else " Facility capacity does not measure quality or outcomes.")))
    return chunks


def query_rows(question, record):
    q=question.casefold()
    if any(w in q for w in ("score","rank","thq","dhq","trend","change","previous","last year")): return []
    health=any(w in q for w in ("health","hospital","facilit","bhu","rhc","dispensar","bed","clinic"))
    budget=any(w in q for w in ("budget","expenditure","spent","spending","utilization","lapse"))
    key="official_budget" if budget else "official_health" if health else None
    if not key or key not in record: return []
    rows=record[key]["observations"]
    if budget:
        prefix="dha_development_" if "development" in q else "dha_total_"
        return [o for o in rows if o["metric_key"].startswith(prefix)]
    kinds=[k for k,words in {"bhus":["bhu","basic health"],"rhcs":["rhc","rural health"],"hospitals":["hospital"],"dispensaries":["dispensar"],"tb_clinics":["tb clinic"],"trauma_centers":["trauma"]}.items() if any(w in q for w in words)]
    return [o for o in rows if (not kinds or any(o["metric_key"].startswith(f"phs_{k}_") for k in kinds)) and o["metric_key"].endswith("_beds" if "bed" in q else "_count")]


def fact_search(repository, question, slugs, limit):
    if not any(w in question.casefold() for w in ("health","hospital","facilit","bhu","rhc","dispensar","bed","clinic","budget","expenditure","spent","spending","utilization","lapse")): return []
    results=[]
    for slug in slugs or [d["slug"] for d in repository.list_districts()]:
        record=repository.get_district(slug)
        # Preserve the established, separately defined pilot metrics for specific legacy questions.
        from app.facts import requested_metrics
        if record["score_details"] and requested_metrics(question): continue
        for row in query_rows(question,record):
            source=record["sources"][row["source_id"]]
            eid=f"service-{slug}-{row['metric_key']}-{row['period']}"
            text=passage(record["name"],row)
            if row["category"]=="accountability": text+=" Scope: District Health Authority only."
            results.append(RetrievedEvidence(id=eid,district_slug=slug,district_name=record["name"],category=row["category"],text=text,
              source_id=row["source_id"],locator=row["locator"],period=row["period"],keyword_rank=len(results)+1,
              citation=Citation(evidence_id=eid,source_id=row["source_id"],publisher=source["publisher"],title=source["title"],period=row["period"],url=source["url"],locator=row["locator"],passage=text)))
    return results[:limit]


def seed_services(session, dataset):
    from sqlalchemy import select
    from app.database.models import District, Observation, Source, EvidenceChunk
    from app.database.seed import _upsert
    for sid,source in dataset["sources"].items(): _upsert(session,Source,dict(id=sid,**source),["id"])
    ids=dict(session.execute(select(District.slug,District.id)).all())
    for record in dataset["districts"]:
        did=ids[record["slug"]]
        for row in record["observations"]:
            if row["value"] is None: continue
            values=dict(row,district_id=did,definition_version=VERSION,geography_level="district",comparability_group=None,quality_flags=[],population_basis=None)
            # Existing qualified pilot health rows retain their provenance and comparability group.
            existing=session.scalar(select(Observation).where(Observation.district_id==did,Observation.metric_key==row["metric_key"],Observation.period==row["period"]))
            if existing:
                if float(existing.value)!=row["value"] or existing.source_id!=row["source_id"]: raise ValueError("Conflicting existing service observation")
                continue
            _upsert(session,Observation,values,["district_id","metric_key","period"])
        for chunk in evidence(record): _upsert(session,EvidenceChunk,dict(chunk,district_id=did),["id"])
