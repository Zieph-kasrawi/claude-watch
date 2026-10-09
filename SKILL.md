---
name: watch
description: Watch a video (URL or local path) and extract everything in it worth keeping — full timestamped transcript, key moments, the ideas and claims it makes, entities, quotable lines, and scene frames Claude actually looks at. Use whenever the founder shares a video and wants to learn from it, research it, summarize it, check what it claims, or turn it into notes — and for reviewing a video's own craft, where it also profiles pacing and the first ten seconds. Produces a structured report.md and offers to file it in the research library as research, tied to why it was watched.
argument-hint: "<video-url-or-path> [why you're watching it]"
allowed-tools: Bash, Read, Edit, Write, AskUserQuestion
homepage: https://github.com/taoufik123-collab/claude-watch
repository: https://github.com/taoufik123-collab/claude-watch
author: taoufik
license: MIT
user-invocable: true
---

# /watch — Claude watches a video

You don't have a video input; this skill gives you one. A Python script downloads the video, extracts frames as JPEGs (one per detected shot via scene-change), gets a timestamped transcript (native captions first, then Whisper API as fallback), runs editorial pacing metrics, and microscopes the first 10 seconds at higher density. You then `Read` each frame path to see the images, combine them with the transcript to answer the user, fill the structured `report.md`, and offer to file the analysis in the research library.

## What each watch produces beyond frames and a transcript

- **Scene-change frame sampling** — one frame per detected shot instead of uniform ticks. Cuts the frame budget on long videos while capturing every transition.
- **Editorial pacing metrics** — cuts/min, mean shot length, motion (when available). Lets you reason about pacing the way an editor does.
- **Hook microscope** — first 10s auto-runs at 2 fps + word-level Whisper. The single most leveraged 10 seconds of any video deserves dense treatment.
- **Structured `report.md`** — every watch emits an ingest-shaped report at `<workdir>/report.md` with TL;DR, key moments, hook breakdown, editorial profile, quotable moments, entities, concepts, and transcript. Narrative sections are emitted as `<!-- pending Claude fill: ... -->` markers — you fill them in before offering to save.
- **Step 4.4 — Save gate** — after answering the user, you ask once: "Save this to the research library?" Only on yes do you file it, as a research note — never as adopted practice — following the library wiki's own `SCHEMA.md`.

None of the above add new dependencies — pure ffmpeg + stdlib + the existing Whisper backend.

## Configuration — where reports are saved

Watched videos are filed in a **research library**: material that is a rough guide and a consultant, not established or adopted practice. It is kept apart from any memory of established facts, so /watch never writes to a notes vault, a memory store or a `CLAUDE.md`.

The library's location is one setting, `WATCH_RESEARCH_LIBRARY_DIRECTORY`, read from the environment and then from `~/.config/watch/.env`. Whoever owns the library repoints that one value; nothing else in this skill names a path. The directory holds two layers:

- `wiki/` — the compiled wiki. Its `wiki/SCHEMA.md` governs every page, link and log entry. Read it before writing anything there.
- `raw/transcripts/` — immutable raw transcripts, one file per video.

Resolve it with:

```bash
RESEARCH_LIBRARY_DIRECTORY="$(python3 "${CLAUDE_SKILL_DIR}/scripts/research_library.py")"
```

On exit 1 (the setting is unset, or the directory has no `wiki/SCHEMA.md`) skip Step 4.4, save nothing, and print one line in chat: `📄 Report (no research library configured): <workdir>/report.md`. Never fall back to another location.

## Step 0 — Setup preflight (runs every `/watch` invocation, silent on success)

**Python interpreter:** every `python3 ...` command in this skill is for macOS/Linux. On **Windows**, substitute `python` — the `python3` command on Windows is the Microsoft Store stub and will not run the script.

