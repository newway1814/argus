# Frame pass

Goal: read what the transcript only points at. Every frame is read beside the words spoken at its timestamp — frame + speech = what is actually happening.

1. Download video-only, 720p (code must be legible), sponsor segments cut, into the scratchpad:
   ```
   yt-dlp --js-runtimes node --sponsorblock-remove sponsor -f "bestvideo[height<=720]" -o "%(id)s.%(ext)s" <url>
   ```
2. Extract the frames — one command, one decode:
   ```
   python "<this skill's folder>/extract_frames.py" <file> frames/
   ```
   The script collects every scene-change candidate with its change score in a single pass, collapses bursts (frames under 1s apart are one moment — a transition animation), keeps the highest-scoring frames within an 80-frame budget, and falls back to even sampling (~1 per 30s) when scene detection finds nothing usable (live typing and gradual screens dodge it). No thresholds to tune, no reruns. Each filename is its own timestamp: `frame_14m22s.jpg` sits at 14:22.
3. **Fill the blind spots — the script reports, you judge.** The script ends by listing every gap over 60 seconds between kept frames. For each reported gap where the transcript is screen-narrating (typing, demoing, walking through UI), pull explicit stills every ~20 seconds across it:
   ```
   python "<this skill's folder>/extract_frames.py" <file> frames/ --stills <s1>,<s2>,<s3>
   ```
   Gaps where the speaker is just talking need nothing.
4. Read the frames in batches, each beside the transcript lines at its timestamp. Hunt: commands, config files, code, UI paths, URLs, benchmark tables — anything the speaker calls "this" or "here". Transcribe them exactly; they become the runbook.

Done when nothing in the runbook says "shown on screen" without the actual content quoted beside it.
