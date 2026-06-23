"""Optional checkpoint: catch audio uploaded DIRECTLY into the NotebookLM web UI.

The normal flow scans an audio folder. But if you sometimes upload a recording straight
into a NotebookLM notebook (never touching the folder), the scan misses it. List the
notebook id(s) under `notebooklm.scan_notebook_ids` in config and this module finds
audio sources there that are READY (indexed), RECENT, and have NO minutes file yet —
run.py then grounds each into minutes from the existing source (no re-upload).

Gated by recency (so it never mass-backfills an old notebook) and by the minutes-file
check (so it never re-minutes something already done). Off by default (empty list).
"""
import datetime

from meeting_minutes import gather, config
from meeting_minutes import notebooklm as nb

AUDIO_EXTS = (".m4a", ".mp3", ".wav", ".mp4", ".aac", ".ogg", ".flac")


def _is_audio(title):
    return bool(title) and title.lower().endswith(AUDIO_EXTS)


def _recent(created_at, days, today=None):
    """True if created_at (ISO) is within `days` of today. days=0 disables the window."""
    if not days:
        return True
    if not created_at:
        return False
    try:
        d = datetime.date.fromisoformat(str(created_at)[:10])
    except ValueError:
        return False
    return 0 <= ((today or datetime.date.today()) - d).days <= days


def _cfg_for(cfg, notebook_id):
    """Shallow cfg copy whose notebook_id is `notebook_id` — lets the existing
    notebooklm helpers (list_sources, generate_minutes) target a scan notebook."""
    return {**cfg, "notebooklm": {**cfg.get("notebooklm", {}), "notebook_id": notebook_id}}


def scan_unminuted(cfg=None, days=7, runner=None, today=None):
    """Audio sources in the configured scan notebook(s) that are ready, recent, and have
    no minutes file yet. Returns dicts: {notebook_id, source_id, title, stem}."""
    cfg = cfg or config.load()
    runner = runner or nb._default_runner
    out, seen = [], set()
    for nbid in (cfg.get("notebooklm", {}).get("scan_notebook_ids") or []):
        cfg2 = _cfg_for(cfg, nbid)
        for r in nb.list_sources(runner=runner, cfg=cfg2):
            title = r.get("title") or r.get("name") or ""
            if not _is_audio(title) or not nb._is_ready(r):
                continue
            if not _recent(r.get("created_at"), days, today):
                continue
            stem = title.rsplit(".", 1)[0]
            if stem in seen or gather.is_already_done(title, cfg):
                continue
            seen.add(stem)
            out.append({"notebook_id": nbid, "source_id": r.get("id") or r.get("source_id"),
                        "title": title, "stem": stem})
    return out
