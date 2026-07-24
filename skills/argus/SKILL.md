---
name: argus
description: Watch a YouTube video, Instagram reel, Short, or other video URL — transcript, frames, and audio — and file what it teaches into the watch-vault. Use when the user shares a video/reel URL to watch/process/take notes on, or asks to drain the watch queue.
allowed-tools: Bash(python "${CLAUDE_SKILL_DIR}/"*), Bash(python3 "${CLAUDE_SKILL_DIR}/"*), Bash(py -3 "${CLAUDE_SKILL_DIR}/"*)
---

# Argus

The hundred-eyed watchman: watches so the user doesn't have to, and files everything for later retrieval. Vault path and conventions live in the **argus-vault** skill — follow it for all writing and linking.

Usage: `/argus <url>` · `/argus <url> --frames` (force the frame pass) · `/argus queue`

Instance config (vault path, playlist URL, Telegram token) lives at `~/.claude/argus.config.json`. Config missing, or a needed piece empty? Follow [SETUP.md](SETUP.md) — Argus sets itself up in-line and keeps going; it never sends the user to a docs page. The Telegram token stays inside that file: [telegram.py](telegram.py) reads it and makes every Bot API call, so the token never enters a command line, a tool log, or this transcript.

**Never dead-end.** When a dependency or fetch fails: (1) try one auto-install or fix, (2) if it still fails, give the exact one-line fix for the user's OS, and (3) proceed with the best note this machine can produce right now, flagging what's missing in the note itself (`frames: no`, "audio unread — install faster-whisper to unlock"). The user always walks away with a note.

**Write for someone who wasn't there.** The reader did not watch the video and does not already know the vocabulary — the note fails if it can only be read by someone who did. So the TL;DR and Watch verdict are the on-ramp: everyday language, no term the reader wouldn't meet in ordinary conversation, and anything unavoidable glossed on the spot in a handful of words. Everything below them keeps exact names, flags, commands, and UI labels — paraphrasing a runbook makes it unusable, which is a different failure and a worse one.

Terms follow the vault's bar (argus-vault): one with a `topics/` page gets `[[linked]]` and is never re-explained here; one appearing in this video alone gets a one-line plain meaning inline, the first time it appears.

**Bundled scripts.** Call them as `<python> "${CLAUDE_SKILL_DIR}/<script>.py"`, where `<python>` is the `python_cmd` recorded in the config (`python` is only a guess, and on Windows the working runtime is often `py -3` or an absolute path). A config written before this key existed won't have it — resolve it per [SETUP.md](SETUP.md) step 6 and write it back, once, rather than guessing every run. `${CLAUDE_SKILL_DIR}` resolves wherever the skill is installed — personal, project, or a marketplace cache — so never guess a path.

**One working directory per item.** Everything downloaded or generated for an item lives in `<scratchpad>/argus/<source>-<id>/`: media, `transcript.txt`, `speech.txt`, `frames/`. Never write these to a shared directory — during a queue drain, three items are in flight at once, and a fixed name like `reel.mp4` means one worker reads another's video and quotes the wrong screen. Delete the directory once the note is written.

**Every yt-dlp call starts `yt-dlp --ignore-config --js-runtimes node`.** `--ignore-config` is what makes the anonymity promise true: by default yt-dlp reads the user's own config files, which can inject cookies, credentials, output paths, download archives, or postprocessors that Argus never asked for and the note never records. Argus passes its own flags and nothing else. (Node missing → drop `--js-runtimes node`, keep `--ignore-config`, try anyway, and note the one-line Node install if fetches act up.)

## Single item

1. **Ledger check — before any branch.** Ask for the item's identity rather than parsing the URL yourself, so the ledger, the note, and the Telegram inbox always agree on one name:
   ```
   <python> "${CLAUDE_SKILL_DIR}/note_writer.py" --identity <url>
   ```
   It prints `identity: <source>:<id>`, the `source`, and the timestamp-link template for that platform. If `videos/_processed.txt` holds that identity — or a bare `<id>` line, from ledgers written before identities were namespaced — report the existing note and stop.

   Reel or Short (`instagram.com/reel`, `/shorts/`)? Follow [REELS.md](REELS.md), which returns here for steps 6–8. Regular video: continue.
