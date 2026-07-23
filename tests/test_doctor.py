import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "skills" / "argus" / "doctor.py"


class DoctorCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.vault = self.root / "vault"
        self.home.mkdir()
        self.bin.mkdir()
        self.vault.mkdir()
        self.config = self.home / ".claude" / "argus.config.json"
        self.config.parent.mkdir()

    def executable(self, name, output):
        path = self.bin / name
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def python_executable(
        self,
        *,
        version=(3, 12, 2),
        faster_whisper=True,
        model_cached=True,
        resolved=None,
    ):
        path = self.bin / "argus-python"
        payload = json.dumps(
            {
                "sys_executable": str(resolved or path),
                "version": list(version),
                "faster_whisper": faster_whisper,
                "model_cached": model_cached,
            }
        )
        path.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--version\" ]; then\n"
            f"  printf '%s\\n' 'Python {version[0]}.{version[1]}.{version[2]}'\n"
            "else\n"
            f"  printf '%s\\n' '{payload}'\n"
            "fi\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def write_config(self, python_cmd):
        self.config.write_text(
            json.dumps(
                {
                    "vault_path": str(self.vault),
                    "python_cmd": str(python_cmd),
                    "playlist_url": "https://youtube.com/playlist?list=test",
                    "telegram_token": "test-token",
                    "telegram_owner_id": 123,
                    "transcription_model": "small",
                }
            ),
            encoding="utf-8",
        )
        self.config.chmod(0o600)

    def run_doctor(self, platform="macos", config=None):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["PATH"] = str(self.bin)
        config = config or self.config
        return subprocess.run(
            [
                sys.executable,
                str(DOCTOR),
                "--config",
                str(config),
                "--platform",
                platform,
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_healthy_environment_reports_every_capability(self):
        python = self.python_executable()
        self.write_config(python)
        self.executable("yt-dlp", "2026.07.01")
        self.executable("node", "v24.0.0")
        self.executable("ffmpeg", "ffmpeg version 8.0")
        self.executable("ffprobe", "ffprobe version 8.0")

        for platform in ("macos", "linux", "windows"):
            with self.subTest(platform=platform):
                result = self.run_doctor(platform)

                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout + result.stderr,
                )
                self.assertIn(f"configured: {python}", result.stdout)
                self.assertIn(f"resolved: {python}", result.stdout)
                self.assertIn("captions: ready", result.stdout)
                self.assertIn("transcription: ready", result.stdout)
                self.assertIn("frames: ready", result.stdout)
                self.assertIn("vault writing: ready", result.stdout)
                self.assertIn("queue: ready", result.stdout)
                self.assertIn("Telegram: ready", result.stdout)
                self.assertIn("overall: healthy", result.stdout)

    def test_missing_required_command_fails_with_one_preparation_command_per_os(self):
        python = self.python_executable()
        self.write_config(python)
        self.executable("node", "v24.0.0")
        self.executable("ffmpeg", "ffmpeg version 8.0")
        self.executable("ffprobe", "ffprobe version 8.0")

        for platform in ("macos", "linux", "windows"):
            with self.subTest(platform=platform):
                result = self.run_doctor(platform)

                self.assertNotEqual(result.returncode, 0)
                command = f'"{python}" -m pip install --upgrade yt-dlp'
                self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)
                self.assertIn("captions: unavailable", result.stdout)
                self.assertIn("overall: unhealthy", result.stdout)

    def test_wrong_interpreter_does_not_borrow_dependencies_from_doctor_runtime(self):
        resolved = self.root / "other-environment" / "python"
        python = self.python_executable(
            faster_whisper=False,
            model_cached=False,
            resolved=resolved,
        )
        self.write_config(python)
        self.executable("yt-dlp", "2026.07.01")
        self.executable("node", "v24.0.0")
        self.executable("ffmpeg", "ffmpeg version 8.0")
        self.executable("ffprobe", "ffprobe version 8.0")

        for platform in ("macos", "linux", "windows"):
            with self.subTest(platform=platform):
                result = self.run_doctor(platform)

                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout + result.stderr,
                )
                self.assertIn(f"configured: {python}", result.stdout)
                self.assertIn(f"resolved: {resolved}", result.stdout)
                self.assertIn("faster-whisper: unavailable", result.stdout)
                self.assertIn("transcription: unavailable", result.stdout)
                command = f'"{resolved}" -m pip install faster-whisper'
                self.assertEqual(
                    result.stdout.count(f"prepare: {command}"),
                    1,
                )

    def test_unwritable_vault_fails_with_os_specific_preparation_command(self):
        python = self.python_executable()
        self.write_config(python)
        self.executable("yt-dlp", "2026.07.01")
        self.executable("node", "v24.0.0")
        self.executable("ffmpeg", "ffmpeg version 8.0")
        self.executable("ffprobe", "ffprobe version 8.0")
        self.vault.chmod(0o500)
        self.addCleanup(self.vault.chmod, 0o700)
        expected = {
            "macos": f'chmod u+w "{self.vault}"',
            "linux": f'chmod u+w "{self.vault}"',
            "windows": (
                f'icacls "{self.vault}" /grant "%USERNAME%:(OI)(CI)M"'
            ),
        }

        for platform, command in expected.items():
            with self.subTest(platform=platform):
                result = self.run_doctor(platform)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("vault writing: unavailable", result.stdout)
                self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)
                self.assertIn("overall: unhealthy", result.stdout)

    def test_insecure_config_fails_with_os_specific_preparation_command(self):
        python = self.python_executable()
        self.write_config(python)
        self.executable("yt-dlp", "2026.07.01")
        self.executable("node", "v24.0.0")
        self.executable("ffmpeg", "ffmpeg version 8.0")
        self.executable("ffprobe", "ffprobe version 8.0")

        self.config.chmod(0o644)
        for platform in ("macos", "linux"):
            with self.subTest(platform=platform):
                result = self.run_doctor(platform)
                command = f'chmod 600 "{self.config}"'

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("config permissions: unavailable", result.stdout)
                self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)

        outside = self.root / "argus.config.json"
        outside.write_bytes(self.config.read_bytes())
        outside.chmod(0o600)
        result = self.run_doctor("windows", outside)
        destination = "$HOME\\.claude\\argus.config.json"
        command = (
            f'Move-Item -LiteralPath "{outside}" -Destination "{destination}"'
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config permissions: unavailable", result.stdout)
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)

    def test_optional_failures_print_commands_without_running_or_writing_them(self):
        python = self.python_executable(
            faster_whisper=False,
            model_cached=False,
        )
        self.write_config(python)
        self.executable("yt-dlp", "2026.07.01")
        package_manager_marker = self.root / "package-manager-ran"
        brew = self.bin / "brew"
        brew.write_text(
            "#!/bin/sh\n"
            f'touch "{package_manager_marker}"\n'
            "exit 99\n",
            encoding="utf-8",
        )
        brew.chmod(0o755)
        before = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mode)
            for path in self.root.rglob("*")
            if path.is_file()
        }

        result = self.run_doctor("macos")

        after = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mode)
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, after)
        self.assertFalse(package_manager_marker.exists())
        self.assertEqual(
            result.stdout.count("prepare: brew install node"),
            1,
        )
        self.assertEqual(
            result.stdout.count("prepare: brew install ffmpeg"),
            1,
        )
        self.assertEqual(
            result.stdout.count(
                f'prepare: "{python}" -m pip install faster-whisper'
            ),
            1,
        )

    def test_uncached_model_reports_explicit_prefetch_without_downloading(self):
        python = self.python_executable(model_cached=False)
        self.write_config(python)
        self.executable("yt-dlp", "2026.07.01")
        self.executable("node", "v24.0.0")
        self.executable("ffmpeg", "ffmpeg version 8.0")
        self.executable("ffprobe", "ffprobe version 8.0")

        result = self.run_doctor()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("model small cache: unavailable", result.stdout)
        self.assertIn("transcription: unavailable", result.stdout)
        prefetch = DOCTOR.with_name("transcribe_audio.py")
        command = f'"{python}" "{prefetch}" --prefetch'
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)

    def test_unsupported_python_version_is_a_required_failure(self):
        python = self.python_executable(version=(3, 8, 19))
        self.write_config(python)
        self.executable("yt-dlp", "2026.07.01")
        self.executable("node", "v24.0.0")
        self.executable("ffmpeg", "ffmpeg version 8.0")
        self.executable("ffprobe", "ffprobe version 8.0")
        expected = {
            "macos": "brew install python@3.12",
            "linux": "sudo apt-get install -y python3",
            "windows": "winget install --id Python.Python.3.12 --exact",
        }

        for platform, command in expected.items():
            with self.subTest(platform=platform):
                result = self.run_doctor(platform)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("version: 3.8.19", result.stdout)
                self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)
                self.assertIn("overall: unhealthy", result.stdout)

    def test_missing_configured_python_fails_with_setup_command(self):
        missing = self.root / "missing-python"
        self.write_config(missing)
        self.executable("yt-dlp", "2026.07.01")
        self.executable("node", "v24.0.0")
        self.executable("ffmpeg", "ffmpeg version 8.0")
        self.executable("ffprobe", "ffprobe version 8.0")

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"configured: {missing}", result.stdout)
        self.assertIn("resolved: unavailable", result.stdout)
        self.assertEqual(result.stdout.count("prepare: /argus setup"), 1)
        self.assertIn("overall: unhealthy", result.stdout)

    def test_missing_config_file_fails_with_setup_command(self):
        missing = self.root / "missing-config.json"

        result = self.run_doctor(config=missing)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config: unavailable", result.stdout)
        self.assertEqual(result.stdout.count("prepare: /argus setup"), 1)
        self.assertIn("overall: unhealthy", result.stdout)

    def test_model_name_from_config_cannot_execute_python(self):
        marker = self.root / "model-name-executed"
        malicious_model = (
            'small"\n'
            f'Path(r"{marker}").write_text("bad")\n'
            "#"
        )
        self.config.write_text(
            json.dumps(
                {
                    "vault_path": str(self.vault),
                    "python_cmd": sys.executable,
                    "playlist_url": "https://youtube.com/playlist?list=test",
                    "telegram_token": "",
                    "telegram_owner_id": None,
                    "transcription_model": malicious_model,
                }
            ),
            encoding="utf-8",
        )
        self.config.chmod(0o600)
        self.executable("yt-dlp", "2026.07.01")

        self.run_doctor()

        self.assertFalse(marker.exists())

    def test_non_object_config_reports_failure_instead_of_crashing(self):
        self.config.write_text("[]", encoding="utf-8")
        self.config.chmod(0o600)

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("config: expected a JSON object", result.stdout)
        self.assertEqual(result.stdout.count("prepare: /argus setup"), 1)


if __name__ == "__main__":
    unittest.main()
