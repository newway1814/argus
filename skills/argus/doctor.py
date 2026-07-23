"""Read-only preflight for the Argus runtime and configured capabilities."""

import argparse
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path


MINIMUM_PYTHON = (3, 9)
DEFAULT_MODEL = "small"
SYNC_FOLDERS = {"onedrive", "dropbox", "google drive", "icloud drive"}
PLATFORM_POLICIES = {
    "macos": {
        "python": "brew install python@3.12",
        "yt-dlp": "brew install yt-dlp",
        "node": "brew install node",
        "frames": "brew install ffmpeg",
        "vault_create": 'mkdir -p "{path}"',
    },
    "linux": {
        "vault_create": 'mkdir -p "{path}"',
    },
    "windows": {
        "python": "winget install --id Python.Python.3.12 --exact",
        "yt-dlp": "winget install --id yt-dlp.yt-dlp --exact",
        "node": "winget install --id OpenJS.NodeJS.LTS --exact",
        "frames": "winget install --id Gyan.FFmpeg --exact",
        "vault_create": (
            'New-Item -ItemType Directory -Force -Path "{path}"'
        ),
    },
}
LINUX_MANAGER_POLICIES = {
    "apt-get": {
        "python": "sudo apt-get install -y python3",
        "yt-dlp": "sudo apt-get install -y yt-dlp",
        "node": "sudo apt-get install -y nodejs",
        "frames": "sudo apt-get install -y ffmpeg",
    },
    "dnf": {
        "python": "sudo dnf install -y python3",
        "yt-dlp": "sudo dnf install -y yt-dlp",
        "node": "sudo dnf install -y nodejs",
        "frames": "sudo dnf install -y ffmpeg-free",
    },
    "yum": {
        "python": "sudo yum install -y python3",
        "yt-dlp": "sudo yum install -y yt-dlp",
        "node": "sudo yum install -y nodejs",
        "frames": "sudo yum install -y ffmpeg",
    },
    "pacman": {
        "python": "sudo pacman -S --needed python",
        "yt-dlp": "sudo pacman -S --needed yt-dlp",
        "node": "sudo pacman -S --needed nodejs",
        "frames": "sudo pacman -S --needed ffmpeg",
    },
    "zypper": {
        "python": "sudo zypper install -y python3",
        "yt-dlp": "sudo zypper install -y yt-dlp",
        "node": "sudo zypper install -y nodejs",
        "frames": "sudo zypper install -y ffmpeg",
    },
    "apk": {
        "python": "sudo apk add python3",
        "yt-dlp": "sudo apk add yt-dlp",
        "node": "sudo apk add nodejs",
        "frames": "sudo apk add ffmpeg",
    },
}
LINUX_ID_MANAGERS = {
    "alpine": "apk",
    "arch": "pacman",
    "debian": "apt-get",
    "fedora": "dnf",
    "rhel": "dnf",
    "suse": "zypper",
    "ubuntu": "apt-get",
}


def platform_name(requested):
    if requested != "auto":
        return requested
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "windows"
    return "linux"


def command_parts(value, platform):
    text = str(value or "").strip()
    if not text:
        return []
    path = Path(text).expanduser()
    if path.is_absolute() and path.exists():
        return [str(path)]
    return shlex.split(text, posix=platform != "windows")