2. **Metadata first — it decides everything downstream.**
   ```
   yt-dlp --ignore-config --js-runtimes node --skip-download --print "%(title)s | %(channel)s | %(upload_date)s | %(duration_string)s" <url>
   ```
   **Over ~90 minutes, stop and ask before spending.** Reading a marathon transcript costs a large share of the user's usage window before a single word of the note exists, and a 3-sentence TL;DR of seven hours is a bad note anyway — long content is a season, not an episode. So say the real price and let them choose:

   > "This is 4h12m ≈ [rough cost: a large chunk of a session]. It has 14 chapters. Process **whole** (one note, one TL;DR), **by chapter** (one note, a section per chapter — recommended), or **pick chapters**?"

   Fetch chapters with `yt-dlp --ignore-config --js-runtimes node --skip-download --print "%(chapters)s" <url>`. By-chapter is the default recommendation because it matches how marathon content is actually used: someone wants the 20 minutes on one subject, and per-chapter TL;DRs plus deep links get them there. Process each chosen chapter as its own mini-item (own TL;DR, runbook, verdict) inside **one** note, using the chapter's start time for its deep links. No chapters published? Offer the same choice over ~30-minute slices instead.

   Also warn when the video is caption-less **and** over ~2 hours: local whisper runs at roughly 2–4× realtime, so that's hours of CPU before anything appears. Offer selected chapters only, or a stub note they can revisit.
3. **Tier 1 — transcript.**
   ```
   yt-dlp --ignore-config --js-runtimes node --skip-download --write-auto-subs --write-subs --sub-langs "en.*,en" --sub-format "vtt/srt/best" -o "%(id)s" <url>
   ```
   - No English subs? Run `--list-subs` and fetch the video's original language instead.
   - No captions in any language? Listen instead of stubbing — grab the *smallest* stream (whisper resamples to 16 kHz; quality is irrelevant, and platforms without audio-only streams, like X, would otherwise force a full-quality video download over throttled HLS):
   ```
   yt-dlp --ignore-config --js-runtimes node -f "bestaudio/worst[ext=mp4]/worst" --concurrent-fragments 8 -o "%(id)s.%(ext)s" <url>
   <python> "${CLAUDE_SKILL_DIR}/transcribe_audio.py" <downloaded file> transcript.txt
   ```
   (faster-whisper installs on first use per SETUP.md; local, no upload; it reads video containers directly — no extraction step). A download crawling under ~50 KB/s after 2 minutes is throttled: kill it and retry the next format in the chain rather than waiting. Only if transcription is impossible on this machine: write a stub note (metadata, `watch-verdict: watch`, body: "No captions and no local transcription — needs eyeballs"), add a digest line saying so, ledger it, and stop.
   - Collapse the rolling captions before reading. Raw auto-captions repeat every line roughly 3 times. Pass the bare video id, not a filename: the script finds whichever language suffix yt-dlp actually wrote (`.en`, `.en-orig`, `.en-US`, and others) and reads VTT or SRT either way, so no ffmpeg is needed to get a transcript.
   ```
   <python> "${CLAUDE_SKILL_DIR}/clean_transcript.py" <id> transcript.txt
   ```
   For a selected chapter or custom window, pass its absolute source seconds. The output keeps those original timestamps:
   ```
   <python> "${CLAUDE_SKILL_DIR}/clean_transcript.py" <id> transcript-<chapter>.txt --start <start> --end <end> --duration <source-duration>
   ```
   Use the duration reported by step 2. Download captions once, then run this command once per selected chapter against the same caption file. Put every chapter result and the frames from its own `frames-<chapter>/` directory into the one video note described in step 6. Never trim or re-zero the media or captions.
   It exits non-zero if the file parses to nothing — that is a **no-captions** result, so fall through to the audio path above; never treat it as a quiet video.
   Read `transcript.txt`. Done when you can state the video's type (tutorial | news | explainer | opinion | workflow) and a 3-sentence TL;DR.
