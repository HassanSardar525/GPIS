from pathlib import Path

from app.cache import CacheRead, cache_key, normalized_query, retrieval_corpus_version
from app.embeddings import DeterministicTestEmbedder
from app.repositories import JsonRepository
from app.schemas import ChatRequest, QuestionRoute
from app.services import HybridRetriever


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "curated" / "districts.json"


class DictCache:
    name = "test"
    status = "available"

    def __init__(self):
        self.values = {}
        self.locks = {}

    def get(self, key):
        value = self.values.get(key)
        return CacheRead(value, "hit" if value is not None else "miss")

    def set(self, key, value, ttl_seconds):
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)

    def acquire_lock(self, key, ttl_seconds):
        if key in self.locks:
            return None
        self.locks[key] = "token"
        return "token"

    def release_lock(self, key, token):
        if self.locks.get(key) == token:
            self.locks.pop(key)

    def close(self):
        return None


class BrokenCache(DictCache):
    def get(self, key):
        return CacheRead(None, "error")

    def set(self, key, value, ttl_seconds):
        return False

    def acquire_lock(self, key, ttl_seconds):
        return None


class CountingEmbedder(DeterministicTestEmbedder):
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return super().embed(texts)


def evidence_payload(items):
    return [item.model_dump(mode="json") for item in items]


def test_retrieval_cache_returns_fresh_equivalent_models_and_skips_embedding():
    repository = JsonRepository(DATA)
    cache = DictCache()
    embedder = CountingEmbedder()
    retriever = HybridRetriever(repository, embedder, cache=cache)
    request = ChatRequest(
        question="What official places provide basic medical care in the district?",
        districts=["rahim-yar-khan"],
    )

    cold = retriever.retrieve(request, QuestionRoute.EVIDENCE)
    warm = retriever.retrieve(request, QuestionRoute.EVIDENCE)

    assert cold
    assert evidence_payload(warm) == evidence_payload(cold)
    assert warm is not cold
    assert embedder.calls == 1


def test_embedding_cache_is_shared_across_distinct_retrieval_filters():
    repository = JsonRepository(DATA)
    cache = DictCache()
    embedder = CountingEmbedder()
    retriever = HybridRetriever(repository, embedder, cache=cache)
    question = "What does the record say about access to learning for girls?"

    retriever.retrieve(
        ChatRequest(question=question, districts=["dera-ghazi-khan"]),
        QuestionRoute.EVIDENCE,
    )
    retriever.retrieve(
        ChatRequest(question=question, districts=["multan"]),
        QuestionRoute.EVIDENCE,
    )

    assert embedder.calls == 1
    assert len([key for key in cache.values if ":retrieval:" in key]) == 2
    assert len([key for key in cache.values if ":embedding:" in key]) == 1


def test_corpus_version_change_bypasses_old_retrieval_result(monkeypatch):
    repository = JsonRepository(DATA)
    cache = DictCache()
    embedder = CountingEmbedder()
    retriever = HybridRetriever(repository, embedder, cache=cache)
    version = {"value": "corpus-a"}
    monkeypatch.setattr(repository, "cache_version", lambda: version["value"])
    request = ChatRequest(question="What is Multan literacy?", districts=["multan"])

    retriever.retrieve(request, QuestionRoute.EXACT_FACT)
    version["value"] = "corpus-b"
    retriever.retrieve(request, QuestionRoute.EXACT_FACT)

    assert len([key for key in cache.values if ":retrieval:" in key]) == 2
    assert embedder.calls == 1


def test_malformed_retrieval_cache_is_deleted_and_rebuilt():
    repository = JsonRepository(DATA)
    cache = DictCache()
    retriever = HybridRetriever(repository, CountingEmbedder(), cache=cache)
    request = ChatRequest(question="What is Multan literacy?", districts=["multan"])

    expected = retriever.retrieve(request, QuestionRoute.EXACT_FACT)
    retrieval_key = next(key for key in cache.values if ":retrieval:" in key)
    cache.values[retrieval_key] = "not-json"
    actual = retriever.retrieve(request, QuestionRoute.EXACT_FACT)

    assert evidence_payload(actual) == evidence_payload(expected)
    assert cache.values[retrieval_key] != "not-json"


def test_cache_failure_falls_back_to_normal_retrieval():
    repository = JsonRepository(DATA)
    retriever = HybridRetriever(repository, CountingEmbedder(), cache=BrokenCache())

    results = retriever.retrieve(
        ChatRequest(question="What is Multan literacy?", districts=["multan"]),
        QuestionRoute.EXACT_FACT,
    )

    assert results
    assert results[0].id.startswith("fact-multan-")


def test_cache_keys_hash_questions_and_corpus_fingerprint_changes(tmp_path):
    question = "Private question text"
    key = cache_key("retrieval", {"query": normalized_query(question)})
    assert question.casefold() not in key

    data = tmp_path / "districts.json"
    data.write_text("first", encoding="utf-8")
    first = retrieval_corpus_version(data, "prototype-v1")
    data.write_text("second", encoding="utf-8")
    second = retrieval_corpus_version(data, "prototype-v1")
    assert first != second
