"""Historical evidence integrity, handovers, missingness and deployment parity."""
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.history import ASSETS, HistoryRepository, INSUFFICIENT, compare_observations, packaged_release, validate_release
from app.main import create_app
from app.repositories import JsonRepository


def term(identity, start, end, **updates):
    return dict(id=identity, person=identity, role='Chief minister', responsibility='provincial_executive',
                start=start,end=end,start_precision='day',end_precision='day',status='verified',**updates)


def obs(start,end,value,unit='count',**updates):
    return dict(id=start,start=start,end=end,period=start+' / '+end,value=value,metric='test',unit=unit,
                definition='v1',population_group='district',geography='same-boundary',comparability='reviewed',
                status='verified',anchor_ids=['source'],**updates)


def test_handover_and_caretaker_do_not_split_fiscal_year():
    terms=[term('elected','2022-07-01','2023-01-22'),term('caretaker','2023-01-22','2024-02-25',caretaker=True),term('successor','2024-02-26','2026-01-01')]
    rows=[obs('2022-07-01','2023-06-30',32,'percent'),obs('2023-07-01','2024-06-30',46,'percent')]
    result=compare_observations(rows,terms)
    assert result['label']=='Change across multiple administrations'
    assert result['change']==14 and result['unit']=='percentage points'
    assert [t['id'] for t in result['officeholders']]==['elected','caretaker','successor']
    assert compare_observations(rows,terms,terms[1])['label']==INSUFFICIENT


def test_within_tenure_uses_full_measurement_intervals():
    t=term('person','2023-01-22','2024-02-25')
    rows=[obs('2023-02-01','2023-02-01',4),obs('2023-12-31','2023-12-31',6)]
    assert compare_observations(rows,[t],t)['label']=='Observed change within this tenure'
    assert compare_observations(rows,[t],t)['change']==2
    t['start_precision']='month'
    assert compare_observations(rows,[t],t)['change'] is None
    t['start_precision']='day';t['end']=None;t['end_precision']='unknown'
    assert compare_observations(rows,[t],t)['change'] is None


@pytest.mark.parametrize('change',['missing','geography','definition','population_group','unit','comparability','overlap','pending','vacancy'])
def test_incompatible_or_missing_comparisons_blocked(change):
    t=term('person','2020-01-01','2025-01-01')
    rows=[obs('2023-01-01','2023-01-01',4),obs('2023-12-31','2023-12-31',6)]
    if change=='missing':rows[0]['value']=None
    elif change=='overlap':rows[0]['end']='2023-12-31'
    elif change=='pending':t['status']='awaiting_review'
    elif change=='vacancy':t['vacancy']=True
    else:rows[1][change]='different'
    assert compare_observations(rows,[t],t)['change'] is None


def test_release_coverage_and_sources():
    data=packaged_release();validate_release(data)
    assert len(data['districts'])==36
    manual=json.loads((ROOT/'data/curated/health_history_review.json').read_text(encoding='utf8'))
    # Independently printed Punjab totals on Table 3 page 19.
    assert {k:sum(r['counts'][k] for r in manual['rows']) for k in ('hospitals','dispensaries','rhcs','bhus')} == dict(hospitals=339,dispensaries=1185,rhcs=374,bhus=2533)
    for slug in data['districts']:
        r=HistoryRepository().history(slug,'phs_hospitals_count')
        assert len(r['observations'])==2
        assert r['comparison']['change'] is not None
        assert HistoryRepository().history(slug,'literacy_total_pct')['comparison']['change'] is None
    comparable=sum(HistoryRepository().history(s,'dha_development_utilization_pct')['comparison']['change'] is not None for s in data['districts'])
    assert comparable==31
    store = HistoryRepository()
    lahore = store.history('lahore', 'dha_development_expenditure_million_pkr')
    assert lahore['comparison']['change'] == pytest.approx(4.595 - 22.350)
    disputed = store.history('mandi-bahauddin', 'dha_development_budget_million_pkr')
    assert disputed['comparison']['change'] is None
    assert '30.562' in disputed['observations'][-1]['reason']
    assert len(disputed['observations'][-1]['anchor_ids']) == 2
    mpas=[t for t in data['terms'] if t['role']=='MPA']
    assert len(mpas)>250
    assert all(t['start'] is None and t['end'] is None and t['mapping_anchor_ids'] for t in mpas)
    assert set(d for t in mpas for d in t['districts'])==set(data['districts'])
    multan=HistoryRepository().history('multan','dha_development_budget_million_pkr')
    assert multan['observations'][-1]['value']==1013.030
    assert 'conflict' in multan['observations'][-1]['reason']


