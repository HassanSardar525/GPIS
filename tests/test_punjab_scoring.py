import copy
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.punjab_scoring import VERSION, load_contract, validate_contract
from app.repositories import JsonRepository

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/curated/districts.json'


def test_all_36_scores_have_same_budget_year_and_canonical_sources():
    data = load_contract(BASE)
    repo = JsonRepository(BASE, VERSION)
    assert len(repo.list_districts()) == len(repo.rankings('overall')) == 36
    for record in data['districts']:
        profile=repo.get_district(record['slug'])
        assert profile['official_budget']['period']=='FY 2023-24'
        assert len(profile['score_details'])==4
        for detail in profile['score_details'].values():
            assert detail['version']==VERSION and 0<=detail['score']<=100
            assert detail['confidence'] is None
        for category in ['education','health','accountability']:
            evidence=next(e for e in record['evidence'] if e['category']==category)
            assert evidence['locator'] and evidence['source_id'] in data['sources']
    lahore=repo.get_district('lahore')
    # Independently checked: literacy 84.5, lowest cohort capacity 0.0,
    # mean of 5070.884/5472.33 and 4.595/6.884 is 79.7; overall 54.7.
    assert lahore['derived']['scores']==dict(education=84.5,health=0.0,accountability=79.7,overall=54.7)
    assert '380.562' in ' '.join(repo.get_district('mandi-bahauddin')['source_warnings'])
    assert JsonRepository(BASE).get_district('multan')['derived']['scores']['overall']==41.0


@pytest.mark.parametrize('change', ['period','missing','duplicate','zero_grant','utilization'])
def test_invalid_contract_cannot_be_published(change):
    data=copy.deepcopy(load_contract(BASE))
    d=data['districts'][0]
    budget=next(o for o in d['service_observations'] if o['metric_key']=='dha_total_budget_million_pkr')
    if change=='period': budget['period']='FY 2022-23'
    if change=='missing': d['health']['bhus']=None
    if change=='duplicate': data['districts'][-1]=copy.deepcopy(d)
    if change=='zero_grant': budget['value']=0
    if change=='utilization': d['accountability']['overall_budget_lapse_pct']=99
    with pytest.raises(ValueError): validate_contract(data)


def test_punjab_api_scores_chat_and_comparison():
    settings=Settings(score_version=VERSION)
    with TestClient(create_app(settings=settings, repository=JsonRepository(BASE,VERSION))) as client:
        response=client.get('/api/v1/rankings?category=overall')
        assert response.status_code==200 and len(response.json()['rankings'])==36
        for question in ['What is the health score for Lahore?', 'Compare Lahore and Multan overall scores', 'How is the health score calculated?']:
            response=client.post('/api/v1/chat',json={'question':question,'districts':['lahore'],'model':'fallback'})
            assert response.status_code==200, response.text
            body=response.json()
            assert not body['abstained'] and body['citations'], body
            assert 'ten-district' not in body['answer']


def test_new_snapshot_reproduces_without_touching_curated_files():
    pytest.importorskip('pdfplumber')
    from scripts.build_punjab_scores import NORTH_FILE, build
    if not NORTH_FILE.exists(): pytest.skip('Official PDFs not downloaded')
    assert build()==load_contract(BASE)


@pytest.mark.skipif(not os.getenv('GPIS_PUNJAB_TEST_DATABASE_URL'),reason='Dedicated Punjab test database not configured')
def test_punjab_database_seed_and_backend_parity():
    from app.database.seed import seed_database
    from app.database.repository import PostgresRepository
    url=os.environ['GPIS_PUNJAB_TEST_DATABASE_URL']
    first=seed_database(url,BASE,VERSION)
    assert seed_database(url,BASE,VERSION)==first
    assert first['score_results']==184  # 40 legacy + 36 x four new scores
    postgres=PostgresRepository(url,VERSION)
    curated=JsonRepository(BASE,VERSION)
    for category in ['education','health','accountability','overall']:
        assert postgres.rankings(category)==curated.rankings(category)
    for d in curated.list_districts():
        a,b=postgres.get_district(d['slug']),curated.get_district(d['slug'])
        assert a['derived']['scores']==b['derived']['scores']
        assert a['health']==b['health']
        assert a['official_budget']['period']=='FY 2023-24'
        for key,value in b['accountability'].items():
            assert a['accountability'][key]==pytest.approx(value,abs=1e-6)
    assert PostgresRepository(url,'prototype-v1').get_district('multan')['derived']['scores']['overall']==41.0
