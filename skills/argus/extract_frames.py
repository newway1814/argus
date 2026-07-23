"""Scene-frame extraction in a single decode.

One ffmpeg pass collects every scene-change candidate with its change score;
selection happens in post: bursts (frames < 1s apart) collapse to their last
frame, then the highest-scoring frames are kept within the budget — the ideal
scene threshold, found exactly, with no re-decodes. Videos with no usable scene
changes (live typing, gradual screens) fall back to even sampling.

Filenames carry their own timestamp (frame_14m22s.jpg), Windows-safe.
Ends by reporting gaps over 60s between kept frames, for transcript-aware
still-filling by the caller.

Usage:
  extract_frames.py <video> <out_dir> [--max 80] [--min 6]
  extract_frames.py <video> <out_dir> --stills 250,270,290
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

FLOOR = 0.04          # candidate threshold; real selection happens by score
BURST_WINDOW = 1.0    # frames closer than this are one moment; keep the last
GAP_REPORT = 60       # report gaps longer than this (seconds)
FALLBACK_SPACING = 30 # even-sampling fallback: one frame per this many seconds
FALLBACK_MIN, FALLBACK_CAP = 8, 40


def run(cmd, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=cwd)


def duration_of(video):
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)])
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def name_for(secs):
    return f"frame_{int(secs) // 60}m{int(secs) % 60:02d}s.jpg"


def fmt(secs):
    return f"{int(secs) // 60}:{int(secs) % 60:02d}"


def grab_still(video, secs, out_dir):
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", str(secs), "-i", str(video), "-frames:v", "1", "-q:v", "3",
         str(out_dir / name_for(secs))])


def candidates(video, tmp):
    """One decode: every frame past FLOOR, with pts_time and scene score."""
    # cwd=tmp keeps the filtergraph's file= free of drive-letter colons (Windows).
    meta = tmp / "scores.txt"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video.resolve()),
         "-vf", f"select='gt(scene,{FLOOR})',metadata=print:file=scores.txt",
         "-fps_mode", "vfr", "-q:v", "3", "%05d.jpg"], cwd=tmp)
    if not meta.exists():
        return []
    out, pts = [], None
    for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"frame:\d+\s+pts:\S+\s+pts_time:([\d.]+)", line)
        if m:
            pts = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scene_score=([\d.]+)", line)
        if m and pts is not None:
            out.append((pts, float(m.group(1))))
            pts = None
    return out  # index i -> file tmp/%05d.jpg with i+1


def select_frames(cands, budget):
    """Collapse bursts to their last frame (max score), then top-N by score."""
    bursts, cur = [], []
    for i, (t, score) in enumerate(cands):
        if cur and t - cands[cur[-1]][0] >= BURST_WINDOW:
            bursts.append(cur)
            cur = []
        cur.append(i)
    if cur:
        bursts.append(cur)
    picked = [(b[-1], max(cands[i][1] for i in b)) for b in bursts]
    if len(picked) > budget:
        picked = sorted(picked, key=lambda p: p[1], reverse=True)[:budget]
    return sorted(i for i, _ in picked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out_dir")
    ap.add_argument("--max", type=int, default=80, dest="budget")
    ap.add_argument("--min", type=int, default=6, dest="floor_count")
    ap.add_argument("--stills", help="comma-separated seconds; grab those frames and exit")
    args = ap.parse_args()

    video, out_dir = Path(args.video), Path(args.out_dir)
    if not video.is_file():
        sys.exit(f"extract_frames: not found: {video}")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.stills:
        for s in args.stills.split(","):
            grab_still(video, int(float(s)), out_dir)
        print(f"stills: {len(args.stills.split(','))} written to {out_dir}")
        return

    tmp = out_dir / ".candidates"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    cands = candidates(video, tmp)
    kept_times = []

    if len(select_frames(cands, args.budget)) >= args.floor_count:
        for i in select_frames(cands, args.budget):
            src = tmp / f"{i + 1:05d}.jpg"
            if src.exists():
                shutil.move(str(src), str(out_dir / name_for(cands[i][0])))
                kept_times.append(cands[i][0])
        mode = "scene-scored"
    else:
        dur = duration_of(video)
        n = max(FALLBACK_MIN, min(FALLBACK_CAP, int(dur // FALLBACK_SPACING) or FALLBACK_MIN))
        for j in range(n):
            secs = int(dur * j / n)
            grab_still(video, secs, out_dir)
            kept_times.append(secs)
        mode = "even-spaced fallback"

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"kept {len(kept_times)} frames ({mode}) -> {out_dir}")
    for a, b in zip(kept_times, kept_times[1:]):
        if b - a > GAP_REPORT:
            print(f"gap {fmt(a)} -> {fmt(b)} ({int(b - a)}s)")


if __name__ == "__main__":
    main()
