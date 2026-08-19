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
    def __init__(self, districts: list[dict], sources: dict):
        self.sources = sources
        self.documents = []
        for district in districts:
            for evidence in district["evidence"]:
                self.documents.append({**evidence, "district": district["name"], "slug": district["slug"]})
        self.document_frequency = Counter()
        for document in self.documents:
            self.document_frequency.update(set(tokenize(self._search_text(document))))

    @staticmethod
    def _search_text(document: dict) -> str:
        return f"{document['district']} {document['category']} {document['text']}"

    def search(self, query: str, district_slug: str | None = None, limit: int = 4) -> list[dict]:
        query_tokens = tokenize(query)
        query_counts = Counter(query_tokens)
        total_documents = len(self.documents)
        results = []
        for document in self.documents:
            if district_slug and document["slug"] != district_slug:
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
                results.append(
                    {
                        **document,
                        "relevance": round(score, 3),
                        "citation": {
                            "publisher": source["publisher"],
                            "title": source["title"],
                            "period": source["period"],
                            "url": source["url"],
                            "locator": document["locator"],
                        },
                    }
                )
        return sorted(results, key=lambda item: item["relevance"], reverse=True)[:limit]


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
