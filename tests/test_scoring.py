import copy
import json
from pathlib import Path

import pytest

from app.errors import MissingScoreInputs
from app.scoring import rankings, score_districts
from app.score_quality import (
    aggregate_confidence,
    evidence_confidence,
    staged_health_result,
    staged_rankings,
    weighted_coverage,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data/curated/districts.json").read_text(encoding="utf-8"))
GOLDEN = json.loads((ROOT / "tests/fixtures/golden_scores.json").read_text(encoding="utf-8"))
V2_GOLDEN = json.loads(
    (ROOT / "tests/fixtures/evidence_v2_golden.json").read_text(encoding="utf-8")
)


def test_scores_match_locked_golden_contract():
    actual = {district["slug"]: district["derived"]["scores"] for district in score_districts(DATA["districts"])}
    assert actual == GOLDEN["districts"]


def test_all_scores_are_bounded():
    for district in score_districts(DATA["districts"]):
        assert all(0 <= score <= 100 for score in district["derived"]["scores"].values())


def test_missing_required_input_rejects_score():
    districts = copy.deepcopy(DATA["districts"])
    del districts[0]["education"]["literacy_total_pct"]
    with pytest.raises(MissingScoreInputs, match="education.literacy_total_pct"):
        score_districts(districts)


def test_tied_rankings_are_stable_and_alphabetical():
    districts = score_districts(DATA["districts"])
    districts[0]["derived"]["scores"]["overall"] = 50
    districts[1]["derived"]["scores"]["overall"] = 50
    ordered = rankings(districts, "overall")
    tied = [item["name"] for item in ordered if item["score"] == 50]
    assert tied == sorted(tied)


@pytest.mark.parametrize("case", ["full", "partial_at_threshold", "below_threshold"])
def test_evidence_v2_health_golden_cases(case):
    expected = V2_GOLDEN["health"][case]
    actual = staged_health_result(expected["inputs"])

    assert actual["score"] == expected["score"]
    assert actual["coverage"] == expected["coverage"]
    assert actual["ranked"] is expected["ranked"]
    assert actual["missing_components"] == expected["missing_components"]


def test_coverage_uses_expected_weight_without_zero_filling():
    assert weighted_coverage(
        {"capacity": 90, "activity": None, "outcomes": None},
        {"capacity": 0.5, "activity": 0.25, "outcomes": 0.25},
    ) == 0.5


def test_confidence_uses_documented_evidence_properties():
    factors = {
        "source_authority": 1.0,
        "recency": 0.75,
        "directness": 0.5,
        "cross_district_comparability": 1.0,
    }
    assert evidence_confidence(factors) == 0.8125
    assert aggregate_confidence({"capacity": 1.0, "activity": 0.75, "outcomes": None}, {
        "capacity": 0.5, "activity": 0.25, "outcomes": 0.25
    }) == 0.9167


def test_confidence_rejects_unreviewed_rating_values():
    with pytest.raises(ValueError, match="0.5, 0.75, or 1.0"):
        evidence_confidence({
            "source_authority": 1.0,
            "recency": 0.25,
            "directness": 1.0,
            "cross_district_comparability": 1.0,
        })


def test_evidence_v2_rankings_keep_insufficient_coverage_unranked():
    ordered = staged_rankings([
        {"name": "Beta", "score": 80.0, "ranked": True},
        {"name": "Alpha", "score": 80.0, "ranked": True},
        {"name": "Non-comparable", "score": None, "ranked": False},
    ])

    assert [item["name"] for item in ordered[:2]] == V2_GOLDEN["ranking"]["tied_names_in_order"]
    assert ordered[-1]["rank"] is V2_GOLDEN["ranking"]["non_comparable_rank"]
