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
         "please log in", "not authenticated", "invalid_grant")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_CIT = re.compile(r"\s*\[\d+\]")


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
