import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent import AgentChatService, build_agent_tools
from app.llm import FailingProvider
from app.repositories import JsonRepository
from app.schemas import ChatRequest, QuestionRoute
from app.services import ChatService, HybridRetriever


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = JsonRepository(ROOT / "data/curated/districts.json")
RETRIEVER = HybridRetriever(REPOSITORY, None)


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def bind_tools(self, tools, **kwargs):
        self.tools = tools
        return self

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


def service_for(model):
    fallback = ChatService(REPOSITORY, RETRIEVER, FailingProvider())
    return AgentChatService(REPOSITORY, RETRIEVER, model, fallback)


@pytest.mark.asyncio
async def test_agent_answers_greeting_without_retrieval():
    model = ScriptedModel([AIMessage(content="Hello! Ask me about district performance.")])
    response = await service_for(model).answer(ChatRequest(question="Hi there", session_id="session-greeting"))

    assert response.route == QuestionRoute.CONVERSATION
    assert response.tools_used == []
    assert response.citations == []
    assert response.mode == "groq"


@pytest.mark.asyncio
async def test_agent_calls_structured_district_tool_for_capabilities():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "district_data",
                        "args": {"action": "list", "districts": [], "category": "overall"},
                        "id": "call-list",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="You can currently query 10 districts."),
        ]
    )
    response = await service_for(model).answer(
        ChatRequest(question="How many districts can I query?", session_id="session-districts")
    )

    assert response.route == QuestionRoute.EXACT_FACT
    assert response.tools_used == ["district_data"]
    assert "10 districts" in response.answer


@pytest.mark.asyncio
async def test_agent_returns_only_real_citations_from_tool_results():
    evidence_id = "score-multan-education-prototype-v1"
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "district_data",
                        "args": {"action": "scores", "districts": ["multan"], "category": "education"},
                        "id": "call-score",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content=f"Multan's education score is grounded in stored components 【{evidence_id}】."),
        ]
    )
    response = await service_for(model).answer(
        ChatRequest(
            question="Why did Multan receive its education score?",
            districts=["multan"],
            session_id="session-score",
        )
    )

    assert response.citations[0].evidence_id == evidence_id
    assert f"[{evidence_id}]" in response.answer
    assert response.tools_used == ["district_data"]
    assert all(citation.evidence_id != "invented" for citation in response.citations)


@pytest.mark.asyncio
async def test_agent_invented_citation_triggers_grounded_fallback():
    model = ScriptedModel([AIMessage(content="Multan has a value of 99% [invented-source].")])
    response = await service_for(model).answer(
        ChatRequest(
            question="What is literacy in Multan?",
            districts=["multan"],
            session_id="session-invalid-citation",
        )
    )

    assert response.mode == "extractive"
    assert response.citations
    assert all(citation.evidence_id != "invented-source" for citation in response.citations)
    assert "deterministic RAG fallback" in response.warnings[0]


@pytest.mark.asyncio
async def test_langgraph_session_retains_prior_turn_messages():
    model = ScriptedModel(
        [
            AIMessage(content="Hello!"),
            AIMessage(content="Yes, your previous message was hello."),
        ]
    )
    service = service_for(model)
    await service.answer(ChatRequest(question="Hello", session_id="session-memory"))
    second = await service.answer(
        ChatRequest(question="What did I say before?", session_id="session-memory")
    )

    human_messages = [message for message in model.calls[-1] if isinstance(message, HumanMessage)]
    assert [message.content for message in human_messages] == ["Hello", "What did I say before?"]
    assert second.session_id == "session-memory"


@pytest.mark.asyncio
async def test_all_three_tools_return_structured_payloads():
    tools = {tool.name: tool for tool in build_agent_tools(REPOSITORY, RETRIEVER)}
    district_payload = json.loads(
        await tools["district_data"].ainvoke({"action": "list", "districts": [], "category": "overall"})
    )
    evidence_payload = json.loads(
        await tools["evidence_search"].ainvoke(
            {"query": "Multan literacy", "districts": ["multan"], "category": "education", "period": None}
        )
    )
    project_payload = json.loads(
        await tools["project_knowledge"].ainvoke({"query": "What is the GPIS project?"})
    )

    assert district_payload["count"] == 10
    assert evidence_payload["evidence"]
    assert any(item["evidence_id"] == "gpis-project-scope" for item in project_payload["citations"])
