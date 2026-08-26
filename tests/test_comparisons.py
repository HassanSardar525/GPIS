from pathlib import Path

import pytest

from app.comparisons import (
    build_comparison,
    comparison_language_is_safe,
    comparison_numbers_are_grounded,
    format_comparison_summary,
    requested_comparison_category,
)
from app.errors import InvalidComparison, TrendUnavailable
from app.repositories import JsonRepository
from app.llm import FailingProvider, GeneratedAnswer
from app.schemas import ChatRequest
from app.services import ChatService, HybridRetriever


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = JsonRepository(ROOT / "data/curated/districts.json")


def test_overall_comparison_has_deterministic_scores_ranks_and_components():
    comparison = build_comparison(REPOSITORY, ["multan", "bahawalpur"], "overall")

    assert [item.slug for item in comparison.districts] == ["multan", "bahawalpur"]
    assert [item.score for item in comparison.districts] == [41.0, 84.3]
    assert [item.rank for item in comparison.districts] == [9, 2]
    assert comparison.score_delta == 43.3
    assert comparison.rank_delta == -7
    assert {item.key for item in comparison.components} == {"education", "health", "accountability"}
    assert comparison.trends == []
    assert len(comparison.citations) == 2


def test_accountability_comparison_includes_source_linked_trends():
    comparison = build_comparison(REPOSITORY, ["multan", "bahawalpur"], "accountability")

    assert len(comparison.trends) == 2
    assert comparison.trends[0].change_percentage_points == 24.92
    assert comparison.trends[0].citation.evidence_id == "multan-development-trend"
    assert len(comparison.citations) == 4
    assert any("development-budget utilization only" in item for item in comparison.limitations)


def test_comparison_preserves_left_right_order_and_signed_delta():
    forward = build_comparison(REPOSITORY, ["multan", "bahawalpur"], "education")
    reverse = build_comparison(REPOSITORY, ["bahawalpur", "multan"], "education")

    assert forward.score_delta == -5.5
    assert reverse.score_delta == 5.5
    assert forward.components[0].delta == -8.06
    assert reverse.components[0].delta == 8.06


@pytest.mark.parametrize("districts", [[], ["multan"], ["multan", "multan"], ["multan", "bahawalpur", "vehari"]])
def test_comparison_requires_exactly_two_distinct_districts(districts):
    with pytest.raises(InvalidComparison):
        build_comparison(REPOSITORY, districts, "overall")


def test_comparison_summary_uses_canonical_values_and_citations():
    comparison = build_comparison(REPOSITORY, ["multan", "bahawalpur"], "overall")
    summary = format_comparison_summary(comparison)

    assert "Multan scores 41.0 at rank 9" in summary
    assert "Bahawalpur scores 84.3 at rank 2" in summary
    assert "leads Multan by 43.3 points" in summary
    assert "[score-multan-overall-prototype-v1]" in summary


def test_tied_scores_use_an_explicit_tie_summary():
    repository = JsonRepository(ROOT / "data/curated/districts.json")
    repository.by_slug["multan"]["derived"]["scores"]["overall"] = 50.0
    repository.by_slug["bahawalpur"]["derived"]["scores"]["overall"] = 50.0
    comparison = build_comparison(repository, ["multan", "bahawalpur"], "overall")

    assert comparison.score_delta == 0
    assert "are tied" in format_comparison_summary(comparison)


def test_missing_trend_is_labeled_instead_of_converted_to_zero():
    class TrendlessRepository:
        def __getattr__(self, name):
            return getattr(REPOSITORY, name)

        def development_trend(self, slug):
            if slug == "bahawalpur":
                raise TrendUnavailable("Comparable trend data is unavailable for Bahawalpur")
            return REPOSITORY.development_trend(slug)

    comparison = build_comparison(
        TrendlessRepository(), ["multan", "bahawalpur"], "accountability"
    )

    assert len(comparison.trends) == 1
    assert any("unavailable for Bahawalpur" in item for item in comparison.limitations)


