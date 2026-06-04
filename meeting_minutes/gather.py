"""Find new audio and load related prior minutes for cross-checking (point 2)."""
import os
from pathlib import Path

from meeting_minutes import config
from meeting_minutes.classify import classify

AUDIO_EXTS = (".m4a", ".mp3", ".mp4", ".wav", ".aac")


def minutes_path(audio_path, cfg=None):
    cfg = cfg or config.load()
    info = classify(audio_path, cfg)
    title = Path(audio_path).stem            # title = filename (customer + type + date)
    return Path(config.output_dir(cfg)) / info["account"] / f"{title}.md"


def is_already_done(audio_path, cfg=None):
    return minutes_path(audio_path, cfg).exists()


def scan_new_audio(cfg=None, days=14, now=None):
    """Recent + not-yet-done audio files in the configured audio_dir."""
    import time
    cfg = cfg or config.load()
    d = Path(config.audio_dir(cfg))
    if not d.exists():
        return []
    cutoff = (now or time.time()) - days * 86400 if days else None
    out = []
    for p in sorted(d.glob("*")):
        if p.suffix.lower() not in AUDIO_EXTS:
            continue
        if cutoff is not None and p.stat().st_mtime < cutoff:
            continue
        if is_already_done(str(p), cfg):
            continue
        out.append(str(p))
    return out


def load_related_minutes(account, cfg=None):
    """Concatenate recent prior minutes for the same account — used ONLY to correct
    transcription typos in names/products (point 2). '' if disabled / none."""
    cfg = cfg or config.load()
    cc = cfg.get("crosscheck", {})
    if not cc.get("enabled", True) or not account or account == "_Uncategorized":
        return ""
    folder = Path(config.output_dir(cfg)) / account
    if not folder.is_dir():
        return ""
    files = sorted(folder.glob("*.md"), reverse=True)[: cc.get("max_prior", 3)]
    return "\n\n---\n\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in files)
