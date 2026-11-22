# Packaged original-page previews

These PNGs are rendered from checksum-pinned official reports. Filenames contain
the original document checksum prefix and one-based PDF page number. Page labels,
source links, original-document hashes, preview hashes, reviewed rectangles and
accessible text are registered in `../curated/history.json`.

Build with `python scripts/build_history.py`; verify with `python -m app.history`.
Only registered assets are served. Deploy this directory together with the curated
release. Raw PDFs are intentionally unnecessary at runtime. Screenshots and review
scratch files belong in `.cache`, not here. Preview images are full original pages;
the browser overlays the highlight separately.
