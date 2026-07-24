import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTE_WRITER = ROOT / "skills" / "argus" / "note_writer.py"
sys.path.insert(0, str(NOTE_WRITER.parent))
from telegram import harvest  # noqa: E402


class YouTubeIdentityCliTests(unittest.TestCase):
    def identity(self, url):
        return subprocess.run(
            [sys.executable, str(NOTE_WRITER), "--identity", url],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_supported_urls_share_one_identity(self):
        cases = [
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
            ("https://www.youtube.com/watch?list=PL123&v=dQw4w9WgXcQ", "youtube"),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&si=abc#details", "youtube"),
            ("https://youtu.be/dQw4w9WgXcQ?si=abc#details", "youtube"),
            ("https://youtube.com/shorts/dQw4w9WgXcQ?feature=share", "youtube-shorts"),
            ("https://www.youtube.com/live/dQw4w9WgXcQ?si=abc", "youtube"),
            ("https://youtube.com/embed/dQw4w9WgXcQ?start=30", "youtube"),
        ]
        for url, source in cases:
            with self.subTest(url=url):
                result = self.identity(url)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("identity: youtube:dQw4w9WgXcQ", result.stdout)
                self.assertIn(f"source: {source}", result.stdout)
                self.assertIn(
                    "link: https://youtu.be/dQw4w9WgXcQ?t={seconds}",
                    result.stdout,
                )

    def test_malformed_youtube_urls_are_rejected(self):
        cases = [
            "https://youtube.com/watch",
            "https://youtube.com/watch?v=",
            "https://youtube.com/watch?v=short",
            "https://youtube.com/watch?v=dQw4w9WgXcQ!",
            "https://youtu.be/",
            "https://youtube.com/shorts/",
            "https://youtube.com/live/not-valid",
            "https://youtube.com/embed/dQw4w9WgXcQ/extra",
            "https://youtube.com/@creator",
        ]
        for url in cases:
            with self.subTest(url=url):
                result = self.identity(url)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid YouTube video URL", result.stderr)
                self.assertNotIn("identity:", result.stdout)

    def test_telegram_skips_malformed_youtube_urls_without_losing_valid_ones(self):
        updates = [
            {
                "update_id": 8,
                "message": {
                    "from": {"id": 4},
                    "date": 123,
                    "text": (
                        "https://youtube.com/watch?v=short "
                        "https://youtu.be/dQw4w9WgXcQ"
                    ),
                },
            }
        ]

        records, high = harvest(
            {"telegram_offset": 0, "telegram_owner_id": 4},
            updates,
        )

        self.assertEqual(high, 8)
        self.assertEqual([record["identity"] for record in records], [
            "youtube:dQw4w9WgXcQ"
        ])


if __name__ == "__main__":
    unittest.main()
