"""Transcription backends for the `cloud` and `local` engines.

- local: faster-whisper on your machine (private; slow on CPU). Returns text.
- cloud: Google Gemini (fast; needs GEMINI_API_KEY). See cloud_stt.py.

NotebookLM (the default backend) does not use this module — it transcribes server-side.
"""
import os
from functools import lru_cache

from meeting_minutes import config


@lru_cache(maxsize=1)
def _model(size, device="auto", compute_type="int8"):
    from faster_whisper import WhisperModel
    return WhisperModel(size, device=device, compute_type=compute_type)


def transcribe_local(path, model=None, language=None, cfg=None):
    cfg = cfg or config.load()
    size = (cfg.get("local") or {}).get("whisper_model", "large-v3")
    mdl = model or _model(size)
    segments, info = mdl.transcribe(path, language=language, beam_size=5, vad_filter=True)
    parts = [s.text.strip() for s in segments if (s.text or "").strip()]
    return {"text": " ".join(parts).strip(), "language": getattr(info, "language", None)}


def transcribe(path, backend, cfg=None, language=None):
    """Return {'text', 'language'} for the cloud/local backends."""
    if backend == "cloud":
        from meeting_minutes.cloud_stt import transcribe_cloud
        return transcribe_cloud(path, cfg=cfg, language=language)
    return transcribe_local(path, cfg=cfg, language=language)
