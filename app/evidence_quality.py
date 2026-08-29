"""Validated contracts for reviewed multi-period evidence."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FacilityKind = Literal[
    "hospitals",
    "dispensaries",
    "rhcs",
    "bhus",
    "tb_clinics",
    "sh_centers",
    "mch_centers",
    "trauma_centers",
]

EXPECTED_FACILITY_KINDS = {
    "hospitals",
    "dispensaries",
    "rhcs",
    "bhus",
    "tb_clinics",
    "sh_centers",
    "mch_centers",
    "trauma_centers",
}

FACILITY_LABELS = {
    "hospitals": "hospitals",
    "dispensaries": "dispensaries",
    "rhcs": "RHCs",
    "bhus": "BHUs",
    "tb_clinics": "TB clinics",
    "sh_centers": "sub-health centers",
    "mch_centers": "MCH centers",
    "trauma_centers": "trauma centers",
}


class ReviewedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publisher: str
    title: str
    edition: int
    snapshot_date: date
    period_label: str
    official_url: str
    acquisition_url: str
    local_file: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_date: date
    verification: list[str] = Field(min_length=1)


class MetricAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "accepted_with_limitations", "excluded", "pending_review"]
    reason: str


class ComparabilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str
    status: Literal["comparable", "comparable_with_limitations", "not_comparable"]
    table_title: str
    geography_level: Literal["district"]
    unit: Literal["count"]
    confirmed_dimensions: list[str] = Field(min_length=1)
    symbol_policy: str
    metric_assessments: dict[str, MetricAssessment]
    limitations: list[str] = Field(min_length=1)


class FacilityObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int | None = Field(default=None, ge=0)
    beds: int | None = Field(default=None, ge=0)


class HealthCapacityPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    snapshot_date: date
    locator: str
    pdf_page: int = Field(ge=1)
    facilities: dict[FacilityKind, FacilityObservation]

    @model_validator(mode="after")
    def require_all_facility_kinds(self) -> "HealthCapacityPeriod":
        actual = set(self.facilities)
        if actual != EXPECTED_FACILITY_KINDS:
            missing = sorted(EXPECTED_FACILITY_KINDS - actual)
            extra = sorted(actual - EXPECTED_FACILITY_KINDS)
            raise ValueError(f"facility keys differ; missing={missing}, extra={extra}")
        return self


class HealthCapacityDistrict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    periods: list[HealthCapacityPeriod] = Field(min_length=2)

    @model_validator(mode="after")
    def require_unique_ordered_periods(self) -> "HealthCapacityDistrict":
        dates = [period.snapshot_date for period in self.periods]
        if dates != sorted(set(dates)):
            raise ValueError("district periods must be unique and ordered by snapshot date")
        return self


class EvidenceAnomaly(BaseModel):
    model_config = ConfigDict(extra="forbid")

    district_slug: str
    snapshot_date: date
    metric: str
    note: str


class HealthCapacityDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    sources: dict[str, ReviewedSource]
    comparability: ComparabilityDecision
    districts: list[HealthCapacityDistrict] = Field(min_length=1)
    anomalies: list[EvidenceAnomaly] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "HealthCapacityDataset":
        slugs = [district.slug for district in self.districts]
        if len(slugs) != len(set(slugs)):
            raise ValueError("district slugs must be unique")

        known_sources = set(self.sources)
        known_slugs = set(slugs)
        for district in self.districts:
            for period in district.periods:
                if period.source_id not in known_sources:
                    raise ValueError(f"unknown source_id: {period.source_id}")
                source = self.sources[period.source_id]
                if period.snapshot_date != source.snapshot_date:
                    raise ValueError(
                        f"{district.slug} period does not match {period.source_id} snapshot date"
                    )
        for anomaly in self.anomalies:
            if anomaly.district_slug not in known_slugs:
                raise ValueError(f"anomaly references unknown district: {anomaly.district_slug}")
        return self


def load_health_capacity(path: Path) -> HealthCapacityDataset:
    """Load and validate the reviewed health-capacity evidence contract."""
    return HealthCapacityDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))


def health_capacity_change(
    dataset: HealthCapacityDataset,
    district_slug: str,
    facility: FacilityKind,
) -> dict:
    """Return a deterministic two-period change without converting dashes to zero."""
    district = next((item for item in dataset.districts if item.slug == district_slug), None)
    if district is None:
        raise KeyError(f"Unknown district: {district_slug}")
    previous, current = district.periods[0], district.periods[-1]
    previous_value = previous.facilities[facility]
    current_value = current.facilities[facility]

    def change(left: int | None, right: int | None) -> int | None:
        return None if left is None or right is None else right - left

    warnings = [
        anomaly.note
        for anomaly in dataset.anomalies
        if anomaly.district_slug == district_slug
        and anomaly.snapshot_date in {previous.snapshot_date, current.snapshot_date}
        and anomaly.metric.startswith(facility)
    ]
    return {
        "district_slug": district.slug,
        "district_name": district.name,
        "facility": facility,
        "comparability_group": dataset.comparability.group,
        "previous": {
            "snapshot_date": previous.snapshot_date.isoformat(),
            "count": previous_value.count,
            "beds": previous_value.beds,
            "source_id": previous.source_id,
            "locator": previous.locator,
        },
        "current": {
            "snapshot_date": current.snapshot_date.isoformat(),
            "count": current_value.count,
            "beds": current_value.beds,
            "source_id": current.source_id,
            "locator": current.locator,
        },
        "count_change": change(previous_value.count, current_value.count),
        "bed_change": change(previous_value.beds, current_value.beds),
        "warnings": warnings,
    }


def health_capacity_rates(
    dataset: HealthCapacityDataset,
    population_by_slug: dict[str, int],
    population_period: str = "Census 2023",
) -> list[dict]:
    """Normalize reviewed count observations per 100,000 with explicit denominators."""
    normalized = []
    for district in dataset.districts:
        population = population_by_slug.get(district.slug)
        if not population or population <= 0:
            raise ValueError(f"Missing positive population denominator for {district.slug}")
        for period in district.periods:
            for facility, observation in period.facilities.items():
                for measure in ("count", "beds"):
                    value = getattr(observation, measure)
                    normalized.append(
                        {
                            "district_slug": district.slug,
                            "facility": facility,
                            "measure": measure,
                            "period": period.snapshot_date.isoformat(),
                            "value": value,
                            "value_per_100k": (
                                None if value is None else round(value / population * 100_000, 6)
                            ),
                            "population_denominator": population,
                            "population_period": population_period,
                            "source_id": period.source_id,
                            "locator": period.locator,
                            "comparability_group": dataset.comparability.group,
                        }
                    )
    return normalized


def format_health_capacity_period(
    district_name: str,
    period: HealthCapacityPeriod,
) -> str:
    """Format one reviewed table row without inventing values for printed dashes."""
    parts = []
    for facility, observation in period.facilities.items():
        count = "not reported" if observation.count is None else f"{observation.count:,}"
        beds = "not reported" if observation.beds is None else f"{observation.beds:,}"
        parts.append(f"{FACILITY_LABELS[facility]}: {count} institutions, {beds} beds")
    return (
        f"Punjab Health Statistics Table 3 reports {district_name} public health capacity "
        f"at {period.snapshot_date.isoformat()}: "
        + "; ".join(parts)
        + ". Printed dashes are retained as not reported, not converted to zero."
    )
