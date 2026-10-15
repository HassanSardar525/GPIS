"""FastAPI application factory and versioned HTTP interface."""

from __future__ import annotations

import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Path as ApiPath, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langchain_groq import ChatGroq

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

from app.agent import AgentChatService
from app.cache import CacheBackend, build_cache
from app.schemas import CensusRankingResponse
from app.config import ROOT, Settings
from app.embeddings import MiniLMEmbedder
from app.errors import GPISException
from app.llm import FailingProvider, GeminiProvider, GroqProvider, LLMProvider
from app.observability import Observability, build_observability
from app.repositories import GPISRepository, JsonRepository
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DistrictDetail,
    DistrictListResponse,
    FacilityKind,
    HealthCapacityTrendResponse,
    HealthResponse,
    ModelListResponse,
    ModelOption,
    RankingResponse,
    SessionDeleteResponse,
    SessionResponse,
    TrendResponse,
)
from app.session_store import InMemorySessionStore, PostgresCheckpointRuntime, PostgresSessionStore
from app.services import ChatService, DistrictService, HybridRetriever


STATIC = ROOT / "app" / "static"


def build_repository(settings: Settings) -> GPISRepository:
    if settings.repository == "postgres":
        from app.database.repository import PostgresRepository

        return PostgresRepository(settings.database_url, settings.score_version)
    return JsonRepository(settings.curated_data_path, settings.score_version)


def build_chat_service(
    settings: Settings,
    repository: GPISRepository,
    observability: Observability | None = None,
    checkpointer: Any | None = None,
    cache: CacheBackend | None = None,
) -> ChatService:
    observability = observability or build_observability(settings)
    embedder = MiniLMEmbedder(settings.embedding_model) if repository.name == "postgres" else None
    retriever = HybridRetriever(
        repository,
        embedder,
        settings.semantic_threshold,
        observability=observability,
        cache=cache,
        retrieval_cache_ttl_seconds=settings.retrieval_cache_ttl_seconds,
        embedding_cache_ttl_seconds=settings.embedding_cache_ttl_seconds,
    )
    providers: dict[str, LLMProvider] = {}
    models: dict[str, Any] = {}

    if settings.groq_api_key:
        groq_provider = GroqProvider(
            settings.groq_api_key,
            settings.groq_model,
            settings.groq_base_url,
            settings.groq_timeout_seconds,
        )
        providers[f"groq:{settings.groq_model}"] = groq_provider
        providers["groq"] = groq_provider
        groq_model = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url.removesuffix("/openai/v1"),
            temperature=0.1,
            timeout=settings.groq_timeout_seconds,
            max_retries=1,
        )
        models[f"groq:{settings.groq_model}"] = groq_model
        models["groq"] = groq_model

    if settings.gemini_api_key:
        for g_model in ["gemini-1.5-flash", "gemini-2.0-flash"]:
            gemini_provider = GeminiProvider(
                api_key=settings.gemini_api_key,
                model=g_model,
                base_url=settings.gemini_base_url,
                timeout_seconds=settings.gemini_timeout_seconds,
            )
            providers[f"gemini:{g_model}"] = gemini_provider
            if g_model == settings.gemini_model:
                providers["gemini"] = gemini_provider
            if ChatGoogleGenerativeAI:
                try:
                    chat_gemini = ChatGoogleGenerativeAI(
                        model=g_model,
                        google_api_key=settings.gemini_api_key,
                        temperature=0.1,
                        timeout=settings.gemini_timeout_seconds,
                        max_retries=1,
                    )
                    models[f"gemini:{g_model}"] = chat_gemini
                    if g_model == settings.gemini_model:
                        models["gemini"] = chat_gemini
                except Exception:
                    pass

    primary_provider = next(iter(providers.values()), FailingProvider())
    fallback = ChatService(repository, retriever, primary_provider, observability, providers=providers)
    if not models:
        return fallback

    default_model = None
    if settings.gemini_api_key and settings.gemini_model in ("gemini-1.5-flash", "gemini-2.0-flash"):
        default_model = f"gemini:{settings.gemini_model}"
    elif settings.groq_api_key:
        default_model = f"groq:{settings.groq_model}"
    else:
        default_model = next(iter(models.keys()))

    return AgentChatService(
        repository,
        retriever,
        None,
        fallback,
        checkpointer=checkpointer,
        observability=observability,
        models=models,
        default_model=default_model,
    )


