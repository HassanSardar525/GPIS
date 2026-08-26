from contextlib import contextmanager
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from app.agent import AgentChatService
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


@pytest.mark.asyncio
async def test_agent_captures_generation_tool_and_retrieval_spans():
    class ScriptedModel:
        def __init__(self):
            self.responses = [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "evidence_search",
                            "args": {
                                "query": "Multan literacy",
                                "districts": ["multan"],
                                "category": "education",
                                "period": None,
                            },
                            "id": "call-observed-search",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(
                    content=(
                        "Multan's total literacy rate is 61.41% "
                        "[fact-multan-literacy_total_pct]."
                    )
                ),
            ]

        def bind_tools(self, tools, **kwargs):
            return self

        async def ainvoke(self, messages):
            return self.responses.pop(0)

    repository = JsonRepository(ROOT / "data/curated/districts.json")
    observer = CapturingObservability()
    retriever = HybridRetriever(repository, None, observability=observer)
    fallback = ChatService(repository, retriever, FailingProvider(), observer)
    service = AgentChatService(
        repository,
        retriever,
        ScriptedModel(),
        fallback,
        observability=observer,
    )

    response = await service.answer(
        ChatRequest(
            question="What is Multan literacy?",
            districts=["multan"],
            session_id="session-observability",
        )
    )

    names = [span.name for span in observer.spans]
    assert names.count("gpis.agent.generate") == 2
    assert "gpis.agent.tool.evidence_search" in names
    assert "gpis.retrieve" in names
    tool_span = next(span for span in observer.spans if span.name == "gpis.agent.tool.evidence_search")
    assert "fact-multan-literacy_total_pct" in tool_span.attributes["gpis.citation_ids"]
    assert response.tools_used == ["evidence_search"]
