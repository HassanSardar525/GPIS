# Contributing

## Development workflow

1. Read `docs/STATUS.md` and select one item from `docs/BACKLOG.md`.
2. Create a focused branch such as `feature/hybrid-retrieval` or `fix/source-citation`.
3. Keep factual data changes separate from UI-only changes when practical.
4. Update methodology or decision documentation when behavior changes.
5. Run the tests before committing.

```powershell
python -m pytest -q
python scripts/run_rag_evaluation.py --enforce
python scripts/check_markdown_links.py
```

## Evidence requirements

Every new factual observation must include an official publisher, document title, period, URL, and page/table locator. Verify at least one raw value manually. Do not use speeches, manifestos, news articles, or project announcements as score inputs.

## Scoring requirements

- Keep scoring outside the retrieval/generation layer.
- Version every formula change.
- Add a hand-calculated test for new or changed formulas.
- Document directionality, normalization, weights, missing-data behavior, and limitations.

## Pull requests

Describe what changed, why it changed, user impact, evidence implications, and validation performed. Keep pull requests small enough to review without guessing intent.
