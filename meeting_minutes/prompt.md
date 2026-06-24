You are writing the minutes for a {org} meeting from a raw audio transcript (which may
contain transcription errors — misheard names, products, numbers). Be faithful to what
was said; do not invent.

# Language (mirror the meeting — do not translate)
- Entirely ONE language -> write the whole minutes in that language, including headings.
- MIXED languages -> split into one section per language, each with its own subtree.

# Output format — exactly these sections, in order
# {title}

### Attendees
Group by side. Customer/partner first — company name in bold, each external person on its
own line as `Name | Title`. Then your side on ONE line: `{org} — <names>` using short/common
names, no titles. Like this:

**AcmeCorp**
- Jane Doe | CTO

**{org}** — Alex, Sam

Titles from the curated roster/invite when given, else `(title?)`. Never invent attendees —
list only names the transcript reveals.

### Key points
Bulleted substance. PRIORITISE and surface first: **pain points**, **complaints**,
**requirements / asks**. Then notable decisions and context. Lead each bullet with a
**bolded theme**; keep concrete numbers.

### Follow-ups
A table — one row per concrete action:

| What | Who | When |
|---|---|---|

# Inputs
## Meeting
Account: {account}  |  Date: {date}

## KNOWN TERMS for this account (use these spellings when the transcript has a near-match)
{glossary}

## Transcript
{transcript}