def python_probe_source(model):
    model_folder = json.dumps(
        f"models--Systran--faster-whisper-{model}"
    )
    return f"""
import importlib.util
import json
import os
import sys
from pathlib import Path

cache_root = Path(
    os.environ.get("HF_HUB_CACHE")
    or os.environ.get("HUGGINGFACE_HUB_CACHE")
    or Path.home() / ".cache" / "huggingface" / "hub"
)
try:
    importlib.import_module("faster_whisper")
    faster_whisper = True
    faster_whisper_error = ""
except Exception as error:
    faster_whisper = False
    faster_whisper_error = f"{{type(error).__name__}}: {{error}}"
model_dir = cache_root / {model_folder}
snapshots = model_dir / "snapshots"
cached = False
if snapshots.is_dir():
    for snapshot in snapshots.iterdir():
        if not snapshot.is_dir():
            continue
        files = {{path.name for path in snapshot.iterdir() if path.is_file()}}
        core = {{"model.bin", "config.json"}}
        tokenizer = {{"tokenizer.json", "vocabulary.json", "vocabulary.txt"}}
        incomplete = any(
            path.name.endswith((".incomplete", ".lock"))
            for path in model_dir.rglob("*")
        )
        core_ready = all(
            (snapshot / name).stat().st_size > 0
            for name in core
            if (snapshot / name).is_file()
        ) and core.issubset(files)
        tokenizer_ready = any(
            (snapshot / name).is_file()
            and (snapshot / name).stat().st_size > 0
            for name in tokenizer
        )
        if core_ready and tokenizer_ready and not incomplete:
            cached = True
            break
print(json.dumps({{
    "sys_executable": sys.executable,
    "version": list(sys.version_info[:3]),
    "faster_whisper": faster_whisper,
    "faster_whisper_error": faster_whisper_error,
    "model_cached": cached,
}}))
"""


def probe_python(parts, model):
    if not parts:
        return None, "python_cmd is empty"
    try:
        result = subprocess.run(
            [*parts, "-B", "-c", python_probe_source(model)],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, str(error)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "probe failed"
        return None, detail
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return None, "probe returned no readable result"
    required = {
        "sys_executable": str,
        "version": list,
        "faster_whisper": bool,
        "model_cached": bool,
    }
    if not isinstance(payload, dict) or any(
        not isinstance(payload.get(key), expected)
        for key, expected in required.items()
    ):
        return None, "probe returned an invalid result"
    if (
        len(payload["version"]) < 2
        or not all(isinstance(part, int) for part in payload["version"])
    ):
        return None, "probe returned an invalid Python version"
    resolved = Path(payload["sys_executable"]).expanduser()
    if not resolved.is_file():
        return None, f"resolved interpreter does not exist: {resolved}"
    return payload, None


def probe_command(name, version_args):
    path = shutil.which(name)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, *version_args],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    first_line = (result.stdout or result.stderr).strip().splitlines()
    return (path, first_line[0] if first_line else "version unknown")


def powershell_path():
    if os.name == "nt":
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        executable = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if executable.is_file():
            return str(executable)
    return shutil.which("powershell.exe")


def windows_acl_is_secure(path):
    executable = powershell_path()
    if not executable:
        return False
    literal_path = str(path).replace("'", "''")
    script = (
        "$current=[System.Security.Principal.WindowsIdentity]::"
        "GetCurrent().User.Value; "
        'Write-Output \"CURRENT|$current|\"; '
        f"(Get-Acl -LiteralPath '{literal_path}').Access | ForEach-Object {{ "
        "$sid=$_.IdentityReference.Translate("
        "[System.Security.Principal.SecurityIdentifier]).Value; "
        'Write-Output \"$sid|$($_.FileSystemRights)|$($_.AccessControlType)\"'
        " }"
    )
    try:
        result = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode or not result.stdout.strip():
        return False
    current_sid = None
    access_rows = []
    for row in result.stdout.splitlines():
        parts = row.strip().split("|", 2)
        if len(parts) != 3:
            continue
        sid, rights, access_type = parts
        if sid == "CURRENT":
            current_sid = rights
            continue
        access_rows.append((sid, rights, access_type))
    if not current_sid:
        return False
    allowed_sids = {
        current_sid,
        "S-1-5-18",
        "S-1-5-32-544",
    }
    for sid, rights, access_type in access_rows:
        if (
            sid not in allowed_sids
            and access_type.lower() == "allow"
            and rights not in {"", "0"}
        ):
            return False
    return True


def config_security(path, platform):
    if platform != "windows":
        secure = stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
        return secure, "permissions"
    try:
        relative = path.resolve().relative_to(Path.home().resolve())
    except ValueError:
        return False, "location"
    lowered = {part.lower() for part in relative.parts}
    if lowered.intersection(SYNC_FOLDERS):
        return False, "location"
    return windows_acl_is_secure(path), "permissions"