Before every `/watch` run, verify that dependencies and an API key are in place:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py" --check
```

This is a <100ms lookup. On exit 0, the script emits **nothing** — proceed to Step 1 without comment. **Do NOT announce "setup is complete" to the user** — they don't need a status message on every turn. The only acceptable user-visible output from Step 0 is when remediation is required.

On non-zero exit, follow the table:

| Exit | Meaning                                            | Action                                                    |
| ---- | -------------------------------------------------- | --------------------------------------------------------- |
| `2`  | Missing binaries (`ffmpeg` / `ffprobe` / `yt-dlp`) | Run installer                                             |
| `3`  | No Whisper API key                                 | Run installer, then hand the user the key step below      |
| `4`  | Both missing                                       | Run installer, then hand the user the key step below      |

The installer is idempotent — safe to re-run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py"
```

On macOS with Homebrew, it auto-installs `ffmpeg` and `yt-dlp`. On Linux/Windows, it prints the exact install commands for the user to run. It scaffolds `~/.config/watch/.env` with commented placeholders at `0600` perms, and writes `SETUP_COMPLETE=true` once deps + a key are in place so the next session knows this user has already been through the wizard.

**If an API key is still missing after install:** the key must never pass through the chat — never ask for it with `AskUserQuestion`, never accept it pasted into a message, and never write it to a file yourself. On macOS, hand the user this one manual step and wait for them to say it is done. The scripts read the key back from the Keychain at run time (`scripts/keychain.py`), so nothing else needs configuring:

> [!WARNING]
> ⚠️ **Step 1 — Save your Groq key in the macOS Keychain**
>
> **What & why:** /watch needs a Groq key to transcribe videos that have no captions; this stores it in your Mac's Keychain, the password store macOS keeps locked for you, so it never appears in the chat or a file.
>
> **Where:** open the Terminal app, paste the command below and press return, then paste your key (from console.groq.com/keys) when asked and press return again. Nothing shows on screen while you paste the key — that is on purpose.
>
> **You'll know it worked when** you see `✅ Saved: your Groq key is in the macOS Keychain as groq-api-key`; if you see `❌ Not saved: …` instead, nothing was stored — copy the key again and rerun the command.
>
> **Do this** (the command right below this box):

```zsh
read -rs "PASTED_GROQ_API_KEY?Paste your Groq API key, then press return (nothing shows as you paste): "; echo; if [[ "$PASTED_GROQ_API_KEY" =~ '^[A-Za-z0-9_-]+$' ]] && print -r -- "add-generic-password -U -a \"$USER\" -s groq-api-key -w \"$PASTED_GROQ_API_KEY\"" | security -i && [[ -n "$(security find-generic-password -a "$USER" -s groq-api-key -w 2>/dev/null)" ]]; then echo "✅ Saved: your Groq key is in the macOS Keychain as groq-api-key"; else echo "❌ Not saved: nothing usable was stored in the Keychain; copy the key again and rerun this"; fi; unset PASTED_GROQ_API_KEY
```

If the user only has an OpenAI key, hand them the same step with OpenAI in place of Groq (key from platform.openai.com/api-keys; success line names `openai-api-key`), using this command:

```zsh
read -rs "PASTED_OPENAI_API_KEY?Paste your OpenAI API key, then press return (nothing shows as you paste): "; echo; if [[ "$PASTED_OPENAI_API_KEY" =~ '^[A-Za-z0-9_-]+$' ]] && print -r -- "add-generic-password -U -a \"$USER\" -s openai-api-key -w \"$PASTED_OPENAI_API_KEY\"" | security -i && [[ -n "$(security find-generic-password -a "$USER" -s openai-api-key -w 2>/dev/null)" ]]; then echo "✅ Saved: your OpenAI key is in the macOS Keychain as openai-api-key"; else echo "❌ Not saved: nothing usable was stored in the Keychain; copy the key again and rerun this"; fi; unset PASTED_OPENAI_API_KEY
```

After they confirm, re-run `python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py" --check`; exit 0 means the key was found. On Linux or Windows there is no Keychain: tell the user to put the key on the `GROQ_API_KEY=` (or `OPENAI_API_KEY=`) line of `~/.config/watch/.env` themselves, in their own editor. If they don't want to set up Whisper, proceed with `--no-whisper` and tell them videos without native captions will come back frames-only.

