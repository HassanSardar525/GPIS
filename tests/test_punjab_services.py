import json
from pathlib import Path
import pytest
from app.repositories import JsonRepository
from app.punjab_services import query_rows
from app.routing import unavailable_data_reason
from app.schemas import ChatRequest

ROOT = Path(__file__).resolve().parents[1]


def test_official_service_coverage_and_source_periods():
    repo = JsonRepository(ROOT / "data/curated/districts.json")
    for d in repo.list_districts():
        record = repo.get_district(d["slug"])
        assert len(record["official_health"]["observations"]) == 16
        assert record["official_health"]["period"] == "2023-12-31"
        assert len(record["official_budget"]["observations"]) == 4
        assert len(repo.fact_search("How many BHUs?", [d["slug"]], 6)) == 1
    assert len(repo.rankings("overall")) == 10
    lahore = repo.get_district("lahore")
    assert lahore["official_budget"]["period"] == "FY 2022-23"
    assert repo.get_district("faisalabad")["official_budget"]["period"] == "FY 2023-24"
    values = {o["metric_key"]:o["value"] for o in lahore["official_health"]["observations"]}
    assert values["phs_hospitals_count"] == 50
    assert values["phs_hospitals_beds"] == 13634
    assert values["phs_tb_clinics_beds"] is None
    budget = {o["metric_key"]:o["value"] for o in lahore["official_budget"]["observations"]}
    assert budget["dha_total_budget_million_pkr"] == 5818.950
    assert budget["dha_total_expenditure_million_pkr"] == 5719.336
    assert repo.fact_search("hospital beds", ["lahore"], 6)[0].citation.period == "2023-12-31"
    assert repo.fact_search("budget", ["lahore"], 6)[0].citation.period == "FY 2022-23"
    assert unavailable_data_reason(ChatRequest(question="How many BHUs?", districts=["lahore"]),repo) is None
    assert unavailable_data_reason(ChatRequest(question="What is the health score?", districts=["lahore"]),repo)
    assert unavailable_data_reason(ChatRequest(question="How did the budget change?", districts=["lahore"]),repo)


def test_source_snapshot_is_reproducible():
    pytest.importorskip("pdfplumber")
    from scripts.build_punjab_services import OUT, main
    if not (ROOT / "data/raw/agp_punjab_north_dha_2023-24.pdf").is_file():
        pytest.skip("Official North Punjab PDF is not downloaded")
    original = OUT.read_bytes()
    main()
    assert OUT.read_bytes() == original
