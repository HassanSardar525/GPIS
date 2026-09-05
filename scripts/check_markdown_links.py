"""Check that relative file links in Markdown resolve inside the repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^]]*]\(([^)]+)\)")


def main() -> int:
    failures: list[str] = []
    for document in ROOT.rglob("*.md"):
        if {".git", ".venv", ".cache", "node_modules"}.intersection(document.relative_to(ROOT).parts):
            continue
        text = document.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            target = target.strip().strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_text = unquote(target.split("#", 1)[0])
            resolved = (document.parent / path_text).resolve()
            if not resolved.exists():
                failures.append(f"{document.relative_to(ROOT)} -> {target}")
    if failures:
        print("Broken relative Markdown links:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("All relative Markdown links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
