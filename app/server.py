"""Compatibility launcher for `python -m app.server`."""

from __future__ import annotations

import asyncio
import sys
import uvicorn


def main() -> None:
    loop = asyncio.SelectorEventLoop if sys.platform == "win32" else "auto"
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False, loop=loop)


if __name__ == "__main__":
    main()
