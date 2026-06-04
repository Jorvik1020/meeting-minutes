"""Map an audio filename to {date, slug, account} using the accounts in config.

The account becomes the output sub-folder (auto-created). Unmatched -> _Uncategorized.
"""
import os
import re
import unicodedata

from meeting_minutes import config

_DATE = re.compile(r"(20\d\d)[.\-_ ](\d{2})[.\-_ ](\d{2})")  # 2026.05.13 / 2026_05_13 / 2026 05.13


def parse_date(name):
    m = _DATE.search(name)
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else None


def slugify(stem):
    s = _DATE.sub("", stem)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "meeting"


def classify(filename, cfg=None):
    cfg = cfg or config.load()
    stem = os.path.splitext(os.path.basename(filename))[0]
    low = stem.lower()
    account = "_Uncategorized"
    for acc in cfg.get("accounts", []):
        if any(str(k).lower() in low for k in acc.get("keywords", [])):
            account = acc["name"]
            break
    return {"date": parse_date(stem), "slug": slugify(stem), "account": account}
