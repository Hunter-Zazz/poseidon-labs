"""Read local system information without changing system state."""

from datetime import datetime, timezone
import math
import os
from pathlib import Path
import platform
import shutil


def _optional(read):
    """Keep an unavailable source from preventing the rest of collection."""
    try:
        return read() or None
    except (OSError, ValueError):
        return None


def _memory(path: Path) -> dict:
    result = {"total_bytes": None, "available_bytes": None}
    fields = {"MemTotal": "total_bytes", "MemAvailable": "available_bytes"}
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeError):
        return result
    for line in lines:
        name, separator, value = line.partition(":")
        if not separator or name not in fields:
            continue
        parts = value.split()
        try:
            if len(parts) == 2 and parts[1] == "kB":
                amount = int(parts[0])
                if amount >= 0:
                    result[fields[name]] = amount * 1024
        except ValueError:
            continue
    return result


def _uptime(path: Path):
    try:
        seconds = float(path.read_text().split()[0])
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
    except (OSError, ValueError, IndexError):
        return None


def collect_system_info(project_path=None, proc_root=Path("/proc")) -> dict:
    """Return JSON-ready measurements; byte counts are bytes, uptime is seconds.

    Paths can be supplied for testing. Missing measurements are None.
    When project_path is omitted, the current working directory is measured.
    """
    project_path = Path.cwd() if project_path is None else Path(project_path).resolve()
    proc_root = Path(proc_root)
    os_name = _optional(lambda: platform.freedesktop_os_release().get("PRETTY_NAME"))
    disk = _optional(lambda: shutil.disk_usage(project_path))
    return {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "os": os_name or _optional(platform.system),
        "kernel": _optional(platform.release),
        "python_version": _optional(platform.python_version),
        "cpu": {
            "architecture": _optional(platform.machine),
            "logical_count": _optional(os.cpu_count),
        },
        "memory": _memory(proc_root / "meminfo"),
        "disk": {
            "path": str(project_path),
            "total_bytes": disk.total if disk else None,
            "used_bytes": disk.used if disk else None,
            "free_bytes": disk.free if disk else None,
        },
        "uptime_seconds": _uptime(proc_root / "uptime"),
    }
