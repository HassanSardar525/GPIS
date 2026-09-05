import copy
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ingest_official_data import CONFIG, ROOT, Report, extract, load_observations, parse_count, parse_rows, resolve_district

CONFIGURATION = json.loads(CONFIG.read_text())
SOURCE = json.loads((ROOT / 'data/curated/districts.json').read_text())['sources']['pbs_table_1']


def test_district_aliases_and_unknown():
    for alias in ('D.G. Khan', 'DG Khan', 'Dera Ghazi Khan', 'D.G.Khan', 'DERA GHAZI KHAN DISTRICT'):
        assert resolve_district(alias, CONFIGURATION) == 'dera-ghazi-khan'
    with pytest.raises(ValueError):
        resolve_district('Unknown District', CONFIGURATION)


def test_counts_and_missing():
    assert parse_count('5,362,305') == 5362305
    assert parse_count(12.0) == 12
    assert parse_count(0) == 0
    for value in (None, '', '-', '..', 'N/A'):
        assert parse_count(value) is None
    for value in (-1, 1.5, 'NaN', 'Infinity', True, '12,34', '=SUM(C1:C2)', '40%', 2147483648):
        with pytest.raises(ValueError):
            parse_count(value)


def test_rows_reject_duplicates_missing_and_bad_data():
    rows = [(8, ('ATTOCK DISTRICT', None, 2170423)), (9, ('ATTOCK DISTRICT', None, 1)),
            (10, ('MULTAN DISTRICT', None, None)), (11, ('LAHORE DISTRICT', None, -1)),
            (12, ('UNKNOWN DISTRICT', None, 100)), (13, ('RURAL', None, 10)),
            (14, ('VEHARI DISTRICT',)), (15, ('MULTAN TEHSIL', None, 20))]
    observations, report = parse_rows(rows, CONFIGURATION)
    assert observations == []
    assert report.duplicates == 2
    assert report.rejected == 5
    assert report.missing == 1


def test_real_source_golden_and_provenance():
    path = ROOT / SOURCE['local_file']
    if not path.exists():
        pytest.skip('Official workbook is not checked into Git; use the documented raw source')
    observations, report = extract(path, CONFIGURATION)
    assert report.accepted == 36
    assert report.rejected == report.missing == 0
    assert report.warnings == []
    by_slug = {item['slug']: item for item in observations}
    assert by_slug['attock']['value'] == 2170423
    assert by_slug['multan']['value'] == 5362305
    assert report.metrics_extracted == ['population_2023']
    assert 'Punjab Dist!A8:C8' in by_slug['attock']['locator']
    assert 'extraction=openpyxl' in by_slug['attock']['locator']
    assert CONFIGURATION['sha256'] in by_slug['attock']['locator']
    curated = json.loads((ROOT / 'data/curated/districts.json').read_text())
    for district in curated['districts']:
        assert by_slug[district['slug']]['value'] == district['population_2023']


def test_changed_workbook_rejected(tmp_path):
    path = tmp_path / 'wrong.xlsx'
    path.write_bytes(b'not the registered workbook')
    with pytest.raises(ValueError, match='checksum'):
        extract(path, CONFIGURATION)


def test_postgres_idempotency_and_reviewed_conflicts():
    url = os.getenv('GPIS_TEST_DATABASE_URL')
    if not url:
        pytest.skip('GPIS_TEST_DATABASE_URL is not configured')
    from app.database.session import session_factory
    from app.database.models import District, Observation, ScoreResult
    from app.database.repository import PostgresRepository
    observations, _ = extract(ROOT / SOURCE['local_file'], CONFIGURATION)
    with session_factory(url)() as session:
        try:
            before_scores = [(x.id, x.score) for x in session.scalars(select(ScoreResult)).all()]
            before_observations = [(x.id, x.value, x.locator) for x in session.scalars(select(Observation)).all()]
            first = Report(accepted=36)
            load_observations(session, observations, SOURCE, CONFIGURATION, first)
            session.flush()
            second = Report(accepted=36)
            load_observations(session, observations, SOURCE, CONFIGURATION, second)
            assert second.inserted == 0
            assert second.duplicates == 36
            assert second.rejected == 0
            assert before_scores == [(x.id, x.score) for x in session.scalars(select(ScoreResult)).all()]
            for identity, value, locator in before_observations:
                current = session.get(Observation, identity)
                assert (current.value, current.locator) == (value, locator)
            from contextlib import contextmanager
            from app.errors import DistrictNotFound
            @contextmanager
            def borrowed_session():
                yield session
            repository = PostgresRepository.__new__(PostgresRepository)
            repository.sessions = borrowed_session
            repository.score_version = 'prototype-v1'
            assert len(repository.list_districts()) == 36
            assert repository.get_district('multan')['population_2023'] == 5362305
            assert repository.get_district('attock')['score_details'] == {}
            assert len(repository.rankings('overall')) == 10
            changed = copy.deepcopy(observations[:1])
            changed[0]['value'] += 1
            conflict = Report(accepted=1)
            load_observations(session, changed, SOURCE, CONFIGURATION, conflict)
            assert conflict.rejected == 1
            assert conflict.inserted == 0
            assert conflict.warnings
        finally:
            session.rollback()


def test_checked_in_golden_row():
    fixture = json.loads((ROOT / 'tests/fixtures/pbs_table_1_golden.json').read_text())
    rows, report = parse_rows([(fixture['row'], fixture['cells'])], CONFIGURATION)
    assert report.accepted == 1
    for key in ('slug', 'metric_key', 'value', 'source_id'):
        assert rows[0][key] == fixture[key]
    assert "source row='ATTOCK DISTRICT', population=2170423" in rows[0]['locator']


def test_duplicate_with_missing_value_withholds_valid_row():
    rows, report = parse_rows([(8, ('ATTOCK DISTRICT', None, 2170423)),
                               (9, ('ATTOCK DISTRICT', None, None))], CONFIGURATION)
    assert rows == []
    assert report.duplicates == 2
    assert report.missing == 1
    assert report.rejected == 1


def test_malformed_header(tmp_path):
    from hashlib import sha256
    from openpyxl import Workbook
    path = tmp_path / 'malformed.xlsx'
    workbook = Workbook()
    workbook.active.title = CONFIGURATION['sheet']
    workbook.active['C2'] = 'POPULATION 2017'
    workbook.save(path)
    config = {**CONFIGURATION, 'sha256': sha256(path.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match='header'):
        extract(path, config)
