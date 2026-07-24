import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACT_FRAMES = ROOT / "skills" / "argus" / "extract_frames.py"
CLEAN_TRANSCRIPT = ROOT / "skills" / "argus" / "clean_transcript.py"
TRANSCRIBE_AUDIO = ROOT / "skills" / "argus" / "transcribe_audio.py"


class PipelineFailureCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def executable(self, name, output):
        path = self.root / (f"{name}.cmd" if os.name == "nt" else name)
        if os.name == "nt":
            path.write_text(f"@echo off\r\necho {output}\r\n", encoding="utf-8")
        else:
            path.write_text(
                f"#!/bin/sh\nprintf '%s\\n' '{output}'\n",
                encoding="utf-8",
            )
            path.chmod(0o755)
        return path

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe is required")
    def test_invalid_media_fails_without_output_files(self):
        media = self.root / "invalid.mp4"
        media.write_bytes(b"not media")
        output = self.root / "frames"

        result = subprocess.run(
            [
                sys.executable,
                str(EXTRACT_FRAMES),
                str(media),
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("kept ", result.stdout)
        self.assertEqual(list(output.glob("frame_*.jpg")), [])

    def test_missing_ffmpeg_fails_without_counting_frames(self):
        media = self.root / "video.mp4"
        media.write_bytes(b"placeholder")
        output = self.root / "frames"
        self.executable("ffprobe", "120")
        env = os.environ.copy()
        env["PATH"] = str(self.root)

        result = subprocess.run(
            [
                sys.executable,
                str(EXTRACT_FRAMES),
                str(media),
                str(output),
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ffmpeg is not on PATH", result.stderr)
        self.assertNotIn("kept ", result.stdout)
        self.assertEqual(list(output.glob("frame_*.jpg")), [])

    def test_empty_caption_file_fails_without_transcript(self):
        captions = self.root / "empty.vtt"
        captions.write_text("WEBVTT\n", encoding="utf-8")
        output = self.root / "transcript.txt"

        result = subprocess.run(
            [
                sys.executable,
                str(CLEAN_TRANSCRIPT),
                str(captions),
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("parsed 0 caption lines", result.stderr)
        self.assertFalse(output.exists())

    def test_missing_python_dependency_is_an_explicit_failure(self):
        output = self.root / "transcript.txt"

        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(TRANSCRIBE_AUDIO),
                str(self.root / "audio.mp4"),
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("faster-whisper is not installed", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
