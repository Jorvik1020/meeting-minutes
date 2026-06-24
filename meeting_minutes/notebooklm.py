"""Thin wrapper over the notebooklm-py CLI (https://github.com/...).

NotebookLM transcribes + indexes audio server-side, then answers grounded questions —
so it does transcription AND summarisation with no API key and no per-day quota.
Binary path + notebook id come from config.yaml.
"""
import re
import json
import subprocess

from meeting_minutes import config

_AUTH = ("authentication expired", "auth required", "401 unauthorized",
         "please log in", "not authenticated", "invalid_grant",
         "authentication expired or invalid", "redirected to",
         "re-authenticate", "accounts.google.com", "weblitesignin")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_CIT = re.compile(r"\s*\[\d+(?:\s*[-,]\s*\d+)*\]")  # [3] · [2, 3] · [7-9] · [1, 2, 3]


def _bin(cfg=None):
    return (cfg or config.load())["notebooklm"]["binary"]


def _nb(cfg=None):
    return (cfg or config.load())["notebooklm"]["notebook_id"]


def _default_runner(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def _out(r):
    return getattr(r, "stdout", "") or ""


def login_refresh(runner=_default_runner, cfg=None):
    return runner([_bin(cfg), "login", "--browser-cookies", "chrome"])


def _run(args, runner=_default_runner, cfg=None):
    cmd = [_bin(cfg), *args]
    r = runner(cmd)
    blob = (_out(r) + (getattr(r, "stderr", "") or "")).lower()
    if any(m in blob for m in _AUTH):
        login_refresh(runner, cfg)
        r = runner(cmd)
    return r


def auth_ok(runner=_default_runner, cfg=None):
    """True iff NotebookLM accepts the current session for a REAL API call.

    `notebooklm doctor` only checks that a session cookie exists on disk — but an
    EXPIRED cookie still passes that while every real call redirects to Google
    sign-in. So we make an actual read (`list`) and look for the sign-in/redirect
    markers. Use this as a preflight so the job fails fast (warn + local fallback)
    instead of uploading audio that can never index and writing an ungrounded
    apology to the minutes file. Fix on failure: open Chrome -> notebooklm.google.com
    -> sign in, then `notebooklm login --browser-cookies chrome`."""
    r = runner([_bin(cfg), "list"])
    if getattr(r, "returncode", 0) != 0:
        return False
    blob = (_out(r) + (getattr(r, "stderr", "") or "")).lower()
    return not any(m in blob for m in _AUTH)


def source_add(path, runner=_default_runner, cfg=None):
    r = _run(["source", "add", path, "-n", _nb(cfg), "--type", "file",
              "--mime-type", "audio/mp4", "--json"], runner=runner, cfg=cfg)
    out = _out(r).strip()
    try:
        d = json.loads(out)
        if isinstance(d, dict):
            for k in ("source_id", "id", "sourceId"):
                if d.get(k):
                    return d[k]
    except (ValueError, TypeError):
        pass
    m = _UUID.search(out)
    return m.group(0) if m else None


def source_wait(src_id, runner=_default_runner, cfg=None, timeout=900):
    r = _run(["source", "wait", src_id, "-n", _nb(cfg), "--timeout", str(timeout)],
             runner=runner, cfg=cfg)
    return getattr(r, "returncode", 1) == 0


def _is_ready(row):
    return row.get("status") == "ready" or row.get("status_id") == 2


def list_sources(runner=_default_runner, cfg=None):
    """All source rows (dicts) in the configured notebook, or [] on parse failure.
    Pass a cfg whose notebook_id is the notebook you want to scan."""
    out = _out(_run(["source", "list", "-n", _nb(cfg), "--json"], runner=runner, cfg=cfg)).strip()
    try:
        d = json.loads(out)
    except (ValueError, TypeError):
        return []
    rows = d.get("sources", d) if isinstance(d, dict) else d
    return [r for r in (rows or []) if isinstance(r, dict)]


def source_status(src_id, runner=_default_runner, cfg=None):
    """Return 'ready' for an indexed source, else its raw status (e.g. 'preparing'),
    or None if the id isn't found. The CLI's `source wait` is unreliable for audio,
    so we read the status directly from `source list`."""
    out = _out(_run(["source", "list", "-n", _nb(cfg), "--json"],
                    runner=runner, cfg=cfg)).strip()
    try:
        d = json.loads(out)
    except (ValueError, TypeError):
        return None
    rows = d.get("sources", d) if isinstance(d, dict) else d
    for r in (rows or []):
        if isinstance(r, dict) and (r.get("id") or r.get("source_id")) == src_id:
            return "ready" if _is_ready(r) else (r.get("status") or "unknown")
    return None


def wait_source_ready(src_id, runner=_default_runner, cfg=None,
                      timeout=900, poll_every=30, _sleep=None):
    """Poll `source list` until the source is ready. True iff ready within timeout.
    More reliable for audio than the CLI's `source wait` (which can return before
    transcription completes)."""
    import time as _t
    sleep = _sleep or _t.sleep
    waited = 0
    while True:
        if source_status(src_id, runner=runner, cfg=cfg) == "ready":
            return True
        if waited >= timeout:
            return False
        sleep(poll_every)
        waited += poll_every


def find_source_by_title(title, runner=_default_runner, cfg=None):
    out = _out(_run(["source", "list", "-n", _nb(cfg), "--json"], runner=runner, cfg=cfg)).strip()
    try:
        d = json.loads(out)
    except (ValueError, TypeError):
        return None
    rows = d.get("sources", d) if isinstance(d, dict) else d
    matches = [r for r in (rows or [])
               if isinstance(r, dict) and (r.get("title") or r.get("name")) == title]
    if not matches:
        return None
    ready = [r for r in matches if _is_ready(r)]
    pick = max(ready or matches, key=lambda r: r.get("created_at") or "")
    return pick.get("id") or pick.get("source_id")


def ask(question, src_id=None, runner=_default_runner, cfg=None):
    args = ["ask", question, "-n", _nb(cfg), "--json"]
    if src_id:
        args += ["-s", src_id]
    out = _out(_run(args, runner=runner, cfg=cfg)).strip()
    text = out
    try:
        d = json.loads(out)
        if isinstance(d, dict):
            text = d["answer"] if "answer" in d else (d.get("response") or d.get("text") or out)
    except (ValueError, TypeError):
        pass
    return _CIT.sub("", text or "").strip()
