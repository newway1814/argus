import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACT_FRAMES = ROOT / "skills" / "argus" / "extract_frames.py"


class ExtractFramesCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.out = self.root / "frames"
        self.video = self.root / "unreadable.mp4"
        self.bin.mkdir()
        self.video.write_bytes(b"not real video data")

    def executable(self, name, body):
        if os.name == "nt":
            path = self.bin / f"{name}.cmd"
            path.write_text(f"@echo off\r\n{body}\r\n", encoding="utf-8")
        else:
            path = self.bin / name
            path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
            path.chmod(0o755)
        return path

    def python_executable(self, name, source):
        implementation = self.bin / f"{name}_implementation.py"
        implementation.write_text(source, encoding="utf-8")
        if os.name == "nt":
            body = (
                subprocess.list2cmdline([sys.executable, str(implementation)])
                + " %*"
            )
        else:
            body = (
                f"exec {shlex.quote(sys.executable)} "
                f"{shlex.quote(str(implementation))} \"$@\""
            )
        return self.executable(name, body)

    def run_extract_frames(self):
        env = os.environ.copy()
        env["PATH"] = str(self.bin)
        return subprocess.run(
            [
                sys.executable,
                str(EXTRACT_FRAMES),
                str(self.video),
                str(self.out),
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_failed_without_frames(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("kept ", result.stdout)
        valid_frames = [
            frame
            for frame in self.out.glob("frame_*.jpg")
            if frame.stat().st_size > 0
        ]
        self.assertEqual(valid_frames, [])

    def test_successful_ffmpeg_without_a_frame_is_reported_as_failure(self):
        self.executable("ffprobe", "echo 120")
        self.executable("ffmpeg", "exit /b 0" if os.name == "nt" else "exit 0")

        result = self.run_extract_frames()

        self.assert_failed_without_frames(result)
        self.assertIn("ffmpeg wrote no frame", result.stderr)

    def test_zero_byte_frame_is_reported_as_failure(self):
        self.executable("ffprobe", "echo 120")
        self.python_executable(
            "ffmpeg",
            "import sys\n"
            "from pathlib import Path\n"
            "destination = Path(sys.argv[-1])\n"
            "if destination.suffix.lower() == '.jpg':\n"
            "    destination.touch()\n",
        )

        result = self.run_extract_frames()

        self.assert_failed_without_frames(result)
        self.assertIn("ffmpeg wrote no frame", result.stderr)
        zero_byte_frames = list(self.out.glob("frame_*.jpg"))
        self.assertNotEqual(zero_byte_frames, [])
        self.assertTrue(all(frame.stat().st_size == 0 for frame in zero_byte_frames))

    def test_nonzero_ffprobe_exit_is_reported_as_failure(self):
        if os.name == "nt":
            ffprobe_body = "echo 120\r\nexit /b 7"
        else:
            ffprobe_body = "echo 120\nexit 7"
        self.executable("ffprobe", ffprobe_body)

        result = self.run_extract_frames()

        self.assert_failed_without_frames(result)
        self.assertIn("ffprobe failed (exit 7)", result.stderr)

    def test_nonzero_ffmpeg_exit_is_reported_as_failure(self):
        self.executable("ffprobe", "echo 120")
        self.executable("ffmpeg", "exit /b 9" if os.name == "nt" else "exit 9")

        result = self.run_extract_frames()

        self.assert_failed_without_frames(result)
        self.assertIn("ffmpeg failed (exit 9)", result.stderr)


if __name__ == "__main__":
    unittest.main()
