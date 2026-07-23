---
name: argus
description: Watch a YouTube video or Instagram reel — transcript, frames, and audio — and file what it teaches into the watch-vault. Use when the user shares a video/reel URL to watch/process/take notes on, or asks to drain the watch queue.
---

# Argus

The hundred-eyed watchman: watches so the user doesn't have to, and files everything for later retrieval. Vault path and conventions live in the **argus-vault** skill — follow it for all writing and linking.

Usage: `/argus <url>` · `/argus <url> --frames` (force the frame pass) · `/argus queue`

Instance config (vault path, playlist URL, Telegram token) lives at `~/.claude/argus.config.json`. **Never commit it or echo the token.** Config missing, or a needed piece empty? Follow [SETUP.md](SETUP.md) — Argus sets itself up in-line and keeps going; it never sends the user to a docs page.

**Never dead-end.** When a dependency or fetch fails: (1) try one auto-install or fix, (2) if it still fails, give the exact one-line fix for the user's OS, and (3) proceed with the best note this machine can produce right now, flagging what's missing in the note itself (`frames: no`, "audio unread — install faster-whisper to unlock"). The user always walks away with a note.

Download into the scratchpad only; delete media once the note is written. Add `--js-runtimes node` to every yt-dlp call (Node missing → drop the flag, try anyway, and note the one-line Node install if fetches act up).

## Single item

Reel or Short (instagram.com/reel, /shorts/)? Follow [REELS.md](REELS.md). Regular video:

1. **Ledger check.** Extract the video ID. If it is in `videos/_processed.txt`, report the existing note and stop.
2. **Metadata first — it decides everything downstream.**
   ```
   yt-dlp --js-runtimes node --skip-download --print "%(title)s | %(channel)s | %(upload_date)s | %(duration_string)s" <url>
   ```
   **Over ~90 minutes, stop and ask before spending.** Reading a marathon transcript costs a large share of the user's usage window before a single word of the note exists, and a 3-sentence TL;DR of seven hours is a bad note anyway — long content is a season, not an episode. So say the real price and let them choose:

   > "This is 4h12m ≈ [rough cost: a large chunk of a session]. It has 14 chapters. Process **whole** (one note, one TL;DR), **by chapter** (one note, a section per chapter — recommended), or **pick chapters**?"

   Fetch chapters with `yt-dlp --js-runtimes node --skip-download --print "%(chapters)s" <url>`. By-chapter is the default recommendation because it matches how marathon content is actually used: someone wants the 20 minutes on one subject, and per-chapter TL;DRs plus deep links get them there. Process each chosen chapter as its own mini-item (own TL;DR, runbook, verdict) inside **one** note, using the chapter's start time for its deep links. No chapters published? Offer the same choice over ~30-minute slices instead.

   Also warn when the video is caption-less **and** over ~2 hours: local whisper runs at roughly 2–4× realtime, so that's hours of CPU before anything appears. Offer selected chapters only, or a stub note they can revisit.
3. **Tier 1 — transcript.**
   ```
   yt-dlp --js-runtimes node --skip-download --write-auto-subs --write-subs --sub-langs "en.*,en" --convert-subs srt -o "%(id)s" <url>
   ```
   - No English subs? Run `--list-subs` and fetch the video's original language instead.
   - No captions in any language? Listen instead of stubbing — grab the *smallest* stream (whisper resamples to 16 kHz; quality is irrelevant, and platforms without audio-only streams, like X, would otherwise force a full-quality video download over throttled HLS):
   ```
   yt-dlp --js-runtimes node -f "bestaudio/worst[ext=mp4]/worst" --concurrent-fragments 8 -o "%(id)s.%(ext)s" <url>
   python "<this skill's folder>/transcribe_audio.py" <downloaded file> transcript.txt
   ```
   (faster-whisper installs on first use per SETUP.md; local, no upload; it reads video containers directly — no extraction step). A download crawling under ~50 KB/s after 2 minutes is throttled: kill it and retry the next format in the chain rather than waiting. Only if transcription is impossible on this machine: write a stub note (metadata, `watch-verdict: watch`, body: "No captions and no local transcription — needs eyeballs"), add a digest line saying so, ledger it, and stop.
   - Collapse the rolling SRT before reading — raw auto-captions repeat every line ~3×:
   ```
   python "<this skill's folder>/clean_transcript.py" <id>.en.srt transcript.txt
   ```
   Read `transcript.txt`. Done when you can state the video's type (tutorial | news | explainer | opinion) and a 3-sentence TL;DR.