4. **Tier decision.** Run the frame pass if the type is tutorial/demo, the transcript points at the screen ("as you can see", "click here", "this code", "paste this"), or `--frames` was passed. Two exits to Tier 1 only: a talking head with nothing on screen, or **duration over 60 minutes** (record which in the note; `--frames` overrides the length cap). Frames for a chosen chapter of a long video are fine — pass its time window to the frame script rather than the whole file.
5. **Frame pass.** Follow [FRAMES.md](FRAMES.md).
6. **Write the note through the serializer — never by hand.** Write the body (the template below, minus frontmatter) to `body.md` in the working directory, the metadata to `meta.json`, then:
   ```
   <python> "${CLAUDE_SKILL_DIR}/note_writer.py" --vault <vault_path> --meta meta.json --body body.md
   ```
   It owns the filename, the frontmatter, and an atomic write, and prints the note path plus the timestamp-link template to use. This is not ceremony: a title carrying `:` or a newline silently breaks the frontmatter, `[`/`]`/`#` break every `[[wikilink]]` aimed at the note, Windows rejects `<>:"/\|?*` and reserved names outright, and a vault inside OneDrive is deep enough that a long title overruns the path limit. It also rejects an unknown `type` or `watch-verdict`, which is what keeps the enums here and in argus-vault from drifting apart.
   `meta.json` keys: `title`, `channel`, `url` (the real one, whatever the platform), `published`, `duration`, `type`, `tags`, `watch_verdict`, `frames`. Verdict bar: `watch` is rare — only when doing beats reading (hands-on feel, dense visual demos); always name the exact minute ranges worth the eyeballs. Content demonstrating a usable workflow gets `try` and a `Try Queue.md` entry instead (argus-vault conventions). Chapter-processed videos keep one note with a `## <chapter title> [mm:ss]` section per chapter, each carrying its own TL;DR and runbook, plus one overall TL;DR and verdict at the top.
   Done when `note_writer.py` has printed the note path, every Runbook step is executable without opening the video, and every section that does not apply has been deleted rather than left empty.
7. **Cross-link.** Create or append `tools/` dossiers per the argus-vault dossier bar (memorable tools, techniques, and named methods get a page; household names stay inline as plain text); link the note from every `topics/` MOC it touches, creating MOCs per argus-vault rules. Done when every dossier-worthy item has an entry and the note is reachable from at least one MOC.
8. **Digest + ledger.** Prepend the run's entry below the `---` in `Digest.md`: date, `[[note]]`, TL;DR line, verdict. If `Digest.md` now holds more than 10 run entries, move the oldest overflow into `Digest Archive.md`. Append the step-1 identity (`<source>:<id>`) to `videos/_processed.txt` — reels and shorts included, or the queue re-drains them forever. Delete downloaded media. End with a chat summary: what was watched, the verdict, anything flagged outdated.

## Queue drain (`/argus queue`)

1. **Collect from both doors:**
   - Playlist: `yt-dlp --ignore-config --js-runtimes node --flat-playlist --print id <playlist_url from config>`
   - Telegram inbox:
     ```
     <python> "${CLAUDE_SKILL_DIR}/telegram.py" fetch
     ```
     It prints one `identity<TAB>url<TAB># comment` line per item still waiting, already filtered to the paired owner and to items missing from the ledger. It reads the token itself — never construct a Bot API URL. Items land in the vault's `_inbox.jsonl` and are fsynced *before* the Telegram offset advances, because reading updates deletes them server-side: a crash mid-drain would otherwise lose the queue for good. Telegram also forgets anything older than 24 hours, so the inbox file, not the chat, is the queue. Not paired yet, or no token? It says so and exits; the playlist alone is a fine queue.
   Drop anything already in the ledger.
2. **Ask about the long ones up front.** Check every collected item's duration first (`yt-dlp --ignore-config --js-runtimes node --flat-playlist --print "%(duration_string)s|%(title)s"` on the playlist; a `--skip-download --print` per Telegram URL). Anything over ~90 minutes goes in one question to the user *before* any subagent starts — subagents can't ask, and a drain that silently eats a session's tokens on someone's 4-hour lecture is the fastest way to lose their trust. List the long items with their lengths and offer: by chapter (recommended), whole, or leave in the queue for later. Then pass the decision into that item's subagent prompt.
3. **One subagent per item, isolated.** A frame pass is image-heavy, and a multi-item drain done inline will exhaust the context window. For each remaining item, oldest first, launch a subagent. Run up to 3 at a time, but **only one may transcribe at a time** — whisper is CPU-bound, and three at once turns "2–4× realtime" into something far worse for all three.

   Each worker's prompt carries: the URL, its own working directory `<scratchpad>/argus/<source>-<id>/`, the long-video decision from step 2, and **the current `tools/` and `topics/` filenames** — without that list, two workers coin "Claude Code" and "claude-code" for the same tool and the merge cannot tell they are one thing.

   The worker follows the single-item flow inside its own directory and **writes exactly one file: its own video note**, via `note_writer.py`. It touches no shared file — not the ledger, not a dossier, not a MOC, not `Try Queue.md`, not `Digest.md`. Concurrent appends to one markdown file lose each other's writes. It replies with only this block:
   ```
   identity: <source>:<id>
   note: <note filename>
   digest: <one line — TL;DR, verdict, outdated flags>
   dossiers: <Name> — <what this video said about it>    (one per line, "none" if none)
   topics: <MOC name>                                     (one per line, "none" if none)
   try: <Try Queue.md line, or "none">
   ```