def create_app(
    settings: Settings | None = None,
    repository: GPISRepository | None = None,
    chat_service: ChatService | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    repository = repository or build_repository(settings)
    observability = build_observability(settings)
    cache = build_cache(settings.redis_url)
    district_service = DistrictService(repository)
    checkpoint_runtime = (
        PostgresCheckpointRuntime(settings.database_url)
        if repository.name == "postgres" and settings.database_url
        else None
    )
    session_store = (
        PostgresSessionStore(settings.database_url, settings.session_ttl_hours)
        if repository.name == "postgres" and settings.database_url
        else InMemorySessionStore(settings.session_ttl_hours)
    )
    supplied_chat_service = chat_service
    if not checkpoint_runtime:
        chat_service = chat_service or build_chat_service(
            settings, repository, observability, cache=cache
        )
        session_store.attach_checkpointer(getattr(chat_service, "checkpointer", None))

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        if checkpoint_runtime:
            await checkpoint_runtime.start()
            _application.state.chat_service = supplied_chat_service or build_chat_service(
                settings,
                repository,
                observability,
                checkpointer=checkpoint_runtime.checkpointer,
                cache=cache,
            )
            session_store.attach_checkpointer(checkpoint_runtime.checkpointer)
        try:
            yield
        finally:
            if checkpoint_runtime:
                await checkpoint_runtime.close()
            cache.close()

    application = FastAPI(
        title="Government Performance Intelligence System",
        version="0.2.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.repository = repository
    application.state.chat_service = chat_service
    application.state.observability = observability
    application.state.cache = cache
    application.state.session_store = session_store

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.exception_handler(GPISException)
    async def gpis_error(request: Request, error: GPISException):
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": str(error), "request_id": request.state.request_id}},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request did not match the API contract.",
                    "request_id": request.state.request_id,
                    "details": [
                        {key: value for key, value in item.items() if key != "ctx"}
                        for item in error.errors()
                    ],
                }
            },
        )

    @application.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        available = repository.healthcheck()
        return HealthResponse(
            status="ok" if available else "degraded",
            repository=repository.name,
            database=("available" if available else "unavailable") if repository.name == "postgres" else "not_configured",
            groq="configured" if settings.groq_api_key else "fallback",
            gemini="configured" if settings.gemini_api_key else "not_configured",
            embedding_model=settings.embedding_model,
            phoenix=observability.status,
            cache=cache.status,
        )

    @application.get("/api/v1/models", response_model=ModelListResponse)
    def available_models() -> ModelListResponse:
        options: list[ModelOption] = []
        if settings.groq_api_key:
            options.append(
                ModelOption(
                    id=f"groq:{settings.groq_model}",
                    name=f"Groq ({settings.groq_model})",
                    provider="groq",
                    is_default=(not settings.gemini_api_key),
                )
            )
        if settings.gemini_api_key:
            options.append(
                ModelOption(
                    id="gemini:gemini-1.5-flash",
                    name="Gemini 1.5 Flash",
                    provider="gemini",
                    is_default=(settings.gemini_model == "gemini-1.5-flash" or not settings.groq_api_key),
                )
            )
            options.append(
                ModelOption(
                    id="gemini:gemini-2.0-flash",
                    name="Gemini 2.0 Flash",
                    provider="gemini",
                    is_default=(settings.gemini_model == "gemini-2.0-flash"),
                )
            )
        options.append(
            ModelOption(
                id="fallback",
                name="Deterministic Fallback (Extractive)",
                provider="fallback",
                is_default=(len(options) == 0),
            )
        )
        if not any(opt.is_default for opt in options):
            options[0].is_default = True
        default_id = next(opt.id for opt in options if opt.is_default)
        return ModelListResponse(models=options, default_model=default_id)

    @application.get("/api/v1/districts", response_model=DistrictListResponse)
    def districts() -> DistrictListResponse:
        return DistrictListResponse(districts=district_service.list_districts(), metadata=repository.metadata())

    @application.get("/api/v1/districts/{slug}", response_model=DistrictDetail)
    def district(slug: str) -> DistrictDetail:
        return DistrictDetail.model_validate(district_service.get_district(slug))

    @application.get("/api/v1/census-rankings", response_model=CensusRankingResponse)
    def census_rankings(metric: str = Query(default="literacy_total_pct")) -> CensusRankingResponse:
        return CensusRankingResponse.model_validate(repository.census_ranking(metric))

    @application.get("/api/v1/rankings", response_model=RankingResponse)
    def ranking(category: str = Query(default="overall")) -> RankingResponse:
        return RankingResponse(category=category, rankings=district_service.rankings(category))

    @application.get("/api/v1/districts/{slug}/trends/development-budget", response_model=TrendResponse)
    def development_budget_trend(slug: str) -> TrendResponse:
        return TrendResponse.model_validate(district_service.development_trend(slug))

    @application.get(
        "/api/v1/districts/{slug}/trends/health-capacity",
        response_model=HealthCapacityTrendResponse,
    )
    def health_capacity_trend(slug: str, facility: FacilityKind = Query()) -> HealthCapacityTrendResponse:
        return HealthCapacityTrendResponse.model_validate(
            district_service.health_capacity_trend(slug, facility)
        )

    @application.post("/api/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or str(uuid.uuid4())
        request = request.model_copy(update={"session_id": session_id})
        session_store.ensure_active(session_id)
        response = await application.state.chat_service.answer(request)
        session_store.touch(session_id)
        return response.model_copy(update={"session_id": session_id})

    @application.get("/api/v1/sessions/{session_id}", response_model=SessionResponse)
    def session_status(
        session_id: str = ApiPath(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
    ) -> SessionResponse:
        return SessionResponse.model_validate(session_store.get(session_id))

    @application.delete("/api/v1/sessions/{session_id}", response_model=SessionDeleteResponse)
    async def delete_session(
        session_id: str = ApiPath(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
    ) -> SessionDeleteResponse:
        await session_store.delete(session_id)
        return SessionDeleteResponse(session_id=session_id)

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    application.mount("/static", StaticFiles(directory=STATIC), name="static")
    return application


app = create_app()
