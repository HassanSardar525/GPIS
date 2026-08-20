from contextlib import contextmanager
from pathlib import Path

import pytest

from app.llm import FailingProvider
from app.repositories import JsonRepository
from app.schemas import ChatRequest
from app.services import ChatService, HybridRetriever


ROOT = Path(__file__).resolve().parents[1]


class CapturedSpan:
    def __init__(self, name, kind, attributes):
        self.name = name
        self.kind = kind
        self.attributes = dict(attributes or {})

    def set_attributes(self, attributes):
        self.attributes.update(attributes)


class CapturingObservability:
    status = "configured"

    def __init__(self):
        self.spans = []

    @contextmanager
    def span(self, name, kind, attributes=None):
        span = CapturedSpan(name, kind, attributes)
        self.spans.append(span)
        yield span


@pytest.mark.asyncio
async def test_chat_captures_parent_retrieval_and_generation_spans():
    repository = JsonRepository(ROOT / "data/curated/districts.json")
    observer = CapturingObservability()
    retriever = HybridRetriever(repository, None, observability=observer)
    service = ChatService(repository, retriever, FailingProvider(), observer)

    response = await service.answer(ChatRequest(question="What is Multan literacy?", districts=["multan"]))

    by_name = {span.name: span for span in observer.spans}
    assert set(by_name) == {"gpis.chat", "gpis.retrieve", "gpis.generate"}
    assert by_name["gpis.chat"].attributes["gpis.answer_mode"] == "extractive"
    assert by_name["gpis.retrieve"].attributes["retrieval.document_ids"][0].startswith("fact-multan-")
    assert by_name["gpis.generate"].attributes["llm.provider"] == "unavailable"
