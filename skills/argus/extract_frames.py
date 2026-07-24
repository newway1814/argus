"""Scene-frame extraction: one scan, then exact grabs.

Pass 1 decodes the video once to `-f null` and records every scene-change
candidate with its change score — no images written, so a dense screencast can
no longer bury the scratchpad in tens of thousands of throwaway JPEGs. Selection
happens in post: bursts (frames within 1s of the burst's own start) collapse to
their last frame, then the highest-scoring frames are kept within the budget.
Pass 2 grabs only the survivors, each seeked by timestamp — so a frame's name is
derived from the same number that produced it and cannot drift out of step with
the transcript. Videos with no usable scene changes (live typing, gradual
screens) fall back to even sampling.

Filenames carry their own timestamp (frame_14m22s.jpg), Windows-safe.

Every ffmpeg call is checked and every expected file is verified: this script
either produces the frames it reports or exits non-zero. Silent partial output
would become silently wrong evidence in the note.

Ends by reporting gaps over 60s — including the head gap before the first kept
frame and the tail gap after the last — for transcript-aware still-filling.

Usage:
  extract_frames.py <video> <out_dir> [--start SEC] [--end SEC] [--max 80] [--min 6] [--clean]
  extract_frames.py <video> <out_dir> --start 240 --end 480 --stills 250,270,290
"""
import argparse
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FLOOR = 0.04          # candidate threshold; real selection happens by score
BURST_WINDOW = 1.0    # frames within this of a burst's start are one moment; keep the last
GAP_REPORT = 60       # report gaps longer than this (seconds)
FALLBACK_SPACING = 30 # even-sampling fallback: one frame per this many seconds
FALLBACK_MIN, FALLBACK_CAP = 8, 40


class ExtractError(Exception):
    """Anything that would otherwise leave the caller with partial evidence."""


def run(cmd, cwd=None):
    executable = shutil.which(cmd[0])
    if not executable:
        raise ExtractError(
            f"{cmd[0]} is not on PATH. Install ffmpeg "
            "(winget install Gyan.FFmpeg / brew install ffmpeg / apt install ffmpeg), "
            "or write the note transcript-only with frames: no")
    resolved = [executable, *cmd[1:]]
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        command_line = subprocess.list2cmdline(resolved)
        resolved = [
            os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
            "/d",
            "/s",
            "/c",
            command_line,
        ]
    try:
        p = subprocess.run(resolved, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=cwd)
    except FileNotFoundError:
        raise ExtractError(
            f"{cmd[0]} is not on PATH. Install ffmpeg "
            "(winget install Gyan.FFmpeg / brew install ffmpeg / apt install ffmpeg), "
            "or write the note transcript-only with frames: no")
    if p.returncode != 0:
        tail = " | ".join(p.stderr.strip().splitlines()[-3:]) or "no stderr"
        raise ExtractError(f"{cmd[0]} failed (exit {p.returncode}): {tail}")
    return p


def duration_of(video):
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)])
    try:
        secs = float(p.stdout.strip())
    except ValueError:
        raise ExtractError(f"ffprobe reported no duration for {video.name} — "
                           "the download is probably truncated; refetch it")
    if not math.isfinite(secs) or secs <= 0:
        raise ExtractError(f"{video.name} reports a duration of {secs}s — refetch it")
    return secs


def timestamp_origin_of(video):
    p = run([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=start_time",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video),
    ])
    raw = p.stdout.strip()
    if not raw or raw == "N/A":
        return 0.0
    try:
        origin = float(raw)
    except ValueError:
        raise ExtractError(
            f"ffprobe reported an invalid timestamp origin for {video.name}"
        )
    if not math.isfinite(origin):
        raise ExtractError(
            f"ffprobe reported an invalid timestamp origin for {video.name}"
        )
    return origin


def name_for(secs):
    whole = int(secs)
    millis = round((secs - whole) * 1000)
    if millis == 1000:
        whole += 1
        millis = 0
    suffix = f".{millis:03d}" if millis else ""
    return f"frame_{whole // 60}m{whole % 60:02d}{suffix}s.jpg"


def fmt(secs):
    return f"{int(secs) // 60}:{int(secs) % 60:02d}"


def grab(video, secs, out_dir, duration):
    """Seek to secs and write exactly one frame, or raise."""
    if secs > duration:
        raise ExtractError(f"asked for a still at {fmt(secs)} but {video.name} "
                           f"is only {fmt(duration)} long")
    dest = out_dir / name_for(secs)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", f"{secs:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(dest)])
    if not dest.is_file() or dest.stat().st_size == 0:
        raise ExtractError(f"ffmpeg wrote no frame at {fmt(secs)} of {video.name}")
    return dest


def candidates(video, tmp, start, end, timestamp_origin):
    """One decode, metadata only: every frame past FLOOR, with pts_time and score."""
    # cwd=tmp keeps the filtergraph's file= free of drive-letter colons (Windows).
    meta = tmp / "scores.txt"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-copyts",
         "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
         "-i", str(video.resolve()), "-an",
         "-vf", f"select='gt(scene,{FLOOR})',"
         "metadata=print:file=scores.txt",
         "-f", "null", "-"], cwd=tmp)
    if not meta.exists():
        return []
    out, pts = [], None
    for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"frame:\d+\s+pts:\S+\s+pts_time:([\d.]+)", line)
        if m:
            pts = float(m.group(1)) - timestamp_origin
            continue
        m = re.search(r"lavfi\.scene_score=([\d.]+)", line)
        if m and pts is not None:
            out.append((pts, float(m.group(1))))
            pts = None
    return out