def test_scan_spreadsheet_and_printed_page_locations():
    store=HistoryRepository()
    rows=store.history('multan','phs_hospitals_count')['observations']
    scan=store.evidence(rows[0]['anchor_ids'][0])
    assert scan['pages'][0]['number']==22 and scan['pages'][0]['printed_label']=='7'
    assert scan['pages'][0]['rectangles'] and '22 institutions' in scan['text']
    assert scan['checksum']=='8c7c99b08bd0adfafc3afd324e1551797cbfc6ecd78dd920f7cf177db03aa6e8'
    literacy=store.evidence(store.history('multan','literacy_total_pct')['observations'][0]['anchor_ids'][0])
    cells=[c for s in literacy['worksheets'] for row in s['rows'] for c in row if c['highlight']]
    assert len(cells)==1 and cells[0]['address']=='B1614'
    assert cells[0]['value']==pytest.approx(61.410495,abs=1e-6)


def test_packaged_assets_and_evidence_api_need_no_raw_files(monkeypatch):
    from app.history import verify_packaged_assets
    assert verify_packaged_assets()==56
    data=packaged_release()
    assets={p['asset'] for a in data['anchors'].values() for p in a.get('pages',[])}
    assert len(assets)>45
    assert all((ASSETS/a).is_file() and (ASSETS/a).read_bytes().startswith(b'\x89PNG') for a in assets)
    # Runtime API is intentionally independent of parser libraries and raw files.
    import sys
    monkeypatch.setitem(sys.modules,'pdfplumber',None)
    monkeypatch.setitem(sys.modules,'pypdfium2',None)
    repo=JsonRepository(ROOT/'data/curated/districts.json','punjab-v1')
    with TestClient(create_app(Settings(score_version='punjab-v1'),repository=repo)) as client:
        row=client.get('/api/v1/districts/multan/history').json()['observations'][0]
        anchor=client.get('/api/v1/evidence/'+row['anchor_ids'][0]).json()
        assert client.get(anchor['pages'][0]['asset_url']).status_code==200
        assert client.get('/api/v1/evidence-assets/not-registered.png').status_code==404
        assert client.get('/api/v1/evidence/no-such-anchor').status_code==404
        assert client.get('/api/v1/districts/unknown/history').status_code==404
        assert client.get('/api/v1/districts/multan/history?metric=unknown').status_code==422
        assert client.get('/api/v1/districts/multan/history?tenure=unknown').status_code==404
        assert client.get('/api/v1/districts/multan/history?tenure=maryam-2024').json()['comparison']['change'] is None


@pytest.mark.parametrize('question,expected',[
 ('Who was chief minister during the change in Multan hospital numbers?', 'Parvez Elahi'),
 ('How did Multan health change during Mohsin Naqvi tenure?', 'Insufficient evidence'),
 ('How did education improve during Maryam Nawaz tenure in Lahore?', 'Insufficient evidence'),
 ('Who held office across the 2022 and 2024 budget changes in Multan?', 'administrations'),
 ('Why does the date differ for Parvez Elahi tenure?', '27 July'),
 ('Who held office during Multan budget changes and are there source conflicts?', '1013.030'),
 ('Who are the Multan MPAs?', 'unverified'),
])
def test_named_officeholder_rag(question,expected):
    repo=JsonRepository(ROOT/'data/curated/districts.json','punjab-v1')
    with TestClient(create_app(Settings(score_version='punjab-v1'),repository=repo)) as client:
        r=client.post('/api/v1/chat',json={'question':question,'districts':['multan'],'model':'fallback'}).json()
        assert expected.lower() in r['answer'].lower(),r
        assert r['route']=='tenure_history' and r['citations']
        assert all(c['anchor_ids'] for c in r['citations'])


@pytest.mark.skipif(not os.getenv('GPIS_PUNJAB_TEST_DATABASE_URL'),reason='Dedicated test database not configured')
def test_historical_postgres_json_parity():
    from app.database.seed import seed_database
    url=os.environ['GPIS_PUNJAB_TEST_DATABASE_URL']
    seed_database(url,ROOT/'data/curated/districts.json','punjab-v1')
    pg,js=HistoryRepository('postgres',url),HistoryRepository()
    for slug in js.data()['districts']:
        assert pg.officeholders(slug)==js.officeholders(slug)
        for metric in ('phs_hospitals_count','dha_development_utilization_pct','literacy_total_pct'):
            assert pg.history(slug,metric)==js.history(slug,metric)
    aid=js.history('multan')['observations'][0]['anchor_ids'][0]
    assert pg.evidence(aid)==js.evidence(aid)


def test_personal_allegation_does_not_list_people_as_culprits():
    from app.history_chat import history_answer
    from app.schemas import ChatRequest
    repo=JsonRepository(ROOT/'data/curated/districts.json','punjab-v1')
    answer=history_answer(ChatRequest(question='Which chief minister stole the budget?',districts=['multan']),repo)
    assert answer.abstained and not answer.citations
    assert 'cannot establish' in answer.answer


def test_chief_minister_source_passage_contains_handover_dates():
    from app.history import packaged_release
    release = packaged_release()
    term = next(t for t in release["terms"] if t["id"] == "naqvi-2023")
    text = " ".join(release["anchors"][key]["text"] for key in term["anchor_ids"])
    assert term["start"] in text and term["end"] in text
