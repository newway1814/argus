# Reel pass (Instagram reels, YouTube Shorts, other short vertical video)

Reels carry their payload three ways at once: speech, burned-in text overlays, and the post caption. Argus reads all three, aligned.

Arrive here from SKILL.md step 1 — the ledger check has already run and fixed this item's identity (`instagram:<shortcode>`, `youtube:<id>`).

1. Download (anonymous — `--ignore-config` keeps the user's own yt-dlp config, and any cookies in it, out of the request) and grab the caption text:
   ```
   yt-dlp --ignore-config --js-runtimes node -o "reel.%(ext)s" <url>
   yt-dlp --ignore-config --js-runtimes node --skip-download --print "%(uploader)s | %(title)s | %(description)s" <url>
   ```
   Download blocked or link dead? Write a stub note (`watch-verdict: watch`, body: "Could not fetch — needs eyeballs, open on phone"), digest it, ledger the identity, stop. Never retry with credentials.
2. Ears — transcribe the audio (faster-whisper, local, handles Hindi/Hinglish):
   ```
   <python> "${CLAUDE_SKILL_DIR}/transcribe_audio.py" reel.mp4 speech.txt
   ```
3. Eyes — reels are too short for scene detection, so ask for explicit stills every 2 seconds (`--stills 0,2,4,…` up to the reel's length):
   ```
   <python> "${CLAUDE_SKILL_DIR}/extract_frames.py" reel.mp4 frames/ --stills 0,2,4,6,8,10,12,14
   ```
   Same script as the video path, so each filename carries its own timestamp (`frame_0m08s.jpg` is at 0:08) and no frame-number arithmetic can drift. It creates `frames/`, refuses a still past the end of the reel, and fails loudly rather than reporting frames it did not write. Read every frame beside the speech at its timestamp; transcribe overlays, prompts, commands, and app names exactly.
4. **Return to SKILL.md and finish there — steps 6, 7, and 8: write the note, cross-link, then digest *and ledger*.** A reel that skips step 8 is never recorded, so the queue re-drains it every time. The reel adds to the note:
   - `source: instagram` (or `youtube-shorts`) in frontmatter, and the real reel URL in `url:` — the template's `youtu.be/<id>` shape is YouTube's, and Instagram has no `?t=` deep links, so cite overlay moments as plain `[m:ss]` with no link rather than inventing one.
   - Reels showing a usable workflow get `watch-verdict: try` and an entry in the vault's `Try Queue.md` (see argus-vault conventions).
   - If the user attached a comment when sharing to the bot, quote it in the note under `## Why saved`.

Done when the note's runbook quotes what the reel *showed*, not just what it said — overlays included — and the identity is in `videos/_processed.txt`.
