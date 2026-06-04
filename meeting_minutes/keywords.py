"""Distil a keyword glossary from past minutes (point 2 — cross-check).

A short, high-signal list of known names/products/acronyms from prior minutes lets
the summariser correct transcription mishearings against real terms.
"""
import re

_EN = re.compile(r"[A-Za-z][A-Za-z0-9.+&/-]{2,}")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ATTENDEE = re.compile(r"^\s*[-*]\s*([^—|<\n,(]+?)\s*(?:—|,)", re.M)

_STOP = {
    "the", "and", "for", "this", "that", "with", "from", "they", "you", "our",
    "are", "will", "not", "but", "has", "have", "was", "were", "name", "title",
    "what", "who", "when", "stated", "company", "email", "none", "tbd", "key",
    "points", "follow", "ups", "attendees", "minutes", "meeting", "date",
}


def extract_keywords(text, limit=40, max_len=24):
    if not text:
        return []
    scores = {}

    def add(term, weight):
        t = term.strip(" *·:，。、—-")
        if not t or "*" in t or len(t) > max_len or t.lower() in _STOP:
            return
        if t.isascii() and len(t) < 2:
            return
        scores[t] = scores.get(t, 0) + weight

    for m in _ATTENDEE.finditer(text):
        add(m.group(1), 4)
    for m in _BOLD.finditer(text):
        if len(m.group(1)) <= 14:
            add(m.group(1), 2)
    for m in _EN.finditer(text):
        add(m.group(0), 1)

    return [t for t, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]
