"""Find new audio and load related prior minutes for cross-checking (point 2)."""
import os
import re
from pathlib import Path

from meeting_minutes import config
from meeting_minutes.classify import classify

AUDIO_EXTS = (".m4a", ".mp3", ".mp4", ".wav", ".aac")


# --- Curated per-account glossary + roster ----------------------------------
# Optional hand-maintained file at <output_dir>/_Glossary/<account>.md with two
# sections (`## Terms` and `## People`). Force-injected into the summariser so
# mis-hearings of product/term/people names snap to canonical spellings — fixing
# professional WORDING, not just attendee names. People are folded into the
# glossary as a correction reference, NOT asserted as attendees.
#
#   ## Terms
#   - Token Hub            <!-- NOT "TokenHub" -->
#   - EdgeOne L4
#   ## People
#   - Kevin Clark — Chief Information Officer, AcmeCo <kevin.clark@acme.com>

def _glossary_dir(cfg=None):
    return Path(config.output_dir(cfg)) / "_Glossary"


def _strip_comment(s):
    return re.sub(r"<!--.*?-->", "", s).strip()


def _glossary_section(account, header_prefix, cfg=None):
    """Yield the `- ` bullet lines under the `## <header_prefix...>` section."""
    if not account:
        return
    f = _glossary_dir(cfg) / f"{account}.md"
    if not f.exists():
        return
    in_section = False
    for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
        h = line.strip()
        if h.startswith("## "):
            in_section = h[3:].strip().lower().startswith(header_prefix)
            continue
        if in_section and h.startswith("- "):
            yield _strip_comment(h[2:])


def load_curated_attendees(account, cfg=None):
    """Parse the '## People' roster into attendee dicts (name/title/company/email).
    A name/title reference — NOT proof of attendance (the calendar sidecar decides
    who actually attended)."""
    people = []
    for entry in _glossary_section(account, "people", cfg):
        if not entry:
            continue
        email = None
        m = re.search(r"<([^>]+)>", entry)
        if m:
            email = m.group(1).strip()
            entry = entry[:m.start()].strip()
        name, _, rest = entry.partition("—")
        title, company = rest.strip(), ""
        if "," in rest:
            title, company = (x.strip() for x in rest.rsplit(",", 1))
        people.append({"name": name.strip(), "title": title,
                       "company": company, "email": email})
    return [p for p in people if p["name"]]


def load_glossary_terms(account, cfg=None):
    """Canonical terms (## Terms) PLUS 'Name (Title)' per known person, so the
    summariser corrects professional wording AND people's names/titles. [] if no
    curated file exists for the account."""
    terms = [t for t in _glossary_section(account, "term", cfg) if t]
    for p in load_curated_attendees(account, cfg):
        terms.append(f"{p['name']} ({p['title']})" if p.get("title") else p["name"])
    return terms


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
