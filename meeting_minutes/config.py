"""Load user config from config.yaml (falls back to config.example.yaml)."""
import os
from pathlib import Path
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_CFG = None


def _expand(v):
    return os.path.expanduser(v) if isinstance(v, str) and v.startswith("~") else v


def load(path=None):
    """Return the parsed config dict (cached). Prefers config.yaml."""
    global _CFG
    if _CFG is not None and path is None:
        return _CFG
    p = Path(path) if path else (_ROOT / "config.yaml")
    if not p.exists():
        p = _ROOT / "config.example.yaml"
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cfg.setdefault("paths", {})
    cfg["paths"]["audio_dir"] = _expand(cfg["paths"].get("audio_dir", "~/MeetingAudio"))
    cfg["paths"]["output_dir"] = _expand(cfg["paths"].get("output_dir", "~/MeetingMinutes"))
    nb = cfg.setdefault("notebooklm", {})
    nb["binary"] = _expand(nb.get("binary", ""))
    nb.setdefault("scan_notebook_ids", [])      # direct-upload scan (off by default)
    if path is None:
        _CFG = cfg
    return cfg


def audio_dir(cfg=None):
    return (cfg or load())["paths"]["audio_dir"]


def output_dir(cfg=None):
    return (cfg or load())["paths"]["output_dir"]