def select_frames(cands, budget):
    """Collapse bursts to their last frame (max score), then top-N by score.

    A burst is measured from its own first frame, never from the running last
    one: candidates spaced just under BURST_WINDOW apart — live typing, a slowly
    filling screen — would otherwise chain end to end and collapse minutes of
    distinct screens into a single frame.
    """
    bursts, cur = [], []
    for i, (t, score) in enumerate(cands):
        if cur and t - cands[cur[0]][0] >= BURST_WINDOW:
            bursts.append(cur)
            cur = []
        cur.append(i)
    if cur:
        bursts.append(cur)
    picked = [(b[-1], max(cands[i][1] for i in b)) for b in bursts]
    if len(picked) > budget:
        picked = sorted(picked, key=lambda p: p[1], reverse=True)[:budget]
    times, seen = [], set()
    for i in sorted(i for i, _ in picked):
        # Two survivors inside one second would collide on filename and one
        # would silently overwrite the other.
        if int(cands[i][0]) not in seen:
            seen.add(int(cands[i][0]))
            times.append(cands[i][0])
    return times


def report_gaps(kept, start, end):
    edges = [start] + sorted(kept) + [end]
    for a, b in zip(edges, edges[1:]):
        if b - a > GAP_REPORT:
            print(f"gap {fmt(a)} -> {fmt(b)} ({int(b - a)}s)")


def window_bounds(start, end, duration):
    start = 0.0 if start is None else start
    end = duration if end is None else end
    if not math.isfinite(start) or not math.isfinite(end):
        raise ExtractError("window start and end must be finite numbers")
    if start < 0:
        raise ExtractError(f"window start must be nonnegative, got {start}")
    if end <= start:
        raise ExtractError(f"window end must be greater than start, got {start} -> {end}")
    if end > duration:
        raise ExtractError(
            f"window end {fmt(end)} exceeds {fmt(duration)} source duration")
    return start, end


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out_dir")
    ap.add_argument("--max", type=int, default=80, dest="budget")
    ap.add_argument("--min", type=int, default=6, dest="floor_count")
    ap.add_argument("--start", type=float, help="absolute source second where processing begins")
    ap.add_argument("--end", type=float, help="absolute source second where processing stops")
    ap.add_argument("--stills", help="comma-separated seconds; grab those frames and exit")
    ap.add_argument("--clean", action="store_true",
                    help="delete frames already in out_dir instead of refusing")
    args = ap.parse_args()

    video, out_dir = Path(args.video), Path(args.out_dir)
    if not video.is_file():
        raise ExtractError(f"not found: {video}")
    duration = duration_of(video)
    timestamp_origin = timestamp_origin_of(video)
    start, end = window_bounds(args.start, args.end, duration)

    # --stills fills gaps in an existing set, so it appends by design.
    if args.stills:
        wanted = [float(s) for s in args.stills.split(",") if s.strip()]
        if not all(math.isfinite(secs) for secs in wanted):
            raise ExtractError("still timestamps must be finite numbers")
        outside = [secs for secs in wanted if not start <= secs < end]
        if outside:
            raise ExtractError(
                f"stills must stay inside {fmt(start)} -> {fmt(end)}; "
                f"outside: {', '.join(fmt(secs) for secs in outside)}")
        out_dir.mkdir(parents=True, exist_ok=True)
        for s in wanted:
            grab(video, s, out_dir, duration)
        print(f"stills: {len(wanted)} written to {out_dir}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    stale = sorted(out_dir.glob("frame_*.jpg"))
    if stale and not args.clean:
        raise ExtractError(
            f"{out_dir} already holds {len(stale)} frames from an earlier run. "
            "Reading them beside this video's transcript would quote another "
            "video's screen. Use a fresh per-item directory, or pass --clean")
    for old in stale:
        old.unlink()

    tmp = out_dir / ".candidates"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        cands = candidates(video, tmp, start, end, timestamp_origin)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    kept = select_frames(cands, args.budget)
    if len(kept) >= args.floor_count:
        mode = "scene-scored"
    else:
        window_duration = end - start
        n = max(
            FALLBACK_MIN,
            min(FALLBACK_CAP, int(window_duration // FALLBACK_SPACING) or FALLBACK_MIN),
        )
        kept = [start + window_duration * j / n for j in range(n)]
        mode = (
            f"even-spaced fallback "
            f"(~1 per {int(window_duration / max(len(kept), 1))}s)"
        )

    for secs in kept:
        grab(video, secs, out_dir, duration)

    print(
        f"kept {len(kept)} frames ({mode}) in "
        f"{fmt(start)} -> {fmt(end)} of {fmt(duration)} -> {out_dir}"
    )
    report_gaps(kept, start, end)


if __name__ == "__main__":
    try:
        main()
    except ExtractError as e:
        sys.exit(f"extract_frames: {e}")
