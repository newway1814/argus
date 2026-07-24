import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTE_WRITER = ROOT / "skills" / "argus" / "note_writer.py"


class NoteWriterCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.meta = self.root / "meta.json"
        self.body = self.root / "body.md"
        self.body.write_text(
            "---\nuntrusted: frontmatter\n---\n\n## Runbook\n\n1. Open settings.\n",
            encoding="utf-8",
        )

    def run_writer(self, meta):
        self.meta.write_text(json.dumps(meta), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(NOTE_WRITER),
                "--vault",
                str(self.vault),
                "--meta",
                str(self.meta),
                "--body",
                str(self.body),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_note_is_serialized_to_one_real_file(self):
        result = self.run_writer(
            {
                "title": 'Setup: "fast" / safe',
                "channel": "Example",
                "url": "https://youtu.be/dQw4w9WgXcQ",
                "published": "2026-07-24",
                "processed": "2026-07-24",
                "duration": "4:12",
                "type": "tutorial",
                "tags": ["argus", "video"],
                "watch_verdict": "try",
                "frames": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        notes = list((self.vault / "videos").glob("*.md"))
        self.assertEqual(len(notes), 1)
        self.assertGreater(notes[0].stat().st_size, 0)
        self.assertEqual(list((self.vault / "videos").glob("*.tmp")), [])
        text = notes[0].read_text(encoding="utf-8")
        self.assertIn('identity: "youtube:dQw4w9WgXcQ"', text)
        self.assertIn('title: "Setup: \\"fast\\" / safe"', text)
        self.assertIn("watch-verdict: try", text)
        self.assertIn("frames: yes", text)
        self.assertIn("## Runbook", text)
        self.assertNotIn("untrusted: frontmatter", text)
        self.assertIn(f"note: {notes[0]}", result.stdout)

    def test_invalid_enum_writes_no_note(self):
        result = self.run_writer(
            {
                "url": "https://youtu.be/dQw4w9WgXcQ",
                "type": "advertisement",
                "watch_verdict": "try",
            }
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.vault / "videos").exists())


if __name__ == "__main__":
    unittest.main()
