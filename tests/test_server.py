import asyncio

from app import server


def test_windows_launcher_passes_selector_loop_to_uvicorn(monkeypatch):
    captured = {}

    monkeypatch.setattr(server.sys, "platform", "win32")
    monkeypatch.setattr(server.uvicorn, "run", lambda *args, **kwargs: captured.update(kwargs))

    server.main()

    assert captured["loop"] is asyncio.SelectorEventLoop
