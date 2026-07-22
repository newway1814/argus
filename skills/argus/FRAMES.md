# Frame pass

Goal: read what the transcript only points at. Every frame is read beside the words spoken at its timestamp — frame + speech = what is actually happening.

1. Download video-only, 720p (code must be legible), sponsor segments cut, into the scratchpad:
   ```
   yt-dlp --js-runtimes node --sponsorblock-remove sponsor -f "bestvideo[height<=720]" -o "%(id)s.%(ext)s" <url>
   ```
2. Extract scene changes with timestamps:
   ```
   ffmpeg -i <file> -vf "select='gt(scene,0.10)',showinfo" -fps_mode vfr frames/%04d.jpg 2> showinfo.log
   ```
   Each frame's timestamp is its `pts_time` in `showinfo.log`.
3. Calibrate to 30–80 frames — 80 is the hard budget at any video length. Over budget → raise the threshold (0.20, 0.30) and rerun; fewer than 10 on a screen-heavy video → lower it to 0.05.
4. **Fill the blind spots — mechanical, not judgment:**
   - Frames within 1 second of each other are one moment (a transition animation); read only the last of the cluster.
   - List the gaps between consecutive kept timestamps. Any gap over 60 seconds while the transcript is screen-narrating (typing, demoing, walking through UI) gets explicit stills every ~20 seconds across it:
   ```
   ffmpeg -y -ss <seconds> -i <file> -frames:v 1 stills/still_<seconds>.jpg
   ```
   Gradual screens (live typing) dodge scene detection — this rule is what catches them.
5. Read the frames in batches, each beside the transcript lines at its timestamp. Hunt: commands, config files, code, UI paths, URLs, benchmark tables — anything the speaker calls "this" or "here". Transcribe them exactly; they become the runbook.

Done when nothing in the runbook says "shown on screen" without the actual content quoted beside it.
