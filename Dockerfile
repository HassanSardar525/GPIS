FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/huggingface

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY data/curated ./data/curated

# PyPI's Linux torch wheel can pull multi-gigabyte CUDA libraries. GPIS only
# performs CPU inference, so install the official CPU wheel first.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-build-isolation ".[observability]"

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m app.cli bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