def test_numeric_grounding_rejects_values_outside_comparison_payload():
    comparison = build_comparison(REPOSITORY, ["multan", "bahawalpur"], "overall")

    assert comparison_numbers_are_grounded(
        "Multan scores 41.0 and Bahawalpur scores 84.3, a 43.3 point difference.", comparison
    )
    assert not comparison_numbers_are_grounded(
        "Multan scores 99.0 and Bahawalpur scores 84.3.", comparison
    )
    assert not comparison_numbers_are_grounded(
        "Multan scores 84.3 and Bahawalpur scores 41.0.", comparison
    )
    assert not comparison_numbers_are_grounded(
        "Multan is rank 2 and Bahawalpur is rank 9.", comparison
    )


def test_numeric_grounding_rejects_swapped_component_and_trend_values():
    education = build_comparison(REPOSITORY, ["multan", "bahawalpur"], "education")
    accountability = build_comparison(REPOSITORY, ["multan", "bahawalpur"], "accountability")

    assert not comparison_numbers_are_grounded(
        "Multan Total literacy is 53.35, while Bahawalpur Total literacy is 61.41.",
        education,
    )
    assert not comparison_numbers_are_grounded(
        "Multan increased by 10.00 percentage points.", accountability
    )


def test_comparison_language_requires_uncertainty_and_rejects_attribution():
    assert comparison_language_is_safe("Female literacy may be a possible contributing factor.")
    assert not comparison_language_is_safe("Female literacy is a contributing factor.")
    assert not comparison_language_is_safe("A politician caused this result.")


def test_comparison_category_uses_domain_terms():
    assert requested_comparison_category("Compare female literacy") == "education"
    assert requested_comparison_category("Compare health facilities") == "health"
    assert requested_comparison_category("Compare budget utilization") == "accountability"
    assert requested_comparison_category("Compare their scores") == "overall"


@pytest.mark.asyncio
async def test_deterministic_chat_returns_structured_comparison_and_summary():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), FailingProvider())
    response = await service.answer(
        ChatRequest(
            question="Compare the overall scores of Multan and Bahawalpur.",
            districts=["multan", "bahawalpur"],
        )
    )

    assert response.mode == "extractive"
    assert response.comparison is not None
    assert response.comparison.category == "overall"
    assert response.comparison.score_delta == 43.3
    assert "Bahawalpur leads Multan by 43.3 points" in response.answer
    assert {item.evidence_id for item in response.citations} >= {
        "score-multan-overall-prototype-v1",
        "score-bahawalpur-overall-prototype-v1",
    }


@pytest.mark.asyncio
async def test_raw_metric_comparison_does_not_substitute_a_score_comparison():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), FailingProvider())
    response = await service.answer(
        ChatRequest(
            question="Compare literacy in Multan and Bahawalpur.",
            districts=["multan", "bahawalpur"],
        )
    )

    assert response.comparison is None
    assert "61.41%" in response.answer
    assert "53.35%" in response.answer


@pytest.mark.asyncio
async def test_two_district_temporal_question_includes_structured_trends():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), FailingProvider())
    response = await service.answer(
        ChatRequest(
            question="Compare last-year development utilization change in Multan and Bahawalpur.",
            districts=["multan", "bahawalpur"],
        )
    )

    assert response.comparison is not None
    assert response.comparison.category == "accountability"
    assert len(response.comparison.trends) == 2
    assert {item.citation.evidence_id for item in response.comparison.trends} == {
        "multan-development-trend",
        "bahawalpur-development-trend",
    }


@pytest.mark.asyncio
async def test_generated_numeric_mismatch_uses_deterministic_comparison_fallback():
    class MismatchedProvider:
        name = "test"

        async def generate(self, question, evidence, structured_context):
            ids = [item.id for item in evidence[:2]]
            return GeneratedAnswer(
                answer=f"Multan scores 99.0 [{ids[0]}]. Bahawalpur scores 84.3 [{ids[1]}].",
                evidence_ids=ids,
                warnings=[],
            )

    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), MismatchedProvider())
    response = await service.answer(
        ChatRequest(
            question="Compare the overall scores of Multan and Bahawalpur.",
            districts=["multan", "bahawalpur"],
        )
    )

    assert response.mode == "extractive"
    assert response.comparison is not None
    assert "Multan scores 41.0" in response.answer
    assert "99.0" not in response.answer
