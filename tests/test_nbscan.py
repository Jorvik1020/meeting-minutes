"""Direct-upload checkpoint: scan a NotebookLM notebook for un-minuted audio sources."""
import datetime

from meeting_minutes import config, notebooklm_scan as scan
from meeting_minutes import notebooklm as nb

TODAY = datetime.date(2026, 6, 23)


def _row(title, status="ready", created="2026-06-23T13:00", sid="s1"):
    return {"title": title, "status": status, "created_at": created, "id": sid}


def _cfg(scan_ids):
    cfg = config.load()
    return {**cfg, "notebooklm": {**cfg.get("notebooklm", {}), "scan_notebook_ids": scan_ids}}


def _patch(monkeypatch, rows, done=()):
    monkeypatch.setattr(nb, "list_sources", lambda runner=None, cfg=None: rows)
    monkeypatch.setattr(scan.gather, "is_already_done",
                        lambda title, cfg=None: any(d in title for d in done))


def test_disabled_when_no_scan_ids(monkeypatch):
    _patch(monkeypatch, [_row("acme 2026.06.23.m4a")])
    assert scan.scan_unminuted(_cfg([]), days=7, today=TODAY) == []


def test_picks_ready_recent_unminuted_audio(monkeypatch):
    _patch(monkeypatch, [_row("acme 2026.06.23.m4a")])
    got = scan.scan_unminuted(_cfg(["nb1"]), days=7, today=TODAY)
    assert len(got) == 1 and got[0]["stem"] == "acme 2026.06.23"
    assert got[0]["notebook_id"] == "nb1" and got[0]["source_id"] == "s1"


def test_skips_non_audio(monkeypatch):
    _patch(monkeypatch, [_row("Some article - Wikipedia"), _row("notes.html")])
    assert scan.scan_unminuted(_cfg(["nb1"]), days=7, today=TODAY) == []


def test_skips_not_ready(monkeypatch):
    _patch(monkeypatch, [_row("x 2026.06.23.m4a", status="preparing")])
    assert scan.scan_unminuted(_cfg(["nb1"]), days=7, today=TODAY) == []


def test_skips_old(monkeypatch):
    _patch(monkeypatch, [_row("x 2026.06.01.m4a", created="2026-06-01T10:00")])
    assert scan.scan_unminuted(_cfg(["nb1"]), days=7, today=TODAY) == []


def test_skips_already_minuted(monkeypatch):
    _patch(monkeypatch, [_row("acme 2026.06.23.m4a")], done=["acme 2026.06.23"])
    assert scan.scan_unminuted(_cfg(["nb1"]), days=7, today=TODAY) == []


def test_status_id_ready_form(monkeypatch):
    row = {"title": "x 2026.06.23.m4a", "status_id": 2, "created_at": "2026-06-23", "source_id": "z"}
    monkeypatch.setattr(nb, "list_sources", lambda runner=None, cfg=None: [row])
    monkeypatch.setattr(scan.gather, "is_already_done", lambda title, cfg=None: False)
    got = scan.scan_unminuted(_cfg(["nb1"]), days=7, today=TODAY)
    assert got and got[0]["source_id"] == "z"
