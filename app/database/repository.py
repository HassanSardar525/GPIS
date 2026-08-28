"""PostgreSQL repository implementing structured and hybrid retrieval primitives."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import joinedload

from app.database.models import DatasetMetadata, District, EvidenceChunk, Observation, RetrievalTrace, ScoreResult, Source
from app.database.session import session_factory
from app.errors import DistrictNotFound, InvalidCategory, TrendUnavailable
from app.evidence_quality import EXPECTED_FACILITY_KINDS
from app.facts import format_fact, requested_metrics
from app.schemas import Citation, RetrievedEvidence
from app.score_explanations import format_score_explanation, requested_score_category
from app.temporal import development_budget_trend


RANKING_CATEGORIES = {"overall", "education", "health", "accountability"}
CURRENT_METRICS = {
    "education": {"literacy_total_pct", "literacy_male_pct", "literacy_female_pct", "out_of_school_children_5_16"},
    "health": {"government_dispensaries", "bhus", "rhcs", "thq_hospitals", "dhq_hospitals", "dhdc"},
    "accountability": {"overall_budget_lapse_pct", "development_budget_lapse_pct", "audited_formations", "total_formations"},
}


class PostgresRepository:
    name = "postgres"

    def __init__(self, database_url: str, score_version: str):
        self.database_url = database_url
        self.score_version = score_version
        self.sessions = session_factory(database_url)

    def healthcheck(self) -> bool:
        try:
            with self.sessions() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def metadata(self) -> dict:
        with self.sessions() as session:
            rows = session.scalars(select(DatasetMetadata)).all()
            return {row.key: row.value for row in rows}

    def _scores(self, session) -> dict[int, dict[str, float]]:
        rows = session.scalars(
            select(ScoreResult).where(ScoreResult.version == self.score_version)
        ).all()
        scores: defaultdict[int, dict[str, float]] = defaultdict(dict)
        for row in rows:
            scores[row.district_id][row.category] = float(row.score)
        return scores

    def list_districts(self) -> list[dict]:
        with self.sessions() as session:
            districts = session.scalars(select(District).order_by(District.name)).all()
            scores = self._scores(session)
            return [
                {"slug": district.slug, "name": district.name, "scores": scores[district.id]}
                for district in districts
            ]

    def rankings(self, category: str) -> list[dict]:
        if category not in RANKING_CATEGORIES:
            raise InvalidCategory(f"Unknown ranking category: {category}")
        with self.sessions() as session:
            rows = session.execute(
                select(District.slug, District.name, ScoreResult.score)
                .join(ScoreResult, ScoreResult.district_id == District.id)
                .where(ScoreResult.version == self.score_version, ScoreResult.category == category)
                .order_by(ScoreResult.score.desc(), District.name)
            ).all()
            return [
                {"rank": rank, "slug": row.slug, "name": row.name, "score": float(row.score)}
                for rank, row in enumerate(rows, start=1)
            ]

    def development_trend(self, slug: str) -> dict:
        metric_keys = {"development_final_grant_million_pkr", "development_expenditure_million_pkr"}
        with self.sessions() as session:
            district = session.scalar(select(District).where(District.slug == slug))
            if not district:
                raise DistrictNotFound(f"District '{slug}' was not found")
            rows = session.execute(
                select(Observation, Source)
                .join(Source, Source.id == Observation.source_id)
                .where(Observation.district_id == district.id, Observation.metric_key.in_(metric_keys))
                .order_by(Observation.period, Observation.metric_key)
            ).all()
            periods: dict[str, dict[str, float]] = defaultdict(dict)
            for observation, _source in rows:
                periods[observation.period][observation.metric_key] = float(observation.value)
            try:
                trend = development_budget_trend(periods)
            except ValueError as error:
                raise TrendUnavailable(str(error)) from error
            if not rows:
                raise TrendUnavailable(f"Comparable development-budget periods are unavailable for {district.name}")
            observation, source = rows[0]
            evidence_chunk = session.scalar(
                select(EvidenceChunk).where(
                    EvidenceChunk.district_id == district.id,
                    EvidenceChunk.id.like("%-development-trend"),
                )
            )
            if not evidence_chunk:
                raise TrendUnavailable(f"Development-trend evidence is unavailable for {district.name}")
            return {
                "district_slug": slug,
                "district_name": district.name,
                **trend,
                "citation": {
                    "evidence_id": evidence_chunk.id,
                    "source_id": source.id,
                    "publisher": source.publisher,
                    "title": source.title,
                    "period": source.period,
                    "url": source.url,
                    "locator": evidence_chunk.locator,
                },
            }

    def health_capacity_trend(self, slug: str, facility: str) -> dict:
        if facility not in EXPECTED_FACILITY_KINDS:
            raise InvalidCategory(f"Unknown health facility category: {facility}")
        metric_keys = {f"phs_{facility}_count", f"phs_{facility}_beds"}
        with self.sessions() as session:
            district = session.scalar(select(District).where(District.slug == slug))
            if not district:
                raise DistrictNotFound(f"District '{slug}' was not found")
            observations = session.scalars(
                select(Observation).where(
                    Observation.district_id == district.id,
                    Observation.metric_key.in_(metric_keys),
                    Observation.comparability_group == "phs-table-3-public-capacity-v1",
                )
            ).all()
            chunks = session.scalars(
                select(EvidenceChunk)
                .options(joinedload(EvidenceChunk.source))
                .where(
                    EvidenceChunk.district_id == district.id,
                    EvidenceChunk.id.like(f"{slug}-health-capacity-%"),
                )
                .order_by(EvidenceChunk.period)
            ).all()
            if len(chunks) < 2:
                raise TrendUnavailable(f"Comparable health-capacity periods are unavailable for {district.name}")
            values = {(row.period, row.metric_key): row for row in observations}
            warnings = list(
                dict.fromkeys(flag for row in observations for flag in (row.quality_flags or []))
            )
            periods = []
            for chunk in chunks:
                count = values.get((chunk.period, f"phs_{facility}_count"))
                beds = values.get((chunk.period, f"phs_{facility}_beds"))
                periods.append(
                    {
                        "snapshot_date": chunk.period,
                        "count": int(count.value) if count else None,
                        "beds": int(beds.value) if beds else None,
                        "citation": {
                            "evidence_id": chunk.id,
                            "source_id": chunk.source.id,
                            "publisher": chunk.source.publisher,
                            "title": chunk.source.title,
                            "period": chunk.source.period,
                            "url": chunk.source.url,
                            "locator": chunk.locator,
                        },
                    }
                )

            def difference(left, right):
                return None if left is None or right is None else right - left

            metadata = session.get(DatasetMetadata, "health_capacity_comparability")
            return {
                "district_slug": district.slug,
                "district_name": district.name,
                "facility": facility,
                "comparability_group": "phs-table-3-public-capacity-v1",
                "periods": periods,
                "count_change": difference(periods[0]["count"], periods[-1]["count"]),
                "bed_change": difference(periods[0]["beds"], periods[-1]["beds"]),
                "warnings": warnings,
                "limitations": metadata.value.get("limitations", []) if metadata else [],
            }

    def trend_search(self, query: str, district_slugs: list[str], limit: int) -> list[RetrievedEvidence]:
        selected = district_slugs or [item["slug"] for item in self.list_districts()]
        trends = [self.development_trend(slug) for slug in selected]
        reverse = not any(word in query.casefold() for word in ("decline", "decrease", "least", "worst"))
        trends.sort(key=lambda item: item["change_percentage_points"], reverse=reverse)
        results = []
        for rank, trend in enumerate(trends[:limit], start=1):
            previous, current = trend["periods"]
            citation = Citation(**trend["citation"])
            results.append(
                RetrievedEvidence(
                    id=citation.evidence_id,
                    district_slug=trend["district_slug"],
                    district_name=trend["district_name"],
                    category="accountability",
                    text=(
                        f"{trend['district_name']} development-budget utilization was {previous['utilization_pct']:.2f}% "
                        f"in {previous['period']} and {current['utilization_pct']:.2f}% in {current['period']}; "
                        f"it {trend['direction']} by {abs(trend['change_percentage_points']):.2f} percentage points."
                    ),
                    source_id=citation.source_id,
                    locator=citation.locator,
                    period=citation.period,
                    keyword_rank=rank,
                    citation=citation,
                )
            )
        return results

    def score_search(self, query, district_slugs, category, limit):
        score_category = requested_score_category(query, category)
        with self.sessions() as session:
            statement = (
                select(ScoreResult, District)
                .join(District, District.id == ScoreResult.district_id)
                .where(
                    ScoreResult.version == self.score_version,
                    ScoreResult.category == score_category,
                )
            )
            if district_slugs:
                statement = statement.where(District.slug.in_(district_slugs))
                statement = statement.order_by(District.name)
            elif any(word in query.casefold() for word in ("best", "highest", "rank")):
                statement = statement.order_by(ScoreResult.score.desc(), District.name)
            elif any(word in query.casefold() for word in ("lowest", "worst")):
                statement = statement.order_by(ScoreResult.score.asc(), District.name)
            else:
                statement = statement.order_by(District.name)
            rows = session.execute(statement.limit(limit)).all()
            source = session.get(Source, "gpis_methodology_v1")
            if not source:
                return []
            results = []
            for rank, (score, district) in enumerate(rows, start=1):
                evidence_id = f"score-{district.slug}-{score_category}-{self.score_version}"
                locator = f"{score_category.title()} formula and stored components"
                results.append(
                    RetrievedEvidence(
                        id=evidence_id,
                        district_slug=district.slug,
                        district_name=district.name,
                        category=score_category,
                        text=format_score_explanation(
                            district.name,
                            score_category,
                            float(score.score),
                            {key: float(value) for key, value in score.components.items()},
                        ),
                        source_id=source.id,
                        locator=locator,
                        period=source.period,
                        keyword_rank=rank,
                        citation=Citation(
                            evidence_id=evidence_id,
                            source_id=source.id,
                            publisher=source.publisher,
                            title=source.title,
                            period=source.period,
                            url=source.url,
                            locator=locator,
                        ),
                    )
                )
            return results

    def get_district(self, slug: str) -> dict:
        with self.sessions() as session:
            district = session.scalar(select(District).where(District.slug == slug))
            if not district:
                raise DistrictNotFound(f"District '{slug}' was not found")
            observations = session.scalars(
                select(Observation).where(Observation.district_id == district.id)
            ).all()
            score_rows = session.scalars(
                select(ScoreResult).where(
                    ScoreResult.district_id == district.id,
                    ScoreResult.version == self.score_version,
                )
            ).all()
            evidence_rows = session.scalars(
                select(EvidenceChunk)
                .options(joinedload(EvidenceChunk.source))
                .where(EvidenceChunk.district_id == district.id)
                .order_by(EvidenceChunk.id)
            ).all()

            categories: dict[str, dict] = {"education": {}, "health": {}, "accountability": {}}
            for observation in observations:
                if observation.metric_key in CURRENT_METRICS.get(observation.category, set()):
                    value = float(observation.value)
                    categories[observation.category][observation.metric_key] = int(value) if value.is_integer() else value
            scores = {row.category: float(row.score) for row in score_rows}
            sources = {
                row.source.id: {
                    "publisher": row.source.publisher,
                    "title": row.source.title,
                    "period": row.source.period,
                    "url": row.source.url,
                    "local_file": row.source.local_file,
                    "sha256": row.source.sha256,
                }
                for row in evidence_rows
            }
            facilities = sum(
                categories["health"].get(field, 0)
                for field in ("government_dispensaries", "bhus", "rhcs", "thq_hospitals", "dhq_hospitals", "dhdc")
            )
            derived = {
                "facility_count": facilities,
                "facilities_per_100k": round(facilities / district.population_2023 * 100_000, 2),
                "scores": scores,
            }
            evidence = [
                {
                    "id": row.id,
                    "category": row.category,
                    "text": row.text,
                    "source_id": row.source_id,
                    "locator": row.locator,
                }
                for row in evidence_rows
            ]
            rankings = {
                category: next(item for item in self.rankings(category) if item["slug"] == slug)
                for category in RANKING_CATEGORIES
            }
            return {
                "slug": district.slug,
                "name": district.name,
                "population_2023": district.population_2023,
                **categories,
                "derived": derived,
                "evidence": evidence,
                "rankings": rankings,
                "sources": sources,
                "metadata": self.metadata(),
            }

    def _filters(self, statement, district_slugs: list[str], category: str | None, period: str | None):
        if district_slugs:
            statement = statement.where(
                or_(District.slug.in_(district_slugs), EvidenceChunk.district_id.is_(None))
            )
        if category:
            statement = statement.where(EvidenceChunk.category == category)
        if period:
            statement = statement.where(EvidenceChunk.period.ilike(f"%{period}%"))
        return statement

    @staticmethod
    def _evidence(row, keyword_rank=None, vector_rank=None, similarity=None) -> RetrievedEvidence:
        chunk, district, source = row
        return RetrievedEvidence(
            id=chunk.id,
            district_slug=district.slug if district else "project",
            district_name=district.name if district else "GPIS Project",
            category=chunk.category,
            text=chunk.text,
            source_id=chunk.source_id,
            locator=chunk.locator,
            period=chunk.period,
            keyword_rank=keyword_rank,
            vector_rank=vector_rank,
            semantic_similarity=similarity,
            citation=Citation(
                evidence_id=chunk.id,
                source_id=source.id,
                publisher=source.publisher,
                title=source.title,
                period=source.period,
                url=source.url,
                locator=chunk.locator,
            ),
        )

    def keyword_search(self, query, district_slugs, category, period, limit):
        with self.sessions() as session:
            ts_query = func.websearch_to_tsquery("english", query)
            rank = func.ts_rank_cd(EvidenceChunk.search_vector, ts_query).label("rank")
            statement = (
                select(EvidenceChunk, District, Source, rank)
                .outerjoin(District, District.id == EvidenceChunk.district_id)
                .join(Source, Source.id == EvidenceChunk.source_id)
                .where(EvidenceChunk.search_vector.op("@@")(ts_query))
            )
            statement = self._filters(statement, district_slugs, category, period).order_by(rank.desc()).limit(limit)
            return [self._evidence(row[:3], keyword_rank=index) for index, row in enumerate(session.execute(statement), start=1)]

    def fact_search(self, query, district_slugs, limit):
        metrics = requested_metrics(query)
        if not metrics:
            return []
        with self.sessions() as session:
            statement = (
                select(Observation, District, Source)
                .join(District, District.id == Observation.district_id)
                .join(Source, Source.id == Observation.source_id)
                .where(Observation.metric_key.in_(metrics))
            )
            if district_slugs:
                statement = statement.where(District.slug.in_(district_slugs))
            rows = session.execute(statement.order_by(District.name, Observation.metric_key).limit(limit)).all()
            results = []
            for rank, (observation, district, source) in enumerate(rows, start=1):
                evidence_id = f"fact-{district.slug}-{observation.metric_key}"
                results.append(
                    RetrievedEvidence(
                        id=evidence_id,
                        district_slug=district.slug,
                        district_name=district.name,
                        category=observation.category,
                        text=format_fact(district.name, observation.metric_key, float(observation.value), observation.unit),
                        source_id=source.id,
                        locator=observation.locator,
                        period=observation.period,
                        keyword_rank=rank,
                        citation=Citation(
                            evidence_id=evidence_id,
                            source_id=source.id,
                            publisher=source.publisher,
                            title=source.title,
                            period=source.period,
                            url=source.url,
                            locator=observation.locator,
                        ),
                    )
                )
            return results

    def vector_search(self, embedding, district_slugs, category, period, limit):
        with self.sessions() as session:
            distance = EvidenceChunk.embedding.cosine_distance(embedding).label("distance")
            statement = (
                select(EvidenceChunk, District, Source, distance)
                .outerjoin(District, District.id == EvidenceChunk.district_id)
                .join(Source, Source.id == EvidenceChunk.source_id)
                .where(EvidenceChunk.embedding.is_not(None))
            )
            statement = self._filters(statement, district_slugs, category, period).order_by(distance).limit(limit)
            results = []
            for index, row in enumerate(session.execute(statement), start=1):
                results.append(self._evidence(row[:3], vector_rank=index, similarity=max(0.0, 1 - float(row.distance))))
            return results

    def record_trace(self, trace: dict) -> None:
        with self.sessions.begin() as session:
            session.add(RetrievalTrace(**trace))
