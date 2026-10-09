# Changelog

All notable changes to `/watch` are documented here.

## [Unreleased]

### Security
- On macOS, Whisper API keys are read from the Keychain (services `groq-api-key` and `openai-api-key`) by the new `scripts/keychain.py`, checked after the environment and before `~/.config/watch/.env`, in `whisper.py`, `setup.py` and the SessionStart hook.
- `SKILL.md` no longer collects API keys through `AskUserQuestion` or writes them to `.env`: it hands the user a silent `read -rs` paste command that stores the key in the Keychain and proves it landed.

### Changed
- Reports are saved to a research library instead of an Obsidian vault. The location is one setting, `WATCH_RESEARCH_LIBRARY_DIRECTORY`, resolved by the new `scripts/research_library.py`; `WATCH_VAULT_DIR` and the `~/Second brain/`, `~/Documents/Obsidian/`, `~/Obsidian/` auto-detection are removed, and an unset or invalid setting saves nothing.
- Step 4.4 now asks before writing anything (the old flow pre-staged into the vault, then deleted it on "no"). On yes it follows the library's `wiki/SCHEMA.md`: a raw transcript, an `ext-NN` source page marked as research and not adopted practice, an index line and a log entry. It copies no frames, edits no cross-cutting wiki pages and does not commit. The old Step 4.5 and its "stage for later" option are gone.
- Step 4.4 saves nothing when no person can answer the question (a headless run, or /watch used inside another agent or workflow), so a pipeline that files its own pages never gets a duplicate `ext-` page.
- Step 4.4 no longer runs `open obsidian://…`; it prints where the report was saved and never launches or focuses an app.
- The "What v2 does differently" heading now says what the section covers: "What each watch produces beyond frames and a transcript".

### Added
- 4 unit tests for the Keychain lookup in `scripts/tests/test_keychain.py`.
- 5 unit tests for the research library setting in `scripts/tests/test_research_library.py`.

## [0.2.0] — 2026-05-25

Based on [bradautomates/claude-video](https://github.com/bradautomates/claude-video) v0.1.3 by Bradley Bonanno (MIT). Its pipeline (yt-dlp + ffmpeg + Whisper) is preserved; everything below is additive.

### Added
- Scene-change frame extraction in `scripts/frames.py` — `extract_scene_change()` + `select_hero_frames()` using ffmpeg's `select=gt(scene,...)` filter. One frame per detected shot instead of uniform every-N-seconds sampling. Keeps token cost flat on long videos. Uniform sampling still available as a fallback for static/screen-recorded sources.
- 0-10s hook microscope in `scripts/hook.py` — 2 fps frames + word-level Whisper transcript on the opening 10 seconds, so the report can tell you what's on screen *as each word lands*.
- Editorial pacing metrics in `scripts/pacing.py` — shot count, cuts/min, mean + median shot length.
- Structured `report.md` emitter in `scripts/report.py` — fixed-schema ingest-ready report with `<!-- pending Claude fill: ... -->` markers for narrative sections (TL;DR, key moments, hook breakdown, editorial profile, quotable moments, entities, concepts).
- Word-level timestamps in `scripts/whisper.py` (Groq + OpenAI backends extended).
- New CLI flags in `scripts/watch.py`: `--intent`, `--no-scene-change`, `--no-hook-microscope`.
- Step 4.4 (stage to Obsidian vault) + Step 4.5 (ingest gate) in `SKILL.md` — optional auto-save to your Obsidian vault. Path resolved via `$WATCH_VAULT_DIR` or auto-detected from `~/Second brain/`, `~/Documents/Obsidian/`, `~/Obsidian/`. Skips cleanly when no vault is detected.
- 7 unit tests under `scripts/tests/` (stdlib `unittest`, no pytest dependency).

### Changed
- `SKILL.md` is now a v2 contract — describes the structured report, the marker-fill step, and the vault config. Backwards-compatible with /watch invocations that don't care about ingest.
- README documents the added features and the `$WATCH_VAULT_DIR` configuration.

## [0.1.3] — 2026-05-09

### Fixed
- Windows: `video.info.json` is read as UTF-8 (#4). Previously `Path.read_text()` defaulted to cp1252 on Windows and crashed on yt-dlp's UTF-8 output, silently dropping Title/Uploader from the report. Same fix applied to `.env` reads/writes in `whisper.py` and `setup.py`.
- `download.py` now logs info.json parse failures to stderr instead of swallowing them.

### Security
- Hardened subprocess argv against option injection (#2): inserted `--` before the URL in the yt-dlp argv, and tightened `is_url` to reject `-`-prefixed sources and require a non-empty netloc. Resolved video/audio paths to absolute via `Path.resolve()` before passing to `ffmpeg`/`ffprobe`, so a relative path starting with `-` can't be misinterpreted as a flag.

## [0.1.2] — 2026-04-24

### Fixed
- Windows console crash: removed the emoji from the long-video warning in `watch.py`; cp1252 consoles couldn't encode it.
- `setup.py` now prints `winget` / `pip` install commands on Windows instead of "unsupported platform" — matches what the README already promised.

### Changed
- `SKILL.md` notes that on Windows the scripts must be invoked with `python`, not `python3` (the latter is the Microsoft Store stub on Windows).

## [0.1.1] — 2026-04-24

### Fixed
- Added `commands/watch.md` shim so `/watch` is callable when installed as a Claude Code plugin. Without it, the plugin loaded but the skill wasn't exposed as a slash command.
- `scripts/build-skill.sh` now strips `commands/` from the claude.ai `.skill` bundle alongside `hooks/` and `.claude-plugin/`.

## [0.1.0] — 2026-04-24

Initial marketplace release.

### Added
- `/watch <url-or-path> [question]` slash command.
- yt-dlp download with native caption extraction (manual + auto-subs).
- ffmpeg frame extraction with auto-scaled fps (≤2 fps, ≤100 frames, duration-aware budget).
- `--start` / `--end` focused mode with denser frame budget and transcript range filtering.
- Whisper fallback (Groq preferred, OpenAI secondary) for videos without captions.
- `setup.py` preflight: silent `--check`, structured `--json`, and installer that auto-runs `brew install` on macOS.
- Session-start hook that prints a one-line status on first run / partial config.
- `.skill` bundle packaging for claude.ai upload via `scripts/build-skill.sh`.
