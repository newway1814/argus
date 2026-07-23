# Frame pass

Goal: read what the transcript only points at. Every frame is read beside the words spoken at its timestamp, frame + speech = what is actually happening.

1. **Check the frame capability before downloading video.** Verify both `ffmpeg` and `ffprobe` are available. If either is missing, do not install it and do not download the video-only stream. Return to SKILL.md with `frames: no`, continue transcript-only, and state that on-screen details were not verified. Do not claim the frame pass completed.
2. Download video-only, 720p (code must be legible), into the scratchpad:
   ```
   yt-dlp --ignore-config --js-runtimes node -f "bestvideo[height<=720]/best[height<=720]/best" -o "%(id)s.%(ext)s" <url>
   ```
   **Never cut segments out of this file.** Removing sponsors (or any other range) shortens the timeline, so every frame after the first cut carries a timestamp that no longer matches the transcript beside it or the `?t=` link in the note, silently, and the note looks perfect while pointing at the wrong minute. Frame timestamps must stay on the same clock as the source. Sponsor reads are cheap to skip while reading; a shifted clock corrupts every deep link in the note.
3. Extract the frames, one command, one decode:
   ```
   <python> "${CLAUDE_SKILL_DIR}/extract_frames.py" <file> frames/
   ```
   The script scans the video once for scene-change candidates and their scores, writing no images, so a dense screencast cannot bury the scratchpad, collapses bursts (frames within 1s of a burst's start are one moment, a transition animation), keeps the highest-scoring frames within an 80-frame budget, then grabs only those by timestamp. It falls back to even sampling when scene detection finds nothing usable (live typing and gradual screens dodge it), and reports which mode it used. No thresholds to tune, no reruns. Each filename is its own timestamp: `frame_14m22s.jpg` sits at 14:22.

   It writes into a **fresh** directory: given one that already holds frames it stops rather than mixing another video's screens into this one's evidence. Use the item's own working directory (`<workdir>/frames/`), or pass `--clean`.
4. **Fill the blind spots, the script reports, you judge.** The script ends by listing every gap over 60 seconds: between kept frames, before the first one, and after the last. A video whose action sits in the middle leaves long unwatched head and tail stretches, and those are exactly the ones a between-frames-only report would never mention. For each reported gap where the transcript is screen-narrating (typing, demoing, walking through UI), pull explicit stills every ~20 seconds across it:
   ```
   <python> "${CLAUDE_SKILL_DIR}/extract_frames.py" <file> frames/ --stills <s1>,<s2>,<s3>
   ```
   Gaps where the speaker is just talking need nothing.
5. Read the frames in batches, each beside the transcript lines at its timestamp. Hunt: commands, config files, code, UI paths, URLs, benchmark tables, anything the speaker calls "this" or "here". Transcribe them exactly; they become the runbook.

Done when nothing in the runbook says "shown on screen" without the actual content quoted beside it.
