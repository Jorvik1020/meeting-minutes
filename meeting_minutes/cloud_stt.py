"""Cloud transcription via Google Gemini (fast; handles long audio).

Needs GEMINI_API_KEY in the environment and the google-genai SDK. Long audio is split
into ~10-min chunks transcribed in parallel (a single call truncates long output), then
stitched. ⚠️ Uploads audio to Google — use only for non-sensitive meetings.
"""
import os
import re
import time
import mimetypes

from meeting_minutes import config

_PROMPT = ("Transcribe this meeting recording verbatim. Preserve the original "
           "language(s) — do not translate. Output ONLY the transcript text.")
_AUDIO_MIME = {".m4a": "audio/mp4", ".mp4": "audio/mp4", ".mp3": "audio/mpeg",
               ".wav": "audio/wav", ".aac": "audio/aac", ".ogg": "audio/ogg"}
_REPEAT = re.compile(r"(.{1,6}?)\1{7,}")


def _mime(path):
    ext = os.path.splitext(path)[1].lower()
    return _AUDIO_MIME.get(ext) or mimetypes.guess_type(path)[0] or "audio/mp4"


def _client():
    from google import genai
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set (get one at aistudio.google.com/apikey)")
    return genai.Client(api_key=key)


def _model(cfg):
    return (cfg.get("cloud") or {}).get("model", "gemini-2.5-flash")


def _collapse_repeats(text):
    return _REPEAT.sub(lambda m: m.group(1) * 3 + " […]", text or "")


def _split(path, chunk_seconds=600, workdir="/tmp"):
    import av
    inp = av.open(path)
    stem = os.path.splitext(os.path.basename(path))[0].replace(" ", "_")

    def _open(i):
        o = av.open(os.path.join(workdir, f"{stem}.chunk{i:02d}.m4a"), "w")
        s = o.add_stream("aac", rate=16000); s.layout = "mono"
        return o, s, av.AudioResampler(format="fltp", layout="mono", rate=16000)

    paths, idx, boundary = [], 0, chunk_seconds
    cur = os.path.join(workdir, f"{stem}.chunk00.m4a"); paths.append(cur)
    out, ost, res = _open(0)
    for fr in inp.decode(audio=0):
        if (fr.time or 0) >= boundary:
            for p in ost.encode(None):
                out.mux(p)
            out.close(); idx += 1; boundary += chunk_seconds
            cur = os.path.join(workdir, f"{stem}.chunk{idx:02d}.m4a"); paths.append(cur)
            out, ost, res = _open(idx)
        for rf in res.resample(fr):
            for p in ost.encode(rf):
                out.mux(p)
    for p in ost.encode(None):
        out.mux(p)
    out.close(); inp.close()
    return paths


def _duration(path):
    try:
        import av
        with av.open(path) as c:
            return c.duration / 1_000_000 if c.duration else None
    except Exception:
        return None


def _one(client, path, model, language):
    from google.genai import types
    f = client.files.upload(file=path, config=types.UploadFileConfig(mime_type=_mime(path)))
    while getattr(getattr(f, "state", None), "name", None) == "PROCESSING":
        time.sleep(2)
        f = client.files.get(name=f.name)
    prompt = _PROMPT + (f" Primary language: {language}." if language else "")
    cfg = types.GenerateContentConfig(temperature=0, max_output_tokens=65536)
    r = client.models.generate_content(model=model, contents=[f, prompt], config=cfg)
    return (getattr(r, "text", "") or "").strip()


def transcribe_cloud(path, cfg=None, language=None, client=None):
    cfg = cfg or config.load()
    client = client or _client()
    model = _model(cfg)
    dur = _duration(path)
    if dur and dur > 720:
        from concurrent.futures import ThreadPoolExecutor
        parts = _split(path)
        try:
            with ThreadPoolExecutor(max_workers=4) as ex:
                texts = list(ex.map(lambda p: _one(client, p, model, language), parts))
        finally:
            for p in parts:
                try:
                    os.remove(p)
                except OSError:
                    pass
        text = "\n".join(t for t in texts if t)
    else:
        text = _one(client, path, model, language)
    return {"text": _collapse_repeats(text).strip(), "language": language}
