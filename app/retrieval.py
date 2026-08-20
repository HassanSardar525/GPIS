"""Small citation-first lexical retriever for the no-dependency prototype."""

from __future__ import annotations

import math
import re
from collections import Counter


TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a", "about", "and", "are", "did", "do", "for", "how", "in", "is",
    "of", "on", "the", "to", "was", "what", "which", "with",
}


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.casefold()) if token not in STOP_WORDS]


class EvidenceRetriever:
    def __init__(self, districts: list[dict], sources: dict, global_evidence: list[dict] | None = None):
        self.sources = sources
        self.documents = []
        for district in districts:
            for evidence in district["evidence"]:
                self.documents.append({**evidence, "district": district["name"], "slug": district["slug"]})
        for evidence in global_evidence or []:
            self.documents.append({**evidence, "district": "GPIS Project", "slug": "project"})
        self.document_frequency = Counter()
        for document in self.documents:
            self.document_frequency.update(set(tokenize(self._search_text(document))))

    def _search_text(self, document: dict) -> str:
        source = self.sources[document["source_id"]]
        return (
            f"{document['district']} {document['category']} {source['publisher']} "
            f"{source['title']} {source['period']} {document['text']}"
        )

    def search(
        self,
        query: str,
        district_slug: str | None = None,
        district_slugs: list[str] | None = None,
        category: str | None = None,
        period: str | None = None,
        limit: int = 4,
    ) -> list[dict]:
        selected = set(district_slugs or [])
        if district_slug:
            selected.add(district_slug)
        query_tokens = tokenize(query)
        query_counts = Counter(query_tokens)
        total_documents = len(self.documents)
        results = []
        for document in self.documents:
            if selected and document["slug"] not in selected and document["slug"] != "project":
                continue
            if category and document["category"] != category:
                continue
            document_counts = Counter(tokenize(self._search_text(document)))
            score = 0.0
            for token, query_frequency in query_counts.items():
                if token not in document_counts:
                    continue
                inverse_document_frequency = math.log(
                    1 + total_documents / (1 + self.document_frequency[token])
                )
                score += query_frequency * (1 + math.log(document_counts[token])) * inverse_document_frequency
            if score > 0:
                source = self.sources[document["source_id"]]
                if period and period.casefold() not in source["period"].casefold():
                    continue
                results.append(
                    {
                        "id": document["id"],
                        "district_slug": document["slug"],
                        "district_name": document["district"],
                        "category": document["category"],
                        "text": document["text"],
                        "source_id": document["source_id"],
                        "locator": document["locator"],
                        "period": source["period"],
                        "keyword_rank": None,
                        "vector_rank": None,
                        "semantic_similarity": None,
                        "rrf_score": round(score, 3),
                        "citation": {
                            "evidence_id": document["id"],
                            "source_id": document["source_id"],
                            "publisher": source["publisher"],
                            "title": source["title"],
                            "period": source["period"],
                            "url": source["url"],
                            "locator": document["locator"],
                        },
                    }
                )
        ordered = sorted(results, key=lambda item: item["rrf_score"], reverse=True)[:limit]
        for rank, result in enumerate(ordered, start=1):
            result["keyword_rank"] = rank
        return ordered


def generate_grounded_answer(question: str, results: list[dict]) -> dict:
    """Generate a concise extractive answer; never invent facts outside retrieval."""
    if not results:
        return {
            "answer": "I could not find enough evidence in the current prototype sources to answer that. Try asking about literacy, health facilities, or budget utilization.",
            "citations": [],
            "mode": "abstained",
        }

    facts = []
    seen = set()
    for result in results[:3]:
        if result["text"] not in seen:
            facts.append(result["text"])
            seen.add(result["text"])
    caution = (
        " These figures show district conditions and administrative proxies; "
        "they do not prove that any individual politician caused the result."
    )
    citations = [
        {"number": number, **result["citation"], "evidence_id": result["id"]}
        for number, result in enumerate(results[:3], start=1)
    ]
    return {
        "answer": " ".join(facts) + caution,
        "citations": citations,
        "mode": "retrieval-grounded prototype",
        "question": question,
    }
