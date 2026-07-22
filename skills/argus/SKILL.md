---
name: argus
description: Watch a YouTube video or Instagram reel — transcript, frames, and audio — and file what it teaches into the Obsidian vault. Use when the user shares a video/reel URL to watch/process/take notes on, or asks to drain the watch queue.
---

# Argus

The hundred-eyed watchman: watches so the user doesn't have to, and files everything for later retrieval. Vault path and conventions live in the **obsidian-vault** skill — follow it for all writing and linking.

Usage: `/argus <url>` · `/argus <url> --frames` (force the frame pass) · `/argus queue`

Instance config (vault path, playlist URL, Telegram token, dashboard URL) lives at `~/.claude/argus.config.json`. **Never commit it or echo the token.** Config missing, or a needed piece empty? Follow [SETUP.md](SETUP.md) — Argus sets itself up in-line and keeps going; it never sends the user to a docs page.

Download into the scratchpad only; delete media once the note is written. Add `--js-runtimes node` to every yt-dlp call.

## Single item

Reel or Short (instagram.com/reel, /shorts/)? Follow [REELS.md](REELS.md). Regular video:

1. **Ledger check.** Extract the video ID. If it is in `videos/_processed.txt`, report the existing note and stop.
2. **Tier 1 — transcript.**
   ```
   yt-dlp --js-runtimes node --skip-download --write-auto-subs --write-subs --sub-langs "en.*,en" --convert-subs srt -o "%(id)s" <url>
   yt-dlp --js-runtimes node --skip-download --print "%(title)s | %(channel)s | %(upload_date)s | %(duration_string)s" <url>
   ```
   - No English subs? Run `--list-subs` and fetch the video's original language instead.
   - No captions in any language? Write a stub note (metadata, `watch-verdict: watch`, body: "No captions — Argus could not watch this; needs eyeballs"), add a digest line saying so, ledger it, and stop.
   - Collapse the rolling SRT before reading — raw auto-captions repeat every line ~3×:
   ```
   python "<this skill's folder>/clean_transcript.py" <id>.en.srt transcript.txt
   ```
   Read `transcript.txt`. Done when you can state the video's type (tutorial | news | explainer | opinion) and a 3-sentence TL;DR.
3. **Tier decision.** Run the frame pass if the type is tutorial/demo, the transcript points at the screen ("as you can see", "click here", "this code", "paste this"), or `--frames` was passed. Two exits to Tier 1 only: a talking head with nothing on screen, or **duration over 60 minutes** (record which in the note; `--frames` overrides the length cap).
4. **Frame pass.** Follow [FRAMES.md](FRAMES.md).
5. **Write the note** to `videos/YYYY-MM-DD - <Title>.md` (published date) using the template below. Verdict bar: `watch` is rare — only when doing beats reading (hands-on feel, dense visual demos); always name the exact minute ranges worth the eyeballs. Content demonstrating a usable workflow gets `try` and a `Try Queue.md` entry instead (obsidian-vault conventions).
6. **Cross-link.** Create or append `tools/` dossiers per the obsidian-vault dossier bar (memorable AI tooling gets a page; household names stay inline as plain text); link the note from every `topics/` MOC it touches, creating MOCs per obsidian-vault rules. Done when every dossier-worthy tool has an entry and the note is reachable from at least one MOC.
7. **Digest + ledger.** Prepend the run's entry below the `---` in `Digest.md`: date, `[[note]]`, TL;DR line, verdict. If `Digest.md` now holds more than 10 run entries, move the oldest overflow into `Digest Archive.md`. Append the video ID to `videos/_processed.txt`. Delete downloaded media. End with a chat summary: what was watched, the verdict, anything flagged outdated.

## Queue drain (`/argus queue`)

1. **Collect from both doors:**
   - Playlist: `yt-dlp --js-runtimes node --flat-playlist --print id <playlist_url from config>`
   - Telegram inbox: `GET https://api.telegram.org/bot<token>/getUpdates?offset=<telegram_offset+1>` — pull every message; keep URLs (with any accompanying text as the user's comment). First ever message fixes `telegram_owner_id` in the config; thereafter ignore messages from anyone else. After a successful drain, write the highest `update_id` back to `telegram_offset`.
   Drop anything already in the ledger.
2. **One subagent per item** — a frame pass is image-heavy, and a multi-item drain done inline will exhaust the context window. For each remaining item, oldest first, launch a subagent whose prompt is: follow the argus skill's single-item flow for `<url>`, skipping the Digest step, and reply with exactly the one-line digest entry (note name, TL;DR, verdict, outdated flags). Run up to 3 at a time.
3. The main session writes one combined Digest entry from the collected lines, updates `Try Queue.md`'s weekly pick if stale (see obsidian-vault), then **rebuilds the dashboard** per [DASHBOARD.md](DASHBOARD.md). One chat summary: N items, which (if any) earned `watch`/`try` and why. Done when the ledger contains every collected ID and the dashboard is republished.

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

## Prerequisites            <!-- tutorials: what the video assumes installed / signed up / known -->

## Runbook                  <!-- tutorials/workflows: reproducible WITHOUT watching -->
1. Numbered steps with exact commands, config, and UI locations, quoted from frames.

## Outdated flags
Stale syntax, renamed flags, deprecated models/APIs — or "None spotted".

## Key claims & facts       <!-- news/explainers -->
- Claim — [mm:ss](https://youtu.be/<id>?t=<seconds>)

## Tools & projects
- [[ToolName]] — what this video said about it (dossier-worthy tools only; household names as plain text)

## Timestamps
- [mm:ss](https://youtu.be/<id>?t=<seconds>) — moment worth jumping to
```
