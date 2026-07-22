# Reel pass (Instagram reels, YouTube Shorts, other short vertical video)

Reels carry their payload three ways at once: speech, burned-in text overlays, and the post caption. Argus reads all three, aligned.

1. Download (anonymous — never with cookies or a login) and grab the caption text:
   ```
   yt-dlp --js-runtimes node -o "reel.%(ext)s" <url>
   yt-dlp --js-runtimes node --skip-download --print "%(uploader)s | %(title)s | %(description)s" <url>
   ```
   Download blocked or link dead? Write a stub note (`watch-verdict: watch`, body: "Could not fetch — needs eyeballs, open on phone"), digest it, ledger it, stop. Never retry with credentials.
2. Ears — transcribe the audio (faster-whisper, local, handles Hindi/Hinglish):
   ```
   python "<this skill's folder>/transcribe_audio.py" reel.mp4 speech.txt
   ```
3. Eyes — reels are too short for scene detection; take a still every 2 seconds:
   ```
   ffmpeg -i reel.mp4 -vf fps=1/2 frames/%03d.jpg
   ```
   Frame N sits at (N-1)×2 seconds. Read every frame beside the speech at its timestamp; transcribe overlays, prompts, commands, and app names exactly.
4. Write the note like any video (template in SKILL.md), plus:
   - `source: instagram` (or `youtube-shorts`) in frontmatter.
   - Reels showing a usable workflow get `watch-verdict: try` and an entry in the vault's `Try Queue.md` (see obsidian-vault conventions).
   - If the user attached a comment when sharing to the bot, quote it in the note under `## Why saved`.

Done when the note's runbook quotes what the reel *showed*, not just what it said — overlays included.
