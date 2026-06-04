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
        nb.source_wait(source_id, runner=runner, cfg=cfg)
    prompt = build_prompt(ctx, title)
    waited = 0
    while True:
        minutes = nb.ask(prompt, src_id=source_id, runner=runner, cfg=cfg)
        if minutes and len(minutes) > 40:
            return minutes
        if waited >= poll_timeout:
            raise RuntimeError("NotebookLM: minutes still empty after indexing wait")
        _sleep(poll_every)
        waited += poll_every
