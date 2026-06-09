"""Generate minutes via NotebookLM: upload audio -> index -> ask for grounded minutes.

Keep the prompt SHORT (glossary, not the full prior-minutes text) — NotebookLM's ask
returns empty on over-long prompts. Poll the ask while the audio is still indexing.
Do NOT call `clear` before ask — it resets the notebook context and breaks grounding.
"""
import os
import time
from pathlib import Path

from meeting_minutes import notebooklm as nb

PROMPT_PATH = Path(__file__).parent / "notebooklm_prompt.md"

# NotebookLM returns a polite apology (not an empty string) while the audio is still
# indexing or if grounding fails — treat these as "not ready", NOT as real minutes.
# Without this, the apology gets written to the minutes file as if it were the summary.
_NOT_READY_MARKERS = (
    "couldn't find enough context", "could not find enough context",
    "not enough context", "i'm sorry", "im sorry", "i am sorry",
    "try giving me more specific keywords",
    "not included in the provided sources", "is not included",
    "i cannot generate the meeting minutes", "cannot generate the meeting minutes",
    "if you can upload or provide", "no sources", "provide the contents",
)


def _is_real_minutes(text):
    if not text or len(text) <= 40:
        return False
    low = text.lower()
    return not any(m in low for m in _NOT_READY_MARKERS)


def build_prompt(ctx, source_title):
    return PROMPT_PATH.read_text(encoding="utf-8").format(
        source_title=source_title,
        title=ctx["title"],
        account=ctx["account"],
        date=ctx.get("date") or "(date unknown)",
        org=ctx.get("org", "our company"),
        glossary=ctx.get("glossary") or "(none)",
    )


def generate_minutes(audio_path, ctx, runner=None, cfg=None, source_id=None,
                     poll_timeout=900, poll_every=60, _sleep=time.sleep):
    runner = runner or nb._default_runner
    title = os.path.basename(audio_path)
    if source_id is None:
        source_id = nb.find_source_by_title(title, runner=runner, cfg=cfg)
    if source_id is None:
        source_id = nb.source_add(audio_path, runner=runner, cfg=cfg)
        if not source_id:
            raise RuntimeError("NotebookLM: source add returned no id")

    # Gate on the source actually being indexed BEFORE asking — applies to BOTH a
    # fresh upload AND a reused source (a reused source may still be 'preparing').
    # Asking a not-ready source returns a plausible-but-ungrounded apology that can
    # slip past the text filter, so we wait on the real status first.
    if not nb.wait_source_ready(source_id, runner=runner, cfg=cfg, timeout=poll_timeout):
        raise RuntimeError("NotebookLM: source not indexed (still preparing) after "
                           f"{poll_timeout}s — not ready to ground minutes")

    prompt = build_prompt(ctx, title)
    waited = 0
    while True:
        minutes = nb.ask(prompt, src_id=source_id, runner=runner, cfg=cfg)
        if _is_real_minutes(minutes):        # real minutes, not empty/indexing/apology
            return minutes
        if waited >= poll_timeout:
            raise RuntimeError("NotebookLM: minutes still empty/ungrounded after "
                               "indexing wait (source likely not indexed yet)")
        _sleep(poll_every)
        waited += poll_every
