# First-run setup

Argus configures itself. Never send the user to edit files or read docs — detect, ask only what can't be detected, write the config, keep going with whatever they originally asked for.

Config lives at `~/.claude/argus.config.json`:

```json
{
  "vault_path": "",
  "playlist_url": "",
  "telegram_token": "",
  "telegram_bot": "",
  "telegram_owner_id": null,
  "telegram_offset": 0,
  "dashboard_url": ""
}
```

## No config at all (first ever run)

1. **Find the vault.** Read Obsidian's own registry — it lists every vault and which is open:
   - Windows: `%APPDATA%\obsidian\obsidian.json`
   - macOS: `~/Library/Application Support/obsidian/obsidian.json`
   - Linux: `~/.config/obsidian/obsidian.json`
   One vault → use it. Several → ask which. Obsidian not installed → offer to create a plain folder (default `~/Documents/Argus Vault`); it's ordinary markdown they can open in Obsidian anytime.
2. **Ask one placement question** if the chosen vault already has the user's own notes: file Argus material at the vault root, or under an `Argus/` subfolder? (Empty vault → root, don't ask.)
3. **Scaffold what's missing, never overwrite:** `videos/`, `topics/`, `tools/`, `Digest.md`, `Try Queue.md`, and a `Welcome.md` home note (skip if one exists).
4. **Check yt-dlp**: `yt-dlp --version` fails → `pip install yt-dlp` (tell the user, don't ask permission for this one — it's the tool's core dependency).
5. Write the config, then continue with the URL the user gave. Total user-facing cost: at most two questions.

## Lazy pieces — set up only when first needed

| Trigger | What to do |
|---|---|
| First frame pass, ffmpeg missing | Install per OS (`winget install Gyan.FFmpeg` / `brew install ffmpeg` / apt), with the user's OK. |
| First reel, faster-whisper missing | `pip install faster-whisper` (say the small model downloads ~500MB once). |
| `/argus queue`, no `playlist_url` | Walk them through it in chat: YouTube → Library → New playlist → visibility **Unlisted** → paste the URL here. Explain why unlisted: readable with zero login, their account never touched. |
| `/argus queue`, no `telegram_token` | Offer the universal inbox: message @BotFather → `/newbot` → paste the token here. From then on: Share → Telegram → their bot, from any app. Skippable — the playlist alone is a fine queue. |
| First drain finishes, no `dashboard_url` | Build and publish the dashboard per DASHBOARD.md, store the minted URL. |

Never ask about a piece the user hasn't triggered. Done when the original request (watch this URL / drain the queue) has been fulfilled — setup is a detour, not a destination.
