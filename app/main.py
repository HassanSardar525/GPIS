"""FastAPI application factory and versioned HTTP interface."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import ROOT, Settings
from app.embeddings import MiniLMEmbedder
from app.errors import GPISException
from app.llm import FailingProvider, GroqProvider
from app.repositories import GPISRepository, JsonRepository
from app.schemas import ChatRequest, ChatResponse, DistrictDetail, DistrictListResponse, HealthResponse, RankingResponse
from app.services import ChatService, DistrictService, HybridRetriever


STATIC = ROOT / "app" / "static"


def build_repository(settings: Settings) -> GPISRepository:
    if settings.repository == "postgres":
        from app.database.repository import PostgresRepository

        return PostgresRepository(settings.database_url, settings.score_version)
    return JsonRepository(settings.curated_data_path)


def build_chat_service(settings: Settings, repository: GPISRepository) -> ChatService:
    embedder = MiniLMEmbedder(settings.embedding_model) if repository.name == "postgres" else None
    retriever = HybridRetriever(repository, embedder, settings.semantic_threshold)
    provider = (
        GroqProvider(
            settings.groq_api_key,
            settings.groq_model,
            settings.groq_base_url,
            settings.groq_timeout_seconds,
        )
        if settings.groq_api_key
        else FailingProvider()
    )
    return ChatService(repository, retriever, provider)


def create_app(
    settings: Settings | None = None,
    repository: GPISRepository | None = None,
    chat_service: ChatService | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    repository = repository or build_repository(settings)
    district_service = DistrictService(repository)
    chat_service = chat_service or build_chat_service(settings, repository)

    application = FastAPI(
        title="Government Performance Intelligence System",
        version="0.2.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    application.state.settings = settings
    application.state.repository = repository
    application.state.chat_service = chat_service

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
            embedding_model=settings.embedding_model,
        )

    @application.get("/api/v1/districts", response_model=DistrictListResponse)
    def districts() -> DistrictListResponse:
        return DistrictListResponse(districts=district_service.list_districts(), metadata=repository.metadata())

    @application.get("/api/v1/districts/{slug}", response_model=DistrictDetail)
    def district(slug: str) -> DistrictDetail:
        return DistrictDetail.model_validate(district_service.get_district(slug))

    @application.get("/api/v1/rankings", response_model=RankingResponse)
    def ranking(category: str = Query(default="overall")) -> RankingResponse:
        return RankingResponse(category=category, rankings=district_service.rankings(category))

    @application.post("/api/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        return await chat_service.answer(request)

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    application.mount("/static", StaticFiles(directory=STATIC), name="static")
    return application


app = create_app()
