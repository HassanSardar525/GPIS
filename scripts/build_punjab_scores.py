"""Rebuild the 36-district scoring contract from registered official sources."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import pdfplumber

from app.ingest_official_data import CONFIG, extract
from app.punjab_data import extract_education

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/curated/punjab_districts.json"
NORTH_FILE = ROOT / "data/raw/agp_punjab_north_dha_2024-25.pdf"
NORTH_HASH = "e0e567d66ba77c993c1ad6ece3cf704c978790eb1b69efeff4e58e4a992cf713"
NORTH_ID = "agp_dha_north_budget_2023_24"
# Printed chapter introduction pages; PDF page = printed page + 18.
NORTH_PAGES = dict(gujranwala=7, gujrat=16, hafizabad=32,
    **{"mandi-bahauddin":39, "nankana-sahib":129}, narowal=56, sialkot=69,
    kasur=82, lahore=98, okara=142, sheikhupura=161, attock=183,
    chakwal=200, jhelum=225, rawalpindi=238, bhakkar=252, khushab=261,
    mianwali=270, sargodha=281)


def north_budget():
    if hashlib.sha256(NORTH_FILE.read_bytes()).hexdigest() != NORTH_HASH:
        raise ValueError("North audit checksum mismatch")
    result = {}
    with pdfplumber.open(NORTH_FILE) as pdf:
        for slug, printed in NORTH_PAGES.items():
            page = printed + 18
            text = pdf.pages[page - 1].extract_text()
            assert "DISTRICT HEALTH AUTHORITY" in text and "2023-24" in text
            assert "Final" in text and "Surrender" in text and "million" in text
            rows = []
            for label, kind in (("Total", "total"), ("Development", "development")):
                matches = [line for line in text.splitlines() if line.startswith(label + " ")]
                if len(matches) != 1:
                    raise ValueError(f"Ambiguous {slug} {label} row: {matches}")
                cells = matches[0].split()[1:]
                if len(cells) != 6:
                    raise ValueError(f"Unexpected columns: {matches[0]}")
                for measure, index in (("budget", 3), ("expenditure", 4)):
                    raw = cells[index]
                    if not re.fullmatch(r"[\d,]+(?:\.\d+)?", raw):
                        raise ValueError(f"Non-numeric scoring cell {slug}: {raw}")
                    rows.append(dict(metric_key=f"dha_{kind}_{measure}_million_pkr",
                        value=float(raw.replace(",", "")), category="accountability",
                        unit="million_pkr", period="FY 2023-24", source_id=NORTH_ID,
                        locator=f"PDF page {page} / printed page {printed}; DHA {slug}; Comments on Budget and Accounts; {label} row; {'Final Grant' if measure == 'budget' else 'Exp.'} column",
                        raw_text=matches[0]))
            result[slug] = rows
    return result


def build():
    legacy = json.loads((ROOT / "data/curated/districts.json").read_text())
    services = json.loads((ROOT / "data/curated/punjab_services.json").read_text())
    c1 = json.loads(CONFIG.read_text())
    c12 = json.loads((ROOT / "data/curated/pbs_table_12.json").read_text())
    population, report = extract(ROOT / legacy['sources']['pbs_table_1']['local_file'], c1)
    if report.rejected or report.missing or len(population) != 36:
        raise ValueError("Incomplete census population")
    education = extract_education(ROOT / legacy['sources']['pbs_table_12']['local_file'], c12, population, c1)
    north = north_budget()
    sources = {**legacy['sources'], **services['sources']}
    for sid, cfg in [('pbs_table_1', c1), ('pbs_table_12', c12)]:
        sources[sid]['sha256'] = cfg['sha256']
    sources[NORTH_ID] = dict(publisher="Auditor-General of Pakistan",
        title="Audit Report on 19 District Health & Education Authorities and Daanish Schools, Punjab (North), Audit Year 2024-25",
        period="FY 2023-24", local_file=str(NORTH_FILE.relative_to(ROOT)).replace('\\','/'), sha256=NORTH_HASH,
        url="https://agp.gov.pk/SiteImage/Policy/AR%20on%20account%20of%2019%20DHand%20Education%20Authorities%20AY%202024-25.pdf")
    sources['gpis_punjab_methodology'] = dict(publisher="GPIS Project", title="GPIS Punjab-wide methodology", period="punjab-v1",
        url="https://github.com/HassanSardar525/GPIS/blob/main/docs/PUNJAB_SCORING.md", local_file="docs/PUNJAB_SCORING.md")
    service_by_slug = {d['slug']:d for d in services['districts']}
    legacy_by_slug = {d['slug']:d for d in legacy['districts']}
    records = []
    for pop in sorted(population, key=lambda d:d['name']):
        slug, name = pop['slug'], pop['name']
        edu = [o for o in education if o['slug'] == slug]
        health = [copy.deepcopy(o) for o in service_by_slug[slug]['observations'] if o['category']=='health']
        budget = north.get(slug) or [copy.deepcopy(o) for o in service_by_slug[slug]['observations'] if o['category']=='accountability']
        assert len(budget)==4 and all(o['period']=='FY 2023-24' for o in budget)
        values = {o['metric_key']:o['value'] for o in health+budget}
        health_values = {k:values[f'phs_{k}_count'] for k in ('hospitals','dispensaries','rhcs','bhus')}
        assert all(v is not None and v >= 0 for v in health_values.values())
        accountability = {}
        for kind, metric in [('total','overall'),('development','development')]:
            grant, expenditure = (values[f'dha_{kind}_{m}_million_pkr'] for m in ['budget','expenditure'])
            assert grant > 0 and expenditure >= 0
            accountability[f'{metric}_budget_lapse_pct'] = 100 - expenditure/grant*100
        warnings = []
        if slug in NORTH_PAGES:
            warnings.append("Budget inputs use the district chapter's variance table; summary and narrative rounding discrepancies are not silently substituted.")
        if slug == 'mandi-bahauddin':
            warnings.append("Source conflict: district variance table reports development final grant Rs 380.562m (PDF 57), while the province summary reports Rs 30.562m (PDF 22). The district table is used; ranking is sensitive to this discrepancy.")
        if any(v < 0 for v in accountability.values()):
            warnings.append("Reported expenditure exceeds final grant; raw utilization is retained and its score contribution is capped at 100.")
        chunks = []
        for category, rows in [('context',[pop]),('education',edu),('health',health),('accountability',budget)]:
            text = ' '.join(f"{name}: {o['metric_key']} = {o['value'] if o['value'] is not None else 'not reported (printed dash)'} {o['unit']}; {o['period']}." for o in rows)
            if category=='accountability': text += ' Scope: District Health Authority only. ' + ' '.join(warnings)
            chunks.append(dict(id=f"punjab-v1-{slug}-{category}", category=category,
                source_id=rows[0]['source_id'], locator='; '.join(dict.fromkeys(o['locator'] for o in rows)), text=text))
        record=dict(slug=slug,name=name,population_2023=pop['value'],
            education={o['metric_key']:o['value'] for o in edu}, health=health_values,
            accountability=accountability, evidence=chunks, source_warnings=warnings,
            observations=[pop,*edu,*health,*budget], service_observations=health+budget)
        # Preserve only the already reviewed temporal contract; new scores are snapshots.
        if slug in legacy_by_slug:
            old=legacy_by_slug[slug]
            record['accountability_periods']=copy.deepcopy(old['accountability_periods'])
            record['evidence'].extend(copy.deepcopy(e) for e in old['evidence'] if e['id'].endswith('-development-trend'))
        records.append(record)
    from app.punjab_scoring import VERSION, METHODS, validate_contract
    result=dict(metadata=dict(title="GPIS Punjab district dataset",generated_on="2026-10-22",
        comparison_scope="36 Census 2023 Punjab districts",score_version=VERSION,
        disclaimer="Scores summarize literacy, four types of public health institutions, and DHA budget utilization. They do not measure care quality, integrity, or individual politician performance. Source discrepancies remain visible."),
        sources=sources, districts=records,
        project_evidence=[dict(id=f'punjab-v1-method-{k}',category='methodology',text=v,source_id='gpis_punjab_methodology',locator=f'{k.title()} formula') for k,v in METHODS.items()])
    result['project_evidence'].append(dict(id='punjab-v1-project-scope',category='project',source_id='gpis_punjab_methodology',locator='Scope',text='GPIS punjab-v1 scores all 36 Census 2023 districts using Census 2023 literacy, PHS capacity as at 31 December 2023, and FY 2023-24 DHA budgets. It retains source citations, original pilot scores and explicit limitations.'))
    validate_contract(result)
    return result


if __name__ == '__main__':
    data=build()
    OUT.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(f"Wrote {len(data['districts'])} districts to {OUT.name}")