def vault_is_writable(path):
    if not path.is_dir():
        return False
    mode = stat.S_IMODE(path.stat().st_mode)
    return bool(mode & stat.S_IWUSR) and os.access(path, os.W_OK)


def status(ready):
    return "ready" if ready else "unavailable"


def configured_status(ready, configured):
    if ready:
        return "ready"
    return "unavailable" if configured else "not configured"


def vault_preparation_command(path, platform):
    if not path.exists():
        return PLATFORM_POLICIES[platform]["vault_create"].format(path=path)
    if platform == "windows":
        return f'icacls "{path}" /grant "%USERNAME%:(OI)(CI)M"'
    return f'chmod u+w "{path}"'


def config_preparation_command(path, platform, reason):
    if platform == "windows" and reason == "location":
        destination = "$HOME\\.claude\\argus.config.json"
        return (
            f'Move-Item -LiteralPath "{path}" -Destination "{destination}"'
        )
    if platform == "windows":
        return (
            f'icacls "{path}" /reset; '
            f'icacls "{path}" /inheritance:r; '
            f'icacls "{path}" /grant:r "${{env:USERNAME}}:F"'
        )
    return f'chmod 600 "{path}"'


def tool_preparation_command(capability, platform):
    if platform == "linux":
        manager = linux_package_manager()
        return LINUX_MANAGER_POLICIES[manager][capability]
    return PLATFORM_POLICIES[platform][capability]


def python_preparation_command(platform):
    return tool_preparation_command("python", platform)


