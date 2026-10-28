"""Reviewed historical records and deterministic interval comparisons.

No inference of office dates, geography, missing values, or personal causation.
The same versioned release is loaded from JSON or PostgreSQL.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import ROOT

RELEASE = ROOT / 'data/curated/history.json'
ASSETS = ROOT / 'data/evidence'
INSUFFICIENT = 'Insufficient evidence for a tenure comparison'


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    district: str
    metric: str
    value: float | None = Field(allow_inf_nan=False)
    unit: str
    start: date
    end: date
    date_precision: str
    period: str
    definition: str
    population_group: str
    geography: str
    comparability: str | None
    status: Literal['verified', 'awaiting_review', 'unavailable']
    reason: str
    anchor_ids: list[str]

    @model_validator(mode='after')
    def valid_interval(self):
        if self.start > self.end:
            raise ValueError('Measurement interval is reversed')
        return self


class OfficeTerm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    person: str | None
    role: str
    responsibility: str
    portfolio: str | None = None
    party: str | None
    caretaker: bool = False
    vacancy: bool = False
    start: date | None
    end: date | None
    start_precision: str
    end_precision: str
    verified_through: date | None = None
    status: Literal['verified', 'awaiting_review', 'unavailable']
    notes: list[str] = Field(default_factory=list)
    districts: list[str] = Field(default_factory=list)
    constituency: str | None = None
    boundary_edition: str | None = None
    mapping_anchor_ids: list[str] = Field(default_factory=list)
    anchor_ids: list[str]

    @model_validator(mode='after')
    def validate_dates_and_mapping(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError('Office dates are reversed')
        if self.start_precision == 'day' and not self.start:
            raise ValueError('Exact start date is missing')
        if self.end_precision == 'day' and not self.end:
            raise ValueError('Exact end date is missing')
        if self.constituency and (not self.boundary_edition or not self.mapping_anchor_ids):
            raise ValueError('Constituency mapping needs a boundary edition and evidence')
        return self


@lru_cache(maxsize=1)
def packaged_release():
    if not RELEASE.is_file():
        return {'anchors': {}, 'citation_index': {}, 'terms': [], 'observations': [], 'districts': {}}
    return json.loads(RELEASE.read_text(encoding='utf8'))


def validate_release(data):
    for row in data['observations']:
        Observation.model_validate(row)
    for row in data['terms']:
        OfficeTerm.model_validate(row)
    for collection in ('terms', 'observations'):
        ids = [x['id'] for x in data[collection]]
        if len(ids) != len(set(ids)):
            raise ValueError(f'Duplicate {collection} ids')
        for row in data[collection]:
            if any(a not in data['anchors'] for a in row['anchor_ids']):
                raise ValueError('Unregistered evidence')
    for anchor in data['anchors'].values():
        for page in anchor.get('pages', []):
            filename = page['asset']
            if Path(filename).name != filename or not filename.endswith('.png'):
                raise ValueError('Invalid asset name')
            for box in page.get('rectangles', []):
                if not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
                    raise ValueError('Invalid highlight rectangle')


def citation_anchors(source_id, locator, evidence_id=''):
    index = packaged_release()['citation_index']
    score = re.fullmatch(r'score-(.+)-(overall|education|health|accountability)-punjab-v1', evidence_id)
    if score and 'calculated-' + score[1] in packaged_release()['anchors']:
        return ['calculated-' + score[1]]
    return index.get(evidence_id, index.get(source_id + '|' + locator, []))


def term_bounds(term):
    """Unknown ends are not silently treated as current officeholding."""
    if term['start_precision'] != 'day' or not term.get('start'):
        return None
    end = term.get('end') if term['end_precision'] == 'day' else term.get('verified_through')
    if not end:
        return None
    return term['start'], end


def overlap(term, start, end):
    bounds = term_bounds(term)
    return bool(bounds and bounds[0] <= end and bounds[1] >= start)


def possible_overlap(term, start, end):
    """Retain approximate official-history handovers, visibly qualified.

    A wholly undated record is never extrapolated into an administration.
    """
    finish = term.get('end') or term.get('verified_through')
    return bool(term.get('start') and finish and term['start'] <= end and finish >= start)


def compare_observations(rows, terms, selected=None):
    usable = sorted((r for r in rows if r['status'] == 'verified' and r['value'] is not None
                     and r['comparability']), key=lambda r: (r['start'], r['end']))
    if selected:
        bounds = term_bounds(selected) if selected['status'] == 'verified' and not selected.get('vacancy') else None
        usable = [r for r in usable if bounds and bounds[0] <= r['start'] and r['end'] <= bounds[1]]
    if len(usable) < 2:
        return {'label': INSUFFICIENT, 'change': None, 'officeholders': [],
                'reason': 'Two comparable observations fully inside the selected dates are required.'}
    first, last = usable[0], usable[-1]
    keys = ('metric', 'unit', 'definition', 'population_group', 'geography', 'comparability')
    if any(first[k] != last[k] for k in keys) or first['end'] >= last['start']:
        return {'label': INSUFFICIENT, 'change': None, 'officeholders': [],
                'reason': 'Definitions, geography, population groups or measurement intervals do not match.'}
    overlapping = [t for t in terms if possible_overlap(t, first['start'], last['end'])]
    executives = [t for t in overlapping if t['role'] == 'Chief minister']
    single_exact = len(executives) == 1 and executives[0]['status'] == 'verified' and term_bounds(executives[0]) and executives[0]['start'] <= first['start'] and term_bounds(executives[0])[1] >= last['end']
    label = 'Observed change within this tenure' if selected or single_exact else 'Change across multiple administrations'
    return {'label': label, 'change': round(last['value'] - first['value'], 6),
            'unit': 'percentage points' if first['unit'] == 'percent' else first['unit'],
            'from': first['period'], 'to': last['period'], 'start': first['start'], 'end': last['end'],
            'observation_ids': [first['id'], last['id']], 'officeholders': overlapping,
            'anchor_ids': list(dict.fromkeys(first['anchor_ids'] + last['anchor_ids'])),
            'reason': 'Observed district change; this does not establish that any officeholder caused it. Fiscal years are not apportioned between administrations.'}


class HistoryRepository:
    def __init__(self, backend='json', database_url=None):
        self.backend = backend
        self.database_url = database_url
        self._release = None

    def data(self):
        if self.backend != 'postgres':
            return packaged_release()
        if self._release is not None:
            return self._release
        from sqlalchemy import text
        from app.database.session import session_factory
        with session_factory(self.database_url)() as session:
            data = session.execute(text("SELECT payload FROM historical_releases WHERE id = 'history-v1'" )).scalar_one_or_none()
        if data is None:
            raise HTTPException(503, 'Historical release has not been seeded.')
        self._release = data
        return data

    def officeholders(self, slug):
        data = self.data()
        if slug not in data['districts']:
            raise HTTPException(404, 'Unknown census district')
        terms = [t for t in data['terms'] if not t['districts'] or slug in t['districts']]
        return {'district': slug, 'terms': terms, 'coverage': data['districts'][slug]['officeholders'],
                'notice': 'District statistics are not constituency measurements. Lists may be incomplete; missing records do not imply a vacancy.'}

    def history(self, slug, metric='phs_hospitals_count', tenure=None):
        data = self.data()
        holders = self.officeholders(slug)
        if metric not in data['metrics']:
            raise HTTPException(422, 'Unknown historical metric')
        selected = next((t for t in holders['terms'] if t['id'] == tenure), None)
        if tenure and not selected:
            raise HTTPException(404, 'Unknown tenure for this district')
        rows = copy.deepcopy([r for r in data['observations'] if r['district'] == slug and r['metric'] == metric])
        for r in rows:
            r['officeholders'] = [t['id'] for t in holders['terms'] if possible_overlap(t, r['start'], r['end'])]
            bounds = term_bounds(selected) if selected else None
            r['within_selected_tenure'] = bool(bounds and bounds[0] <= r['start'] and r['end'] <= bounds[1])
        return {'district': slug, 'metric': metric, 'metric_info': data['metrics'][metric],
                'metrics': data['metrics'], 'observations': sorted(rows, key=lambda r:r['start']),
                'comparison': compare_observations(rows, holders['terms'], selected),
                'coverage': data['districts'][slug]['metrics'][metric], 'selected_tenure': tenure,
                'notice': 'Missing years are not interpolated. Amounts are nominal rupees. No personal causal claim is implied.'}

    def evidence(self, anchor_id):
        anchor = self.data()['anchors'].get(anchor_id)
        if not anchor:
            raise HTTPException(404, 'Unknown evidence anchor')
        result = copy.deepcopy(anchor)
        for page in result.get('pages', []):
            page['asset_url'] = '/api/v1/evidence-assets/' + page['asset']
        return result

    def asset(self, filename):
        registered = {p['asset'] for a in self.data()['anchors'].values() for p in a.get('pages', [])}
        path = (ASSETS / filename).resolve()
        if filename not in registered or path.parent != ASSETS.resolve() or not path.is_file():
            raise HTTPException(404, 'Unregistered or unavailable evidence asset')
        return path


def seed_history(session, data_path):
    from sqlalchemy import text
    path = data_path.with_name('history.json')
    if path.is_file():
        data = json.loads(path.read_text(encoding='utf8'))
        validate_release(data)
        session.execute(text("INSERT INTO historical_releases (id,payload) VALUES ('history-v1',CAST(:payload AS jsonb)) ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload"), {'payload': json.dumps(data)})


def verify_packaged_assets(data=None):
    data = data or packaged_release()
    validate_release(data)
    checked = {}
    for anchor in data['anchors'].values():
        for page in anchor.get('pages', []):
            name = page['asset']
            if name not in checked:
                content = (ASSETS / name).read_bytes()
                if not content.startswith(b'\x89PNG'):
                    raise ValueError('Invalid preview image: ' + name)
                checked[name] = hashlib.sha256(content).hexdigest()
            if checked[name] != page['asset_sha256']:
                raise ValueError('Packaged evidence checksum mismatch: ' + name)
    return len(checked)


if __name__ == '__main__':
    print(f'Validated {verify_packaged_assets()} packaged evidence pages; no raw reports required.')
