"""A provider outage goes through FastAPI and returns a cited district fact."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import JsonRepository
from app.services import ChatService, HybridRetriever


def test_provider_outage_uses_grounded_fallback():
    class OfflineProvider:
        name = "groq"
        calls = 0

        async def generate(self, question, evidence, structured_context):
            self.calls += 1
            raise ConnectionError("Injected outage")

    settings = Settings(score_version="punjab-v1")
    repository = JsonRepository(settings.curated_data_path, settings.score_version)
    provider = OfflineProvider()
    service = ChatService(repository, HybridRetriever(repository, None), provider)
    with TestClient(create_app(settings=settings, repository=repository, chat_service=service)) as client:
        response = client.post("/api/v1/chat", json={"question": "What is Multan's literacy rate?", "districts": ["multan"]})
        response.raise_for_status()
        data = response.json()
    assert provider.calls == 1
    assert data["mode"] == "extractive" and not data["abstained"]
    assert "61.41" in data["answer"] and "Multan" in data["answer"]
    assert any("LLM" in warning for warning in data["warnings"])
    assert any(c["evidence_id"] == "fact-multan-literacy_total_pct" for c in data["citations"])
