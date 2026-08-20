"""Deterministic question classification for retrieval orchestration."""

from __future__ import annotations

from app.retrieval import tokenize
from app.schemas import QuestionRoute


COMPARISON = {"compare", "comparison", "better", "best", "worse", "worst", "rank", "ranking", "position", "versus", "vs"}
METHODOLOGY = {"calculate", "calculated", "formula", "method", "methodology", "score", "weight", "weighted", "mean"}
FACTS = {
    "literacy", "female", "male", "school", "children", "population", "facility", "facilities",
    "bhu", "bhus", "rhc", "rhcs", "hospital", "hospitals", "budget", "lapse", "utilization", "accountability", "education", "health",
}
UNSUPPORTED = {"weather", "recipe", "movie", "sport", "sports", "cricket", "stock", "stocks", "horoscope", "joke"}
PERSON_BLAME = {"blame", "caused", "politician", "representative"}
SCORE_MANIPULATION = {"override"}
EVIDENCE_WORDS = FACTS | {
    "access", "audit", "care", "development", "district", "evidence", "girls", "learning",
    "medical", "performance", "places", "record", "report", "source",
}


def classify_question(question: str) -> QuestionRoute:
    tokens = set(tokenize(question))
    if tokens & (PERSON_BLAME | SCORE_MANIPULATION):
        return QuestionRoute.UNSUPPORTED
    if tokens & UNSUPPORTED and not tokens & EVIDENCE_WORDS:
        return QuestionRoute.UNSUPPORTED
    if tokens & COMPARISON:
        return QuestionRoute.COMPARISON
    if tokens & METHODOLOGY:
        return QuestionRoute.METHODOLOGY
    if tokens & FACTS:
        return QuestionRoute.EXACT_FACT
    if tokens & EVIDENCE_WORDS:
        return QuestionRoute.EVIDENCE
    return QuestionRoute.UNSUPPORTED


def expand_semantic_query(question: str) -> str:
    """Add controlled domain synonyms without asking an LLM to rewrite queries."""
    query = question.casefold()
    expansions = []
    if any(word in query for word in ("girl", "learn", "school", "literacy", "education")):
        expansions.append("education literacy female school learning enrolment")
    if any(word in query for word in ("medical", "care", "clinic", "hospital", "facility", "health")):
        expansions.append("health facilities hospital BHU RHC medical care")
    if any(word in query for word in ("audit", "budget", "corruption", "accountability", "financial")):
        expansions.append("accountability audit budget lapse utilization financial management")
    return " ".join([question, *expansions])
