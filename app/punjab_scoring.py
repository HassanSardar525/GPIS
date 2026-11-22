"""Versioned, source-linked scoring of the 36 Census 2023 Punjab districts."""
from __future__ import annotations

import json
import math
from pathlib import Path

VERSION = 'punjab-v1'
HEALTH_FIELDS = ('hospitals', 'dispensaries', 'rhcs', 'bhus')
METHODS = {
    'education': 'Education is the mean of total literacy, female literacy, and 100 minus the male-female literacy gap, from Census 2023.',
    'health': 'Health counts hospitals, dispensaries, RHCs and BHUs in PHS Table 3 as at 31 December 2023, divides by Census 2023 population per 100,000, and min-max normalizes across all 36 census districts. It measures reported capacity, not quality or outcomes.',
    'accountability': 'Accountability averages total and development DHA expenditure divided by final grant for FY 2023-24. Each contribution is bounded to 0–100; raw utilization and source discrepancies remain visible. Utilization is not proof of integrity or impact.',
    'overall': 'Overall is the equal-weight mean of the rounded education, health and accountability scores under punjab-v1. It combines Census 2023, health capacity at 31 December 2023 and FY 2023-24 DHA budgets, not an annual outcome or a politician rating.',
}


def validate_contract(data):
    districts = data['districts']
    if len(districts) != 36 or len({d['slug'] for d in districts}) != 36:
        raise ValueError('Punjab scoring requires exactly 36 unique census districts')
    for d in districts:
        if d['population_2023'] <= 0:
            raise ValueError('Missing population denominator')
        for field in ('literacy_total_pct','literacy_male_pct','literacy_female_pct'):
            value=d['education'].get(field)
            if value is None or not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"Invalid education input {d['slug']}: {field}")
        for field in HEALTH_FIELDS:
            value=d['health'].get(field)
            if value is None or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid health input {d['slug']}: {field}")
        rows=d['service_observations']
        by_metric={o['metric_key']:o for o in rows}
        if len(by_metric)!=len(rows):
            raise ValueError('Duplicate service observation')
        for field in HEALTH_FIELDS:
            observation=by_metric.get(f'phs_{field}_count')
            if not observation or observation['period']!='2023-12-31' or observation['unit']!='count' or observation['value']!=d['health'][field]:
                raise ValueError('Health scoring input differs from its dated source observation')
        budget={o['metric_key']:o for o in rows if o['category']=='accountability'}
        expected={f'dha_{kind}_{measure}_million_pkr' for kind in ('total','development') for measure in ('budget','expenditure')}
        if set(budget)!=expected:
            raise ValueError('Incomplete budget inputs')
        for o in rows:
            if o['source_id'] not in data['sources'] or not o['locator']:
                raise ValueError('Missing source provenance')
            if o['category']=='accountability':
                if o['period']!='FY 2023-24' or o['unit']!='million_pkr' or o['value'] is None or not math.isfinite(o['value']) or o['value'] < 0:
                    raise ValueError('Budget period or value is incompatible')
                if '_budget_' in o['metric_key'] and o['value'] == 0:
                    raise ValueError('Zero grant cannot be scored')
        for kind, field in [('total','overall'),('development','development')]:
            raw=100-budget[f'dha_{kind}_expenditure_million_pkr']['value']/budget[f'dha_{kind}_budget_million_pkr']['value']*100
            if not math.isclose(raw,d['accountability'][f'{field}_budget_lapse_pct'],abs_tol=1e-8):
                raise ValueError('Derived utilization does not match raw budget cells')


def load_contract(base_path: Path):
    path=base_path.with_name('punjab_districts.json')
    data=json.loads(path.read_text(encoding='utf-8'))
    if data['metadata']['score_version'] != VERSION:
        raise ValueError('Unexpected Punjab score version')
    validate_contract(data)
    return data


def score_districts(districts, generated_on='2026-10-22'):
    from app.scoring import education_score
    rates=[sum(d['health'][k] for k in HEALTH_FIELDS)/d['population_2023']*100000 for d in districts]
    low, high = min(rates), max(rates)
    result=[]
    for d, rate in zip(districts,rates,strict=True):
        total=100-d['accountability']['overall_budget_lapse_pct']
        development=100-d['accountability']['development_budget_lapse_pct']
        scores=dict(education=education_score(d),health=round((rate-low)/(high-low)*100,1) if high!=low else 50.0,
            accountability=round((min(100,max(0,total))+min(100,max(0,development)))/2,1))
        scores['overall']=round(sum(scores.values())/3,1)
        count=sum(d['health'][k] for k in HEALTH_FIELDS)
        components=dict(education=dict(literacy_total_pct=d['education']['literacy_total_pct'],literacy_female_pct=d['education']['literacy_female_pct'],gender_parity=100-abs(d['education']['literacy_male_pct']-d['education']['literacy_female_pct'])),
            health=dict(facility_count=count,facilities_per_100k=round(rate,2),cohort_min=round(low,2),cohort_max=round(high,2)),
            accountability=dict(overall_budget_utilization_pct=total,development_budget_utilization_pct=development),
            overall={k:scores[k] for k in ('education','health','accountability')})
        periods=dict(education='Census 2023',health='2023-12-31; Census 2023 population',accountability='FY 2023-24',overall='Census 2023; health 2023-12-31; DHA FY 2023-24')
        details={k:dict(category=k,score=v,version=VERSION,components=components[k],coverage=1.0,
            reporting_period=periods[k],confidence=None,confidence_factors={},missing_components=[],
            warnings=([METHODS[k]] if k!='education' else [])+(d.get('source_warnings',[]) if k in ('accountability','overall') else []),
            calculated_at=f'{generated_on}T00:00:00+00:00') for k,v in scores.items()}
        result.append({**d,'derived':dict(facility_count=count,facilities_per_100k=round(rate,2),scores=scores,score_details=details)})
    return result
