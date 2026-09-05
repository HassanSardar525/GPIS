import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.punjab_data import ROOT, SNAPSHOT, build_snapshot, parse_percent
from app.repositories import JsonRepository
from app.database.repository import PostgresRepository
from app.schemas import ChatRequest
from app.routing import resolve_request_districts


def test_snapshot_matches_official_sources():
    assert build_snapshot() == json.loads(SNAPSHOT.read_text())
    snapshot = json.loads(SNAPSHOT.read_text())
    assert len(snapshot['districts']) == 26
    for district in snapshot['districts']:
        assert len(district['observations']) == 5
        assert len(district['education']) == 4
        for observation in district['observations']:
            assert 'sha256=' in observation['locator']
            assert 'extraction=openpyxl' in observation['locator']


def test_percentage_validation():
    assert parse_percent('70.22413412857283') == 70.224134
    assert parse_percent('50%') == 50
    for value in (-1, 101, 'NaN', 'Infinity', None, '', '=A1/B1', True):
        with pytest.raises(ValueError):
            parse_percent(value)


@pytest.mark.parametrize('backend', ['json', 'postgres'])
def test_all_districts_queryable_without_invented_scores(backend):
    if backend == 'postgres':
        url = os.getenv('GPIS_TEST_DATABASE_URL')
        if not url:
            pytest.skip('GPIS_TEST_DATABASE_URL not configured')
        repository = PostgresRepository(url, 'prototype-v1')
    else:
        repository = JsonRepository(ROOT / 'data/curated/districts.json')
    from app.services import ChatService, HybridRetriever
    from app.llm import FailingProvider
    settings = Settings(repository=backend, database_url=url if backend == 'postgres' else None)
    chat = ChatService(repository, HybridRetriever(repository, None), FailingProvider())
    app = create_app(settings=settings, repository=repository, chat_service=chat)
    with TestClient(app) as client:
        listed = client.get('/api/v1/districts').json()['districts']
        assert len(listed) == 36
        assert sum(item['scores']['overall'] is not None for item in listed) == 10
        for district in listed:
            response = client.get('/api/v1/districts/' + district['slug'])
            assert response.status_code == 200
            data = response.json()
            assert data['population_2023'] > 0
            assert len(data['education']) == 4
            assert len(data['official_health']['observations']) == 16
            assert len(data['official_budget']['observations']) == 4
            assert data['official_health']['period'] == '2023-12-31'
            if district['scores']['overall'] is None:
                assert data['health'] == data['accountability'] == data['rankings'] == {}
                assert data['derived']['facility_count'] is None
            evidence = repository.fact_search('population literacy', [district['slug']], 6)
            assert len(evidence) == 2
            assert all(item.citation.source_id.startswith('pbs_table_') for item in evidence)
        for question, slug, expected in [
            ('What is Lahore population?', 'lahore', 'Lahore'),
            ('What is literacy in Faisalabad?', 'faisalabad', 'Faisalabad'),
            ('How many out-of-school children in Sialkot?', 'sialkot', 'Sialkot'),
        ]:
            answer = client.post('/api/v1/chat', json={'question': question, 'districts': ['multan']})
            assert answer.status_code == 200, answer.text
            payload = answer.json()
            assert not payload['abstained']
            assert expected in payload['answer']
            assert any(citation['evidence_id'].startswith('fact-' + slug) for citation in payload['citations'])
        for question in ('How many hospitals in Lahore?', 'What is Lahore budget?'):
            payload = client.post('/api/v1/chat', json={'question': question}).json()
            assert not payload['abstained'], payload
            assert payload['citations']
            assert any(c['evidence_id'].startswith('service-lahore-') for c in payload['citations'])
            assert all(c['source_id'] in {'punjab_health_statistics_2024', 'agp_dha_north_budget_2022_23'} for c in payload['citations'] if c['evidence_id'].startswith('service-'))
        unavailable = client.post('/api/v1/chat', json={'question': 'What is Lahore health score?'}).json()
        assert unavailable['abstained']
        assert 'not yet available' in unavailable['answer']
        assert len(repository.rankings('overall')) == 10


def test_named_district_overrides_compatibility_alias():
    repository = JsonRepository(ROOT / 'data/curated/districts.json')
    resolved = resolve_request_districts(ChatRequest(question='Compare Lahore and Faisalabad literacy', district='multan'), repository)
    assert resolved.selected_districts() == ['lahore', 'faisalabad']

def test_unscored_district_card_renders_without_nan_or_fake_rank():
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required for the UI rendering check')
    repository = JsonRepository(ROOT / 'data/curated/districts.json')
    record = repository.get_district('lahore')
    script = r"""
const fs = require('fs');
const vm = require('vm');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const elements = {};
const context = vm.createContext({URL, data, window: {location: {origin: 'http://localhost'},
  localStorage: {getItem: () => null}, crypto: {randomUUID: () => 'test-session'}},
  document: {querySelector: selector => elements[selector] ||= {dataset: {}, setAttribute() {}, textContent: '', innerHTML: ''}}});
const source = fs.readFileSync('app/static/app.js', 'utf8').split("select.addEventListener('change'")[0];
vm.runInContext(source, context);
vm.runInContext('loadRankings = async () => {}; renderDistrict(data);', context);
if (elements['#overall-score'].textContent !== 'Unavailable') throw new Error('Fake score');
if (elements['#overall-rank'].textContent !== 'Not ranked') throw new Error('Fake rank');
if (/NaN|undefined/.test(elements['#scorecards'].innerHTML)) throw new Error('Invalid card');
if (!elements['#scorecards'].innerHTML.includes('Census 2023 education')) throw new Error('Missing facts');
"""
    subprocess.run([node, '-e', script], input=json.dumps(record), text=True, cwd=ROOT, check=True)