4. **The main session applies every shared write, one at a time**, from the returned blocks: append each `identity` to `videos/_processed.txt`, merge `dossiers` into `tools/` pages, add the note to each `topics/` MOC, add `try` lines to `Try Queue.md` and refresh its weekly pick if stale (see argus-vault), then write one combined `Digest.md` entry. Reusing an existing dossier name beats coining a variant. Then, if the bot is configured, **push the digest to Telegram** (the bot is outbox as well as inbox) — write the message to a file and send it, so the token stays in the config:
   ```
   <python> "${CLAUDE_SKILL_DIR}/telegram.py" send --file digest.txt
   ```
   Message shape — short, phone-glanceable, every item deep-linked, under ~15 lines:
   ```
   👁️ Argus watched <N> items
   🧪 This week's try: <workflow> — <one line> (<source link>)
   👀 Worth eyeballs: <title> <mm:ss–mm:ss> <youtu.be link with ?t=>
   ⏭️ <n> skips — full digest in the vault
   ```
   Omit empty sections. No token, no owner id, or the send fails? Skip silently — `Digest.md` is the fallback front page; never block the drain on Telegram.
5. One chat summary: N items, which (if any) earned `watch`/`try` and why. Done when the ledger contains every collected ID (minus anything the user chose to leave queued) and the digest (Telegram if configured, `Digest.md` always) is written.

## Note body template

Write this to `body.md` — no frontmatter. `note_writer.py` emits the frontmatter from `meta.json`, so the field list and its enums live in one place (the script) instead of being restated here and in argus-vault.

Delete any section that does not apply rather than leaving it empty. Deep links: use the `link:` template `note_writer.py` printed — YouTube gets `?t=<seconds>`, and a source without timestamp links gets a plain `[m:ss]` rather than an invented URL.

```markdown
## TL;DR
(≤3 sentences, everyday language — see "Write for someone who wasn't there")

## Watch verdict
Verdict + the minute ranges that deserve eyeballs, or why none do.

## Why this works           <!-- `try` and `watch` verdicts only -->
What the moving parts are, what each phase of the runbook is actually for, and
which steps are essential versus the author's taste. This is what lets a reader
recover when their screen doesn't match the video. Skip it entirely for `skip`
and `skim` — nobody implements those, so it would be pure cost.

## Prerequisites            <!-- tutorials: what the video assumes installed / signed up / known / on hand -->

## Runbook                  <!-- tutorials/workflows: reproducible WITHOUT watching -->
1. Numbered steps with exact commands, config, quantities, and UI locations, quoted from frames.
   **Capture what the video says to copy.** A step reading "paste this file" or
   "use this prompt" is not reproducible if the thing itself lives elsewhere —
   put the actual text in the note. Free when it was on screen or in the
   transcript, since you already read it. When it sits behind an external link
   (a gist, a repo), record the link and what it contains, and fetch the
   contents only if the user asks — don't spend a download on it mid-run.

## Outdated flags
Anything time-sensitive that may have rotted: stale syntax, renamed flags, deprecated models/APIs, old prices or versions — or "None spotted".

## Key claims & facts       <!-- news/explainers -->
- Claim — [mm:ss](https://youtu.be/<id>?t=<seconds>)

## Tools & projects
- [[Name]] — what this video said about it (dossier-worthy tools/techniques only; household names as plain text)

## Timestamps
- [mm:ss](https://youtu.be/<id>?t=<seconds>) — moment worth jumping to
```