**Structured mode (optional):** `python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py" --json` emits `{status, first_run, missing_binaries, whisper_backend, has_api_key, config_file, platform}` where `status` is one of `ready | needs_install | needs_key | needs_install_and_key`. Use this when you need to branch on specifics (e.g. "is this the user's very first run?" → `first_run: true`).

Within a single session, you can skip Step 0 on follow-up `/watch` calls — once `--check` returned 0, nothing about the environment changes between turns.

## When to use

- User pastes a video URL (YouTube, Vimeo, X, TikTok, Twitch clip, most yt-dlp-supported sites) and asks about it.
- User points at a local video file (`.mp4`, `.mov`, `.mkv`, `.webm`, etc.) and asks about it.
- User types `/watch <url-or-path> [question]`.

## Recommended limits

- **Best accuracy: videos under 10 minutes.** Frame coverage scales inversely with duration.
- **Hard caps: 100 frames total and 2 fps.** Token cost grows with frame count, so the script targets a frame budget by duration (and never exceeds 2 fps even when the budget would imply more):
  - ≤30s → ~1-2 fps (up to 30 frames)
  - 30s-1min → ~40 frames
  - 1-3min → ~60 frames
  - 3-10min → ~80 frames
  - \>10min → 100 frames, sparsely spaced (warning printed)
- If the user hands you a long video, consider asking whether they want a specific section before burning tokens on a sparse scan.

## How to invoke

