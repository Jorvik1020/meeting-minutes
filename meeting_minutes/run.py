"""Meeting-minutes pipeline: find new audio -> transcribe + summarise -> write minutes.

  python -m meeting_minutes.run                 # process all new audio
  python -m meeting_minutes.run --file <audio>  # one file
  python -m meeting_minutes.run --dry-run       # print, don't write

Backend comes from config.yaml (notebooklm | cloud | local).
Minutes are written to  <output_dir>/<account>/<account> <date>.md  (account
sub-folder auto-created).  An LLM summariser is used for cloud/local; set
SUMMARISER_CMD or edit summarise() to plug in your LLM. NotebookLM summarises itself.
"""
import os
import sys
import argparse
from pathlib import Path

from meeting_minutes import config, gather, keywords as kw
from meeting_minutes import notebooklm_minutes as nbm
from meeting_minutes.classify import classify


def _title(info):
    # Title = your audio filename (name files "Customer MeetingType YYYY.MM.DD").
    # Falls back to account+date only if no filename title was attached.
    return info.get("title") or (f"{info['account']} {info['date']}" if info["date"] else info["slug"])


def _build_summary_prompt(transcript, ctx):
    fmt = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
    return fmt.format(
        title=ctx["title"], account=ctx["account"], date=ctx.get("date") or "(date unknown)",
        org=ctx.get("org", "our company"), glossary=ctx.get("glossary") or "(none)",
        transcript=transcript,
    )


def _summarise_with_llm(transcript, ctx, cfg):
    """Summarise the transcript into minutes using the friend-configured LLM.
    Provider-agnostic via LiteLLM (model + API key from config/env)."""
    import litellm
    model = (cfg.get("llm") or {}).get("model", "gpt-4o")
    prompt = _build_summary_prompt(transcript, ctx)
    r = litellm.completion(model=model, messages=[{"role": "user", "content": prompt}],
                           temperature=0)
    return r["choices"][0]["message"]["content"]


def process_audio(path, cfg=None, dry_run=False):
    cfg = cfg or config.load()
    info = classify(path, cfg)
    info["title"] = Path(path).stem          # title = your filename (customer + type + date)
    title = _title(info)
    related = gather.load_related_minutes(info["account"], cfg)
    # Curated glossary (canonical terms + known people) FIRST, then auto-extracted
    # keywords — so hand-maintained spellings win over noisy auto-extraction.
    glossary = ", ".join(gather.load_glossary_terms(info["account"], cfg)
                         + kw.extract_keywords(related))
    backend = cfg.get("backend", "notebooklm")
    ctx = {"title": title, "account": info["account"], "date": info["date"],
           "org": cfg.get("you", {}).get("org", "our company"), "glossary": glossary}

    if backend == "notebooklm":
        minutes = nbm.generate_minutes(path, ctx, cfg=cfg)
    else:  # local (Whisper-turbo) or cloud (Gemini) transcribe -> your LLM summarises
        from meeting_minutes.transcribe import transcribe
        result = transcribe(path, backend, cfg=cfg)
        minutes = _summarise_with_llm(result["text"], ctx, cfg)

    if dry_run:
        print(f"\n===== {title} =====\n{minutes}\n")
        return None
    folder = Path(config.output_dir(cfg)) / info["account"]   # auto-create account subfolder
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{title}.md"
    out.write_text(minutes, encoding="utf-8")
    print(f"Wrote {out}")
    return str(out)


def run_job(file=None, dry_run=False, cfg=None):
    cfg = cfg or config.load()
    audios = [os.path.expanduser(file)] if file else gather.scan_new_audio(cfg)
    if not audios:
        print("No new audio.")
        return 0
    for a in audios:
        process_audio(a, cfg=cfg, dry_run=dry_run)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Transcribe + summarise meeting audio")
    ap.add_argument("--file", default=None, help="process a single audio file")
    ap.add_argument("--dry-run", action="store_true", help="print, don't write")
    args = ap.parse_args()
    sys.exit(run_job(file=args.file, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
