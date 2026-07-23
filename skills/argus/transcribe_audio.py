"""Transcribe a media file with faster-whisper into `[m:ss] text` lines.

Local, no upload; reads video containers directly, so no extraction step.

Usage:
  transcribe_audio.py <media> [out.txt]
  transcribe_audio.py --prefetch      # download the model once, during setup

`--prefetch` exists because the first real call otherwise downloads ~460MB with
no output and blows a command timeout that looks like a hang.
"""
import sys
from pathlib import Path

MODEL = "small"

try:
    from faster_whisper import WhisperModel
except ImportError:
    sys.exit("transcribe_audio: faster-whisper is not installed. "
             "Prepare the Python environment recorded in argus.config.json "
             "with faster-whisper, then re-run. Argus does not install packages "
             "during a video run; the model stays local.")


def load(device="cpu"):
    return WhisperModel(MODEL, device=device, compute_type="int8")


def transcribe(media):
    """Take the GPU when it genuinely works, CPU otherwise.

    A machine with a GPU but an incomplete CUDA install loads the model happily
    and only fails at encode time with a missing cublas DLL, so the fallback has
    to wrap the transcription itself, not just the constructor.
    """
    for device in ("auto", "cpu"):
        try:
            segments, _info = load(device).transcribe(str(media), vad_filter=True)
            return list(segments)
        except (RuntimeError, OSError) as e:
            if device == "cpu":
                sys.exit(f"transcribe_audio: {e}")
            print(f"transcribe_audio: GPU path unavailable ({e}); falling back to CPU",
                  file=sys.stderr)
    return []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    if sys.argv[1] == "--prefetch":
        load()
        print(f"transcribe_audio: {MODEL} model ready")
        sys.exit(0)

    media = Path(sys.argv[1])
    if not media.is_file():
        sys.exit(f"transcribe_audio: not found: {media}")

    # vad_filter keeps whisper from looping invented text over silent stretches.
    lines = [f"[{int(s.start) // 60}:{int(s.start) % 60:02d}] {s.text.strip()}"
             for s in transcribe(media)]
    if not lines:
        sys.exit(f"transcribe_audio: no speech found in {media.name}, "
                 "treat as silent, not as a failed read")

    body = "\n".join(lines)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(body, encoding="utf-8")
        print(f"transcribe_audio: {len(lines)} lines -> {sys.argv[2]}")
    else:
        print(body)
