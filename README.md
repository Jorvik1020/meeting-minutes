# meeting-minutes

Turn meeting **audio recordings** into clean, structured **minutes** — with attendees,
key points (pain points / complaints / requirements first), and a follow-up table.

Three interchangeable engines:

| Backend | What it does | Needs | Speed | Privacy |
|---|---|---|---|---|
| **`notebooklm`** (default) | uploads audio → NotebookLM transcribes + summarises | a Google login + [notebooklm-py](https://pypi.org/project/notebooklm-py/) | ~1–10 min | audio → Google |
| `cloud` | Gemini transcribes → you summarise | `GEMINI_API_KEY` | ~6 min | audio → Google |
| `local` | faster-whisper on your machine → you summarise | `faster-whisper` | slow (CPU) | 🔒 stays local |

## Quick start

```bash
git clone <this-repo> && cd meeting-minutes
uv sync                 # or: pip install -e .
cp config.example.yaml config.yaml   # then edit config.yaml (see below)
python -m meeting_minutes.run --dry-run        # preview
python -m meeting_minutes.run                   # write minutes for all new audio
python -m meeting_minutes.run --file "~/MeetingAudio/AcmeCorp 2026.01.15.m4a"
```

## Configure (`config.yaml`)

Everything is in `config.yaml` (git-ignored, so your settings stay private):

1. **You** — your `name`, `email` (to recognise you among attendees), and `org`.
2. **Audio folder** — `paths.audio_dir`: where your recordings land (download from
   Google Drive, AirDrop, etc.). The tool only processes **recent + not-yet-done** files.
3. **NotebookLM** — `notebooklm.binary` (path to the notebooklm-py CLI) and
   `notebooklm.notebook_id` (the notebook to upload into). Or pick `backend: cloud|local`.
4. **Output + accounts** — `paths.output_dir` and your `accounts` list. A filename
   keyword maps each recording to an account, and minutes are written to
   **`<output_dir>/<account>/<account> <date>.md`** — the account sub-folder is
   **created automatically**. Unmatched recordings go to `_Uncategorized/`.

## Cross-check (uses your own history)

When `crosscheck.enabled: true`, the tool reads your **recent prior minutes for the same
account** and distils a glossary of known names/products/terms. The summariser uses it to
**fix transcription mishearings** (e.g. a garbled name → the real one it has seen before).
The more you use it, the better it gets per account.

## Minutes format

Fixed, sales-meeting-oriented format (edit `meeting_minutes/notebooklm_prompt.md` to taste):

- **Title** = `Account YYYY.MM.DD`
- **Attendees** — name — title, company
- **Key points** — pain points / complaints / requirements surfaced first, then context
- **Follow-ups** — `What | Who | When` table
- Language **mirrors the meeting** (no translation; mixed-language → split sections)

See **[`examples/AcmeCorp 2026.01.15.md`](examples/AcmeCorp%202026.01.15.md)** for a sample.

## Schedule it (optional, macOS)

Run it on a timer with `launchd` / `cron`, e.g. weekdays at 16:00, so new recordings turn
into minutes automatically.

---

Filenames should contain the **date** (`2026.01.15`, `2026_01_15`, or `2026 01 15`) and an
**account keyword** — e.g. `AcmeCorp 2026.01.15.m4a`.
