"""Optional OpenTelemetry/Phoenix tracing with a dependency-free no-op fallback."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Iterator, Protocol


LOGGER = logging.getLogger(__name__)


def _attribute_value(value: Any):
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(item, (str, bool, int, float)) for item in value):
        return list(value)
    return json.dumps(value, sort_keys=True)


class SpanHandle(Protocol):
    def set_attributes(self, attributes: dict[str, Any]) -> None: ...


class Observability(Protocol):
    status: str

    def span(self, name: str, kind: str, attributes: dict[str, Any] | None = None): ...


class _NoopSpan:
    def set_attributes(self, attributes: dict[str, Any]) -> None:
        return None


class NoopObservability:
    def __init__(self, status: str = "disabled"):
        self.status = status

    @contextmanager
    def span(
        self, name: str, kind: str, attributes: dict[str, Any] | None = None
    ) -> Iterator[_NoopSpan]:
        yield _NoopSpan()


class _OpenTelemetrySpan:
    def __init__(self, span):
        self._span = span

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        for key, value in attributes.items():
            converted = _attribute_value(value)
            if converted is not None:
                self._span.set_attribute(key, converted)


class PhoenixObservability:
    status = "configured"

    def __init__(self, tracer):
        self.tracer = tracer

    @contextmanager
    def span(self, name: str, kind: str, attributes: dict[str, Any] | None = None):
        initial = {"openinference.span.kind": kind, **(attributes or {})}
        converted = {
            key: value
            for key, raw in initial.items()
            if (value := _attribute_value(raw)) is not None
        }
        with self.tracer.start_as_current_span(name, attributes=converted) as active:
            yield _OpenTelemetrySpan(active)


def build_observability(settings) -> Observability:
    if not settings.phoenix_enabled:
        return NoopObservability()
    try:
        from opentelemetry import trace
        from phoenix.otel import register

        options = {
            "project_name": settings.phoenix_project_name,
            "batch": False,
        }
        if settings.phoenix_endpoint:
            options.update(endpoint=settings.phoenix_endpoint, protocol="http/protobuf")
        register(**options)
        return PhoenixObservability(trace.get_tracer("gpis.rag"))
    except Exception as error:
        LOGGER.warning("Phoenix tracing unavailable: %s", type(error).__name__)
        return NoopObservability(status="unavailable")
