import copy
import json
from pathlib import Path

import pytest

from app.errors import MissingScoreInputs
from app.scoring import rankings, score_districts


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data/curated/districts.json").read_text(encoding="utf-8"))
GOLDEN = json.loads((ROOT / "tests/fixtures/golden_scores.json").read_text(encoding="utf-8"))


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
