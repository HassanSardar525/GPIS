# GPIS contributor guide

GPIS helps people compare Punjab districts and inspect the official evidence behind each figure. The FastAPI application serves a static browser frontend, PostgreSQL/pgvector retrieval, deterministic scores, and optional Groq or Gemini generation. Production runs on Render.

## Workflow

- Before starting, create a separate branch (`feat/<name>`, `fix/<name>`, or `chore/<name>`). Never work on main.
- Work in phases tracked in [PLANS.md](PLANS.md). Start each phase on its own branch. Make each reproduced fix on a dedicated fix branch.
- Tick each completed phase in PLANS.md first, then commit with a clear message. Record blocked checks as pending.
- Push phase branches to GitHub and open a release pull request into main. Stack dependent branches on the preceding phase. Merge only after the release checks in [docs/testing.md](docs/testing.md) pass. Deploy production only from merged main.
- For any UI work, use `$frontend-design`. Define fonts, colors, and spacing tokens first. After building, screenshot at mobile and desktop widths and fix issues.
- Keep score calculations deterministic and versioned. Preserve source periods, district boundaries, missing values, and evidence locators. Qualify incomplete officeholder dates.
- Keep visitor chats outside hosted evaluation. Use reviewed, curated questions for LangSmith experiments.

## Commands

Run from the repository root with Python 3.11 and an activated virtual environment.

```powershell
python -m pip install -e ".[dev,browser,ingestion]"
docker compose up -d database redis
python -m alembic upgrade head
python -m app.cli bootstrap
python -m app.cli ingest-documents --source all
python -m app.server
python -m pytest -q
python scripts/check_markdown_links.py
git diff --check
```

Set GPIS_REPOSITORY=postgres and GPIS_DATABASE_URL before migration and ingestion. Use the Python module and Markdown link checks in [testing](docs/testing.md) for lint. See [.env.example](.env.example) for settings.

## Folder map

- `app/` contains API, retrieval, generation, scores, and history. `app/static/` contains the browser UI.
- `app/database/` contains model and repository implementations. `alembic/` contains migrations.
- `data/curated/` holds reviewed contracts. `data/evidence/` holds packaged source previews. `data/raw/` holds local originals.
- `tests/` and `scripts/` contain regression suites, evaluations and data maintenance commands.
- Read [architecture](docs/architecture.md), [conventions](docs/conventions.md), and [testing](docs/testing.md) before changing their respective areas.