**Step 1 — parse the user input.** Separate the video source from any question the user asked. The question (or the user's prior stated interest) IS the intent — pass it to the script via `--intent`. Example: `/watch https://youtu.be/abc what's the hook pattern?` → source = `https://youtu.be/abc`, intent = `what's the hook pattern?`. If no question is given, use a brief inferred intent ("general summary") so the report's TL;DR has a lens. The intent shapes how the report's TL;DR and entity/concept sections get filled at Step 4 — same video with intent "pricing tactics" vs "editing style" produces different reports.

**Step 2 — run the watch script.** Pass the source verbatim. Do not shell-escape it yourself beyond normal quoting:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" "<source>" --intent "<intent string>"
```

Pass `--intent` whenever you have any signal from the user about why they want this video — the question they asked, a stated goal, or a brief inferred summary. Empty `--intent` works but produces less-targeted report sections.

Optional flags:

- `--start T` / `--end T` — focus on a section. Accepts `SS`, `MM:SS`, or `HH:MM:SS`. When either is set, fps auto-scales denser (see "Focusing on a section" below).
- `--max-frames N` — lower the cap for tighter token budget (e.g. `--max-frames 40`)
- `--resolution W` — change frame width in px (default 512; bump to 1024 only if the user needs to read on-screen text)
- `--fps F` — override auto-fps (clamped to 2 fps max). Setting `--fps` disables scene-change sampling.
- `--out-dir DIR` — keep working files somewhere specific (default: an auto-generated tmp dir)
- `--whisper groq|openai` — force a specific Whisper backend (default: prefer Groq if both keys exist)
- `--no-whisper` — disable the Whisper fallback entirely (frames-only if no captions)
- `--no-scene-change` — force uniform frame sampling (debug only; usually leave on)
- `--no-hook-microscope` — skip the 0-10s dense pass (saves ~1 Whisper call)

### Focusing on a section (higher frame rate)

When the user asks about a specific moment — "what happens at the 2 minute mark?", "zoom into 0:45 to 1:00", "the first 10 seconds" — pass `--start` and/or `--end`. The script switches to focused-mode budgets, which are denser than full-video budgets (still capped at 2 fps):

- ≤5s → 2 fps (up to 10 frames)
- 5-15s → 2 fps (up to 30 frames)
- 15-30s → ~2 fps (up to 60 frames)
- 30-60s → ~1.3 fps (up to 80 frames)
- 60-180s → ~0.6 fps (100 frames, capped)

Focused mode is the right call for:

- Any moment/range the user names explicitly ("around 2:30", "the intro", "the last 30 seconds").
- Any video longer than ~10 minutes where the user's question is about a specific part — running focused on the relevant section is far more useful than a sparse scan of the whole thing.
- Re-runs after a full scan didn't have enough detail in some region.

Transcript is auto-filtered to the same range. Frame timestamps are absolute (real video timeline, not offset-from-start).

Examples:

```bash
# Last 10 seconds of a 1 minute video
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" video.mp4 --start 50 --end 60

# Zoom into 2:15 → 2:45 at 3 fps (90 frames)
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" "$URL" --start 2:15 --end 2:45 --fps 3

# From 1h12m to the end of the video
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" "$URL" --start 1:12:00
```

**Step 3 — Read every frame path the script lists.** The Read tool renders JPEGs directly as images for you. Read all frames in a single message (parallel tool calls) so you see them together. The frames are in chronological order with a `t=MM:SS` timestamp so you can align them to the transcript.

**Step 4 — answer the user, then fill the report.** You now have three streams of evidence:

- **Frames** — what's on screen at each timestamp
- **Transcript** — what's said at each timestamp
- **`report.md`** — structured artifact at `<workdir>/report.md` with `<!-- pending Claude fill: ... -->` markers

First, answer the user's question in chat citing timestamps.

Then, **fill in the pending markers in `report.md` using the Edit tool**. Walk every `<!-- pending Claude fill: ... -->` in order:

- **TL;DR** — 3-5 bullets through the lens of the user's intent (read from the frontmatter)
- **Key moments** — 5-10 timestamped bullets
- **Hook microscope interpretation** — frame-by-frame: visual change × what's said; identify the hook pattern (question, contrarian claim, in-medias-res, demo-first, etc.)
- **Editorial profile fingerprint** — one-line style summary inferred from pacing numbers + hero frames
- **Quotable moments** — top 3-5 punchy, standalone lines from the transcript
- **Entities mentioned** — people, companies, tools, places — as kebab-case, lowercase slugs matching the library wiki's `tools/` and `techniques/` pages, linked bundle-relative (`/tools/<slug>.md`).
- **Concepts surfaced** — frameworks, mental models, named patterns — short gist each

The fully-filled `report.md` is what Step 4.4 files. Do not skip the fill — empty markers produce a sparse, wrong source page.

**Step 4.4 — Offer to save it to the research library, and write only on yes.** Resolve `RESEARCH_LIBRARY_DIRECTORY` per the Configuration section; if none is configured, print the no-library line and go to Step 5. Otherwise use `AskUserQuestion` once (skip it only if the user said "don't save" before /watch ran), before anything is written:

> **Question:** "Save this to the research library? It is filed as research — a rough guide, not adopted practice."
>
> - **Yes — same angle** ("<intent>")
> - **Yes — different angle** (user specifies in the notes field)
> - **No, don't save it**

**On "No":** write nothing and go to Step 5.

**On either "Yes":** `WIKI` below means `$RESEARCH_LIBRARY_DIRECTORY/wiki`.

1. **Read `$WIKI/SCHEMA.md` in full.** It is authoritative for frontmatter, body sections, links and the log format; where it and this step differ, it wins. Then read the newest page in `$WIKI/sources/` whose name starts with `ext-`, and the last few entries of `$WIKI/log.md`, and match them.
2. **If "different angle":** re-edit the TL;DR, Entities and Concepts sections of `report.md` to the new angle before filing.
3. **Number it.** A video the user brought, outside the numbered playlist, is filed with the `ext-` prefix: `NN` is the highest existing `ext-NN` in `$WIKI/sources/` plus one, two digits. `<slug>` is the video title, lowercase, ASCII-only, hyphenated, at most 60 characters. If a source page already records this `video_id`, stop and tell the user where it is instead of filing a duplicate.
4. **Write the raw transcript** to `$RESEARCH_LIBRARY_DIRECTORY/raw/transcripts/ext-NN-<video_id>.md`, in the same shape as the files already there: the title as a heading, then channel, duration, upload date, URL and word count as a bullet list, a `---` rule, then the transcript text verbatim from `report.md`. Never edit it afterwards. If the report has no transcript, write no raw file and say so on the source page.
5. **Write the source page** `$WIKI/sources/ext-NN-<slug>.md` as a `Video Source` per `SCHEMA.md`, compiled from the filled report — not a copy of it. Add to the frontmatter:
   - `tags` that include `external-source`, `ad-hoc` and `research-not-adopted`;
   - `watched_because:` the user's intent (or the different angle), in their words;
   - `standing: research — not established or adopted practice`.

   Directly under the frontmatter, before `# Thesis`, put this banner on its own line: `> **Research note filed by /watch.** Every claim here is the speaker's or this analysis's, not established or adopted practice; treat it as a rough guide.` Use the schema's body sections (`# Thesis`, `# Techniques & claims`, `# Adopt/reject signals`, `# Citations`); write adopt/reject signals as suggestions for the user to weigh, never as decisions. Describe what the frames showed in words; copy no images.
6. **Index and log it.** Add one line for the page under `# External / ad-hoc sources (not playlist)` in `$WIKI/sources/index.md`, matching the existing lines, and append one `ingest` entry for it to `$WIKI/log.md` in the format its newest entries use.
7. **Stop there.** This step files only the video's own pages. The pages shared across videos (`tools/`, `techniques/`, `analyses/`, the root `index.md`) are left to whoever owns the library, so do not create or edit them. Links from the source page to tool or technique pages that do not exist yet are allowed; they mark pages the library's owner may write later.
8. **Do not commit, and open nothing.** Never run `open` or any command that launches or focuses an app. Print in chat, one per line, every file written, as full paths, starting with `📄 Saved to the research library: <full path of the source page>`. If the library sits inside a git repository, say so; whoever commits follows that repository's own rules, using exactly those paths.

The "different angle" path lets the user watch a video for one reason and, on the way out, file it under the reason it turned out to be useful for.

**Step 5 — clean up.** The script prints a working directory at the end. Whether or not the report was saved, the working directory holds only working copies: if the user isn't going to ask follow-ups, delete it with `rm -rf <dir>`; if they might, leave it in place.

## Transcription

The script gets a timestamped transcript in one of two ways:

1. **Native captions (free, preferred).** yt-dlp pulls manual or auto-generated subtitles from the source platform if available.
2. **Whisper API fallback.** If no captions came back (or the source is a local file), the script extracts audio (`ffmpeg -vn -ac 1 -ar 16000 -b:a 64k`, ~0.5 MB/min) and uploads it to whichever Whisper API has a key configured:
   - **Groq** — `whisper-large-v3`. Preferred default: cheaper, faster. Get a key at console.groq.com/keys.
   - **OpenAI** — `whisper-1`. Fallback. Get a key at platform.openai.com/api-keys.

On macOS both keys live in the Keychain (services `groq-api-key` and `openai-api-key`, stored by the Step 0 command); elsewhere they live in `~/.config/watch/.env`. Each key is looked up in the environment first, then the Keychain, then the `.env` file. The script prefers Groq when both are set; override with `--whisper openai` to force OpenAI. Use `--no-whisper` to skip the fallback entirely.

## Failure modes and handling

- **Setup preflight failed** → run `python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py"` (auto-installs ffmpeg/yt-dlp via brew on macOS, scaffolds the `.env`). For the API key, hand the user the Keychain step in Step 0 — never collect the key in chat.
- **No transcript available** → captions missing AND (no Whisper key OR Whisper API failed). Script prints a hint pointing to setup. Proceed frames-only and tell the user.
- **Long video warning printed** → acknowledge it in your answer. Offer to re-run focused on a specific section via `--start`/`--end` rather than a sparse full-video scan.
- **Download fails** → yt-dlp's error goes to stderr. If it's a login-required or region-locked video, tell the user plainly; do not keep retrying.
- **Whisper request fails** → the error is printed to stderr (likely: invalid key, rate limit, or 25 MB upload limit on a very long video). The report will say "none available" for transcript. You can retry with `--whisper openai` if Groq failed (or vice versa).
- **Report has unfilled `<!-- pending Claude fill: ... -->` markers** → you skipped Step 4. Go back, read the report, fill every marker via Edit, then offer to save. Never file a half-filled report — it produces a sparse, wrong source page.
- **Saving fails partway** → do not roll back and do not delete anything. Tell the user which of the Step 4.4 files were written and which were not, with full paths, and leave the working directory in place so the save can be finished from it.

## Token efficiency

This skill burns tokens primarily on frames. Order of magnitude:

- 80 frames at 512px wide is roughly 50-80k image tokens depending on aspect ratio.
- The transcript is cheap (a few thousand tokens at most for a 10-minute video).
- Bumping `--resolution` to 1024 roughly quadruples the image tokens per frame. Only do it when necessary.

If you already watched a video this session and the user asks a follow-up, do **not** re-run the script — you already have the frames and transcript in context. Just answer from what you have.

## Security & Permissions

**What this skill does:**

- Runs `yt-dlp` locally to download the video and pull native captions when the source supports them (public data; the request goes directly to whatever host the URL points at)
- Runs `ffmpeg` / `ffprobe` locally to extract frames as JPEGs and, when Whisper is needed, a mono 16 kHz audio clip
- Sends the extracted audio clip to Groq's Whisper API (`api.groq.com/openai/v1/audio/transcriptions`) when `GROQ_API_KEY` is set (preferred — cheaper, faster)
- Sends the extracted audio clip to OpenAI's audio transcription API (`api.openai.com/v1/audio/transcriptions`) when `OPENAI_API_KEY` is set and Groq is not, or when `--whisper openai` is forced
- Writes the downloaded video, frames, audio, and an intermediate transcript to a working directory under the system temp dir (or `--out-dir` if specified) so Claude can `Read` them
- Reads the Whisper API key(s) from the macOS Keychain (services `groq-api-key` / `openai-api-key`) with `security find-generic-password`; the value is passed to the matching API and never printed
- Reads / creates `~/.config/watch/.env` (mode `0600`) for a `SETUP_COMPLETE` marker and, on platforms without a Keychain, the Whisper API key(s). As a fallback, also reads `.env` in the current working directory
- Reads the `WATCH_RESEARCH_LIBRARY_DIRECTORY` setting and, when saving is consented to, that library's `wiki/SCHEMA.md`
- Only after the user says yes at Step 4.4: writes one raw transcript under `raw/transcripts/`, one source page under `wiki/sources/`, one line in `wiki/sources/index.md` and one entry in `wiki/log.md` inside the research library

**What this skill does NOT do:**

- Does not upload the video itself to any API — only the extracted audio goes out, and only when native captions are missing AND Whisper is not disabled with `--no-whisper`
- Does not access any platform account (no login, no session cookies, no posting)
- Does not share API keys between providers (Groq key only goes to `api.groq.com`, OpenAI key only goes to `api.openai.com`)
- Does not log, cache, or write API keys to stdout, stderr, or output files
- Does not collect API keys through the chat — the user stores them in the Keychain with the Step 0 command
- Does not open, launch or focus any app — it prints where the report was saved
- Does not persist anything outside the working directory, `~/.config/watch/.env`, the Keychain items the user stored, and the research library files listed above — clean up the working directory when you're done (Step 5)
- Does not write to the research library without explicit user consent at the Step 4.4 prompt, and never writes to a notes vault, a memory store or any `CLAUDE.md`
- Does not copy frames or any other image into the research library
- Does not commit, and does not edit the library's `tools/`, `techniques/`, `analyses/` or root `index.md` pages

**Bundled scripts:** `scripts/watch.py` (entry point), `scripts/download.py` (yt-dlp wrapper), `scripts/frames.py` (ffmpeg uniform + scene-change extraction + hero selection), `scripts/pacing.py` (editorial metrics), `scripts/hook.py` (0-10s microscope), `scripts/report.py` (structured report emitter), `scripts/transcribe.py` (caption selection + Whisper orchestration), `scripts/whisper.py` (Groq / OpenAI clients, supports word-level timestamps), `scripts/setup.py` (preflight + installer), `scripts/keychain.py` (macOS Keychain key lookup), `scripts/research_library.py` (resolves the research library setting)

Review scripts before first use to verify behavior.
