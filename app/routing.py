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


def resolve_request_districts(request, repository):
    """Explicit names in the question take precedence over the UI's current selection."""
    import re
    question = request.question.casefold()
    matches = []
    for district in repository.list_districts():
        names = [district['name'], district['slug'].replace('-', ' ')]
        if district['slug'] == 'dera-ghazi-khan':
            names += ['D.G. Khan', 'DG Khan', 'D.G.Khan']
        for name in names:
            match = re.search(r'(?<!\w)' + re.escape(name.casefold()) + r'(?!\w)', question)
            if match:
                matches.append((match.start(), district['slug']))
                break
    if matches:
        return request.model_copy(update={'districts': [slug for _, slug in sorted(matches)], 'district': None})
    return request


def unavailable_data_reason(request, repository):
    """Do not answer a missing district fact with another metric or a fabricated score."""
    from app.facts import requested_metrics
    route = classify_question(request.question)
    if route in {QuestionRoute.METHODOLOGY, QuestionRoute.PROJECT, QuestionRoute.CONVERSATION, QuestionRoute.UNSUPPORTED}:
        return None
    question = request.question.casefold()
    for slug in request.selected_districts():
        record = repository.get_district(slug)
        if record['score_details']:
            continue
        metrics = requested_metrics(question)
        available = {'population_2023', *record['education'], *record['health'], *record['accountability']}
        if (any(metric not in available for metric in metrics)
                or route == QuestionRoute.TEMPORAL_COMPARISON
                or any(word in question for word in ('score', 'rank', 'health', 'hospital', 'facilit', 'budget', 'accountability'))
                or request.category in {'health', 'accountability'}):
            return (f"{record['name']} has Census 2023 population, literacy and out-of-school figures. "
                    'Reviewed GPIS scores, health facilities, budgets and comparable trends are not yet available '
                    'for this district, so I cannot provide the requested measure.')
    return None