4. **Tier decision.** Run the frame pass if the type is tutorial/demo, the transcript points at the screen ("as you can see", "click here", "this code", "paste this"), or `--frames` was passed. Two exits to Tier 1 only: a talking head with nothing on screen, or **duration over 60 minutes** (record which in the note; `--frames` overrides the length cap). Frames for a chosen chapter of a long video are fine — pass its time window to the frame script rather than the whole file.
5. **Frame pass.** Follow [FRAMES.md](FRAMES.md).
6. **Write the note** to `videos/YYYY-MM-DD - <Title>.md` (published date) using the template below. Verdict bar: `watch` is rare — only when doing beats reading (hands-on feel, dense visual demos); always name the exact minute ranges worth the eyeballs. Content demonstrating a usable workflow gets `try` and a `Try Queue.md` entry instead (argus-vault conventions). Chapter-processed videos keep one note with a `## <chapter title> [mm:ss]` section per chapter, each carrying its own TL;DR and runbook, plus one overall TL;DR and verdict at the top.
7. **Cross-link.** Create or append `tools/` dossiers per the argus-vault dossier bar (memorable tools, techniques, and named methods get a page; household names stay inline as plain text); link the note from every `topics/` MOC it touches, creating MOCs per argus-vault rules. Done when every dossier-worthy item has an entry and the note is reachable from at least one MOC.
8. **Digest + ledger.** Prepend the run's entry below the `---` in `Digest.md`: date, `[[note]]`, TL;DR line, verdict. If `Digest.md` now holds more than 10 run entries, move the oldest overflow into `Digest Archive.md`. Append the video ID to `videos/_processed.txt`. Delete downloaded media. End with a chat summary: what was watched, the verdict, anything flagged outdated.

## Queue drain (`/argus queue`)

1. **Collect from both doors:**
   - Playlist: `yt-dlp --js-runtimes node --flat-playlist --print id <playlist_url from config>`
   - Telegram inbox: `GET https://api.telegram.org/bot<token>/getUpdates?offset=<telegram_offset+1>` — pull every message; keep URLs (with any accompanying text as the user's comment). First ever message fixes `telegram_owner_id` in the config; thereafter ignore messages from anyone else. After a successful drain, write the highest `update_id` back to `telegram_offset`.
   Drop anything already in the ledger.
2. **Ask about the long ones up front.** Check every collected item's duration first (`yt-dlp --js-runtimes node --flat-playlist --print "%(duration_string)s|%(title)s"` on the playlist; a `--skip-download --print` per Telegram URL). Anything over ~90 minutes goes in one question to the user *before* any subagent starts — subagents can't ask, and a drain that silently eats a session's tokens on someone's 4-hour lecture is the fastest way to lose their trust. List the long items with their lengths and offer: by chapter (recommended), whole, or leave in the queue for later. Then pass the decision into that item's subagent prompt.
3. **One subagent per item** — a frame pass is image-heavy, and a multi-item drain done inline will exhaust the context window. For each remaining item, oldest first, launch a subagent whose prompt is: follow the argus skill's single-item flow for `<url>`, skipping the Digest step, and reply with exactly the one-line digest entry (note name, TL;DR, verdict, outdated flags). Run up to 3 at a time.
4. The main session writes one combined Digest entry from the collected lines and updates `Try Queue.md`'s weekly pick if stale (see argus-vault). Then, if `telegram_token` and `telegram_owner_id` are set, **push the digest to Telegram** (the bot is outbox as well as inbox):
   ```
   POST https://api.telegram.org/bot<token>/sendMessage
   chat_id=<telegram_owner_id>, disable_web_page_preview=true
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

## Note template

```markdown
---
title:
channel:
url: https://youtu.be/<id>
published: YYYY-MM-DD
processed: YYYY-MM-DD
duration:
type: tutorial | news | explainer | opinion | workflow
tags: []
watch-verdict: skip | skim | watch | try
frames: yes | no
---

## TL;DR
(≤3 sentences)

## Watch verdict
Verdict + the minute ranges that deserve eyeballs, or why none do.

## Prerequisites            <!-- tutorials: what the video assumes installed / signed up / known / on hand -->

## Runbook                  <!-- tutorials/workflows: reproducible WITHOUT watching -->
1. Numbered steps with exact commands, config, quantities, and UI locations, quoted from frames.

## Outdated flags
Anything time-sensitive that may have rotted: stale syntax, renamed flags, deprecated models/APIs, old prices or versions — or "None spotted".

## Key claims & facts       <!-- news/explainers -->
- Claim — [mm:ss](https://youtu.be/<id>?t=<seconds>)

## Tools & projects
- [[Name]] — what this video said about it (dossier-worthy tools/techniques only; household names as plain text)

## Timestamps
- [mm:ss](https://youtu.be/<id>?t=<seconds>) — moment worth jumping to
```
