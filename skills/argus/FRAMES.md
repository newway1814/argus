# Frame pass

Goal: read what the transcript only points at. Every frame is read beside the words spoken at its timestamp — frame + speech = what is actually happening.

1. Download video-only, 720p (code must be legible), into the scratchpad:
   ```
   yt-dlp -f "bestvideo[height<=720]" -o "%(id)s.%(ext)s" <url>
   ```
2. Extract scene changes with timestamps:
   ```
   ffmpeg -i <file> -vf "select='gt(scene,0.10)',showinfo" -fps_mode vfr frames/%04d.jpg 2> showinfo.log
   ```
   Each frame's timestamp is its `pts_time` in `showinfo.log`.
3. Calibrate to 30–80 frames: more than 80 → raise the threshold (0.20, 0.30) and rerun; fewer than 10 on a screen-heavy video → lower it to 0.05.
4. Read the frames in batches, each beside the transcript lines at its `pts_time`. Hunt: commands, config files, code, UI paths, URLs, benchmark tables — anything the speaker calls "this" or "here". Transcribe them exactly; they become the runbook.
5. Gradual screens (live typing) dodge scene detection. If the transcript says code was written but no frame shows the finished file, pull explicit stills:
   ```
   ffmpeg -ss <seconds> -i <file> -frames:v 1 still_<seconds>.jpg
   ```

Done when nothing in the runbook says "shown on screen" without the actual content quoted beside it.