def linux_package_manager():
    for manager in LINUX_MANAGER_POLICIES:
        if shutil.which(manager):
            return manager
    try:
        rows = Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError:
        return "apt-get"
    values = {}
    for row in rows.splitlines():
        key, separator, value = row.partition("=")
        if separator:
            values[key] = value.strip().strip('"').lower()
    identities = [
        values.get("ID", ""),
        *values.get("ID_LIKE", "").split(),
    ]
    for identity in identities:
        if identity in LINUX_ID_MANAGERS:
            return LINUX_ID_MANAGERS[identity]
    return "apt-get"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".claude" / "argus.config.json",
    )
    parser.add_argument(
        "--platform",
        choices=("auto", "macos", "linux", "windows"),
        default="auto",
        help="override operating-system command guidance",
    )
    parser.add_argument(
        "--python",
        dest="python_override",
        help="probe this candidate without writing it to config",
    )
    args = parser.parse_args()
    platform = platform_name(args.platform)
    config_path = args.config.expanduser()

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"config: unavailable ({error})")
        print("  prepare: /argus setup")
        print("overall: unhealthy")
        return 1
    if not isinstance(config, dict):
        print("config: expected a JSON object")
        print("  prepare: /argus setup")
        print("overall: unhealthy")
        return 1

    model = str(config.get("transcription_model") or DEFAULT_MODEL)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", model):
        print("config: transcription_model is invalid")
        print("  prepare: /argus setup")
        print("overall: unhealthy")
        return 1
    configured_python = str(
        args.python_override or config.get("python_cmd") or ""
    )
    python_info, python_error = probe_python(
        command_parts(configured_python, platform),
        model,
    )
    python_ready = bool(
        python_info
        and tuple(python_info.get("version", (0, 0))) >= MINIMUM_PYTHON
    )
    faster_whisper = bool(python_info and python_info.get("faster_whisper"))
    faster_whisper_error = (
        str(python_info.get("faster_whisper_error") or "")
        if python_info
        else ""
    )
    model_cached = bool(python_info and python_info.get("model_cached"))

    tools = {
        "yt-dlp": probe_command("yt-dlp", ("--version",)),
        "node": probe_command("node", ("--version",)),
        "ffmpeg": probe_command("ffmpeg", ("-version",)),
        "ffprobe": probe_command("ffprobe", ("-version",)),
    }
    config_secure, config_security_reason = config_security(
        config_path,
        platform,
    )
    vault_path = Path(str(config.get("vault_path") or "")).expanduser()
    vault_writable = vault_is_writable(vault_path)

    captions = python_ready and bool(tools["yt-dlp"])
    transcription = python_ready and faster_whisper and model_cached
    frame_tools_ready = bool(tools["ffmpeg"] and tools["ffprobe"])
    frames = python_ready and frame_tools_ready
    vault_writing = python_ready and config_secure and vault_writable
    telegram_configured = bool(config.get("telegram_token"))
    telegram_paired = bool(config.get("telegram_owner_id"))
    intake_configured = bool(config.get("playlist_url") or telegram_configured)
    telegram = bool(
        python_ready
        and config_secure
        and config.get("telegram_token")
        and config.get("telegram_owner_id")
    )
    intake_ready = bool(config.get("playlist_url") or telegram)
    queue = captions and vault_writing and intake_ready

    print("Argus doctor (read-only)")
    print(f"platform: {platform}")
    print(f"config: {config_path}")
    print(f"config permissions: {status(config_secure)}")
    if not config_secure:
        print(
            "  prepare: "
            f"{config_preparation_command(config_path, platform, config_security_reason)}"
        )
    print("Python")
    print(f"  configured: {configured_python or 'missing'}")
    if python_info:
        version = ".".join(str(part) for part in python_info["version"])
        print(f"  resolved: {python_info['sys_executable']}")
        print(f"  version: {version}")
        if tuple(python_info["version"]) < MINIMUM_PYTHON:
            print(f"    prepare: {python_preparation_command(platform)}")
        print(f"  faster-whisper: {status(faster_whisper)}")
        if not faster_whisper:
            if faster_whisper_error:
                print(f"    import error: {faster_whisper_error}")
            print(
                f'    prepare: "{python_info["sys_executable"]}" '
                "-m pip install faster-whisper"
            )
        print(f"  model {model} cache: {status(model_cached)}")
        if faster_whisper and not model_cached:
            prefetch = Path(__file__).with_name("transcribe_audio.py")
            print(
                f'    prepare: "{python_info["sys_executable"]}" '
                f'"{prefetch}" --prefetch'
            )
    else:
        print("  resolved: unavailable")
        print(f"  error: {python_error}")
        print("    prepare: /argus setup")
    print("Tools")
    for name, result in tools.items():
        if result:
            print(f"  {name}: ready ({result[1]})")
        else:
            print(f"  {name}: unavailable")
            if name == "yt-dlp":
                if python_info:
                    resolved = python_info["sys_executable"]
                    command = (
                        f'"{resolved}" -m pip install --upgrade yt-dlp'
                    )
                else:
                    command = tool_preparation_command("yt-dlp", platform)
                print(f"    prepare: {command}")
            if name == "node":
                command = tool_preparation_command("node", platform)
                print(f"    prepare: {command}")
    if not frame_tools_ready:
        command = tool_preparation_command("frames", platform)
        print(f"  frame tools prepare: {command}")
    print(f"vault: {vault_path}")
    print(
        "  permission check: "
        f"{'allows writing' if vault_writable else 'unavailable'}"
    )
    if not vault_writable:
        print(f"  prepare: {vault_preparation_command(vault_path, platform)}")
    print("Capabilities")
    print(f"  captions: {status(captions)}")
    print(f"  transcription: {status(transcription)}")
    print(f"  frames: {status(frames)}")
    print(f"  vault writing: {status(vault_writing)}")
    print(f"  queue: {configured_status(queue, intake_configured)}")
    print(
        "  Telegram: "
        f"{configured_status(telegram, telegram_configured)}"
    )
    if telegram_configured and not telegram_paired:
        print("    prepare: /argus setup telegram")
    if python_ready and not transcription:
        print(
            "limitation: captioned videos work; reels and captionless videos "
            "need the transcription preparation above"
        )

    required_healthy = python_ready and bool(tools["yt-dlp"]) and vault_writing
    print(f"overall: {'healthy' if required_healthy else 'unhealthy'}")
    return 0 if required_healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
