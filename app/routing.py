"""Deterministic question classification for retrieval orchestration."""

from __future__ import annotations

from app.retrieval import tokenize
from app.schemas import QuestionRoute


COMPARISON = {"compare", "comparison", "better", "best", "worse", "worst", "rank", "ranking", "position", "versus", "vs"}
CONVERSATION = {"hello", "hey", "hi", "thank", "thanks"}
TEMPORAL = {
    "change", "changed", "decline", "declined", "decrease", "decreased", "improve", "improved",
    "improvement", "previous", "trend", "year", "yearly",
}
METHODOLOGY = {
    "calculate", "calculated", "formula", "mean", "method", "methodology", "normalization",
    "normalized", "score", "weight", "weighted",
}
FORMULA_WORDS = METHODOLOGY - {"score"}
SCORE_REASON = {"explain", "got", "given", "reason", "received", "why"}
PROJECT = {"architecture", "gpis", "pipeline", "project", "rag", "retrieval"}
FACTS = {
    "literacy", "female", "male", "school", "children", "population", "facility", "facilities",
    "bhu", "bhus", "rhc", "rhcs", "hospital", "hospitals", "budget", "lapse", "utilization", "accountability", "education", "health",
}
UNSUPPORTED = {"weather", "recipe", "movie", "sport", "sports", "cricket", "stock", "stocks", "horoscope", "joke"}
PERSON_BLAME = {"blame", "caused", "politician", "politicians", "representative", "representatives"}
SCORE_MANIPULATION = {"override"}
FUTURE_PREDICTION = {"forecast", "predict", "predicted", "prediction"}
PROMPT_INJECTION_PHRASES = {
    "developer message",
    "ignore previous",
    "ignore the system",
    "reveal instructions",
    "reveal the prompt",
    "system message",
    "system prompt",
}
EVIDENCE_WORDS = FACTS | {
    "access", "audit", "care", "development", "district", "evidence", "girls", "learning",
    "medical", "performance", "places", "record", "report", "source",
}


def requires_abstention(question: str) -> bool:
    """Identify requests that must bypass the conversational agent and abstain."""
    lowered = question.casefold()
    tokens = set(tokenize(question))
    return bool(
        tokens & (PERSON_BLAME | SCORE_MANIPULATION | FUTURE_PREDICTION)
        or (tokens & UNSUPPORTED and not tokens & EVIDENCE_WORDS)
        or ("ignore" in tokens and bool(tokens & {"instructions", "previous", "system"}))
        or "next year" in lowered
        or any(phrase in lowered for phrase in PROMPT_INJECTION_PHRASES)
    )


def classify_question(question: str) -> QuestionRoute:
    tokens = set(tokenize(question))
    if requires_abstention(question):
        return QuestionRoute.UNSUPPORTED
    domain_tokens = EVIDENCE_WORDS | METHODOLOGY | PROJECT | COMPARISON | TEMPORAL
    if tokens & CONVERSATION and not tokens & domain_tokens:
        return QuestionRoute.CONVERSATION
    temporal = bool(
        tokens & TEMPORAL
        or "last year" in question.casefold()
        or "year over year" in question.casefold()
    )
    unsupported_trend_domains = {
        "children", "education", "female", "literacy", "male", "outcome", "outcomes", "school"
    }
    if temporal and tokens & unsupported_trend_domains:
        return QuestionRoute.UNSUPPORTED
    if temporal:
        return QuestionRoute.TEMPORAL_COMPARISON
    if tokens & COMPARISON:
        return QuestionRoute.COMPARISON
    if "score" in tokens and tokens & SCORE_REASON and not tokens & FORMULA_WORDS:
        return QuestionRoute.SCORE_EXPLANATION
    if "score" in tokens and not tokens & (FORMULA_WORDS | PROJECT):
        return QuestionRoute.EXACT_FACT
    if tokens & PROJECT:
        return QuestionRoute.PROJECT
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
