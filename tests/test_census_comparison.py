import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.facts import CENSUS_METRICS, census_ranking
from app.main import create_app
from app.repositories import JsonRepository
from app.database.repository import PostgresRepository

ROOT = Path(__file__).resolve().parents[1]


def test_census_ranking_api_has_36_positions_and_sources():
    repository = JsonRepository(ROOT / 'data/curated/districts.json')
    client = TestClient(create_app(settings=Settings(), repository=repository))
    for metric in CENSUS_METRICS:
        response = client.get('/api/v1/census-rankings', params={'metric': metric})
        assert response.status_code == 200
        data = response.json()
        assert len(data['rows']) == 36
        values = [row['value'] for row in data['rows']]
        assert values == sorted(values, reverse=True)
        assert data['period'] == '2023'
        assert all(row['citation']['locator'] and row['citation']['passage'] for row in data['rows'])
        assert data['rows'][0]['position'] == 1
    assert client.get('/api/v1/census-rankings?metric=unknown').status_code == 400
    assert len(client.get('/api/v1/rankings?category=overall').json()['rankings']) == 10


def test_equal_values_share_position_and_zero_is_preserved():
    result = census_ranking('population_2023', [
        {'name': 'C', 'value': 0}, {'name': 'B', 'value': 10}, {'name': 'A', 'value': 10}])
    assert [(row['name'], row['value'], row['position']) for row in result['rows']] == [
        ('A', 10, 1), ('B', 10, 1), ('C', 0, 3)]


def test_postgres_and_json_census_positions_match():
    url = os.getenv('GPIS_TEST_DATABASE_URL')
    if not url:
        pytest.skip('GPIS_TEST_DATABASE_URL not configured')
    postgres = PostgresRepository(url, 'prototype-v1')
    local = JsonRepository(ROOT / 'data/curated/districts.json')
    for metric in CENSUS_METRICS:
        actual = postgres.census_ranking(metric)['rows']
        expected = local.census_ranking(metric)['rows']
        assert [(row['slug'], row['value'], row['position']) for row in actual] == [
            (row['slug'], row['value'], row['position']) for row in expected]
        assert all(row['citation']['source_id'] == ('pbs_table_1' if metric == 'population_2023' else 'pbs_table_12') for row in actual)
