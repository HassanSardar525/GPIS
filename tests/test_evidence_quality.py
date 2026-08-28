from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evidence_quality import (
    HealthCapacityDataset,
    format_health_capacity_period,
    health_capacity_change,
    load_health_capacity,
)
from app.schemas import ScoreResult


DATA_PATH = Path("data/curated/health_capacity_periods.json")


def test_reviewed_health_capacity_dataset_is_complete_and_valid():
    dataset = load_health_capacity(DATA_PATH)

    assert dataset.version == "phs-table-3-review-v1"
    assert len(dataset.districts) == 10
    assert set(dataset.sources) == {
        "punjab_health_statistics_2023",
        "punjab_health_statistics_2024",
    }
    assert dataset.comparability.status == "comparable_with_limitations"
    assert dataset.comparability.metric_assessments["facility_counts"].status == "accepted"
    assert dataset.comparability.metric_assessments["registered_personnel"].status == "excluded"

    for district in dataset.districts:
        assert [period.snapshot_date.isoformat() for period in district.periods] == [
            "2023-01-01",
            "2023-12-31",
        ]
        assert all(period.locator.startswith("Table 3,") for period in district.periods)


def test_capacity_change_uses_reviewed_values_and_exact_locators():
    dataset = load_health_capacity(DATA_PATH)

    change = health_capacity_change(dataset, "multan", "hospitals")

    assert change["previous"]["count"] == 22
    assert change["current"]["count"] == 20
    assert change["count_change"] == -2
    assert change["previous"]["beds"] == 2905
    assert change["current"]["beds"] == 4375
    assert change["bed_change"] == 1470
    assert change["previous"]["locator"] == "Table 3, Multan District row, printed page 7"
    assert change["current"]["locator"] == "Table 3, Multan District row, printed page 7"


def test_source_dashes_remain_null_and_do_not_produce_changes():
    dataset = load_health_capacity(DATA_PATH)

    change = health_capacity_change(dataset, "dera-ghazi-khan", "dispensaries")

    assert change["previous"]["beds"] is None
    assert change["current"]["beds"] == 2
    assert change["bed_change"] is None
    assert change["warnings"] == [
        "The 2023 source prints a dash for dispensary beds while the 2024 source prints two; "
        "the earlier dash remains null rather than zero."
    ]


def test_source_anomaly_is_preserved_instead_of_inferred():
    dataset = load_health_capacity(DATA_PATH)

    change = health_capacity_change(dataset, "rajanpur", "mch_centers")

    assert change["current"]["count"] is None
    assert change["current"]["beds"] == 4
    assert change["count_change"] is None
    assert change["bed_change"] == 0
    assert "count is not inferred" in change["warnings"][0]


def test_dataset_rejects_unknown_source_references():
    dataset = load_health_capacity(DATA_PATH)
    payload = dataset.model_dump(mode="json")
    payload["districts"][0]["periods"][0]["source_id"] = "unknown-source"

    with pytest.raises(ValidationError, match="unknown source_id"):
        HealthCapacityDataset.model_validate(payload)


def test_dataset_rejects_incomplete_facility_contract():
    dataset = load_health_capacity(DATA_PATH)
    payload = dataset.model_dump(mode="json")
    del payload["districts"][0]["periods"][0]["facilities"]["hospitals"]

    with pytest.raises(ValidationError, match="facility keys differ"):
        HealthCapacityDataset.model_validate(payload)


def test_unknown_district_is_explicit():
    dataset = load_health_capacity(DATA_PATH)

    with pytest.raises(KeyError, match="Unknown district"):
        health_capacity_change(dataset, "not-a-district", "hospitals")


def test_score_quality_metadata_is_backward_compatible_and_explicit():
    legacy = ScoreResult(
        category="health",
        score=50,
        version="prototype-v1",
        components={"facilities_per_100k": 3.2},
        coverage=1,
    )
    reviewed = ScoreResult(
        category="health",
        score=50,
        version="prototype-v1",
        components={"facilities_per_100k": 3.2},
        coverage=1,
        reporting_period="Census 2023 population and Audit Year 2024-25 facility listing",
        confidence=None,
        missing_components=[],
        warnings=["relative facility-count proxy"],
    )

    assert legacy.reporting_period == "mixed-current-period"
    assert legacy.confidence is None
    assert legacy.missing_components == []
    assert reviewed.warnings == ["relative facility-count proxy"]


def test_capacity_evidence_formatter_keeps_printed_dashes_explicit():
    dataset = load_health_capacity(DATA_PATH)
    rajanpur = next(item for item in dataset.districts if item.slug == "rajanpur")

    text = format_health_capacity_period(rajanpur.name, rajanpur.periods[-1])

    assert "Rajanpur public health capacity at 2023-12-31" in text
    assert "MCH centers: not reported institutions, 4 beds" in text
    assert "not converted to zero" in text
