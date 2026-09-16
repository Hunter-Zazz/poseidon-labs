from datetime import datetime, timedelta
import json
from types import SimpleNamespace

import pytest

from poseidon_system_collector import collector
from poseidon_system_collector.formatting import format_system_info


def test_collection_units_sources_and_timestamp(tmp_path, monkeypatch):
    (tmp_path / "meminfo").write_text("MemTotal: 2048 kB\nMemAvailable: 1024 kB\n")
    (tmp_path / "uptime").write_text("90061.25 999999.00\n")
    monkeypatch.setattr(collector.platform, "freedesktop_os_release", lambda: {"PRETTY_NAME": "Test Linux"})
    monkeypatch.setattr(collector.platform, "release", lambda: "test-kernel")
    monkeypatch.setattr(collector.platform, "python_version", lambda: "3.test")
    monkeypatch.setattr(collector.platform, "machine", lambda: "test-arch")
    monkeypatch.setattr(collector.os, "cpu_count", lambda: 8)
    paths = []

    def disk_usage(path):
        paths.append(path)
        return SimpleNamespace(total=100, used=60, free=40)

    monkeypatch.setattr(collector.shutil, "disk_usage", disk_usage)
    before = datetime.now().astimezone()
    info = collector.collect_system_info(project_path=tmp_path, proc_root=tmp_path)
    after = datetime.now().astimezone()

    assert info["os"] == "Test Linux"
    assert info["kernel"] == "test-kernel"
    assert info["python_version"] == "3.test"
    assert info["cpu"] == {"architecture": "test-arch", "logical_count": 8}
    assert info["memory"] == {"total_bytes": 2097152, "available_bytes": 1048576}
    assert info["uptime_seconds"] == 90061.25
    assert paths == [tmp_path.resolve()]
    assert info["disk"] == {
        "path": str(tmp_path.resolve()),
        "total_bytes": 100,
        "used_bytes": 60,
        "free_bytes": 40,
    }
    timestamp = datetime.fromisoformat(info["collected_at_utc"])
    assert timestamp.utcoffset() == timedelta(0)
    assert before <= timestamp <= after
    assert "1d 1h 1m 1s" in format_system_info(info)
    assert json.loads(json.dumps(info, allow_nan=False)) == info


def test_missing_sources(tmp_path, monkeypatch):
    def unavailable(*args):
        raise OSError("source unavailable")

    monkeypatch.setattr(collector.shutil, "disk_usage", unavailable)
    monkeypatch.setattr(collector.platform, "freedesktop_os_release", unavailable)
    monkeypatch.setattr(collector.platform, "system", lambda: "Linux")
    monkeypatch.setattr(collector.platform, "release", unavailable)
    monkeypatch.setattr(collector.os, "cpu_count", lambda: None)

    info = collector.collect_system_info(project_path=tmp_path, proc_root=tmp_path)
    assert info["os"] == "Linux"
    assert info["kernel"] is None
    assert info["cpu"]["logical_count"] is None
    assert info["memory"] == {"total_bytes": None, "available_bytes": None}
    assert info["disk"]["total_bytes"] is None
    assert info["uptime_seconds"] is None
    assert "Memory available: unavailable" in format_system_info(info)
    assert "Uptime: unavailable" in format_system_info(info)


@pytest.mark.parametrize("value", ["", "invalid", "-1", "nan", "inf"])
def test_invalid_uptime(tmp_path, value):
    (tmp_path / "uptime").write_text(value)
    assert collector.collect_system_info(project_path=tmp_path, proc_root=tmp_path)["uptime_seconds"] is None


@pytest.mark.parametrize(
    "line",
    ["", "MemAvailable: invalid kB", "MemAvailable: -1 kB", "MemAvailable: 10 MB"],
)
def test_partial_memory(tmp_path, line):
    (tmp_path / "meminfo").write_text("MemTotal: 2 kB\n" + line)
    assert collector.collect_system_info(project_path=tmp_path, proc_root=tmp_path)["memory"] == {
        "total_bytes": 2048,
        "available_bytes": None,
    }


def test_zero_values_are_available(tmp_path):
    (tmp_path / "meminfo").write_text("MemTotal: 0 kB\nMemAvailable: 0 kB\n")
    (tmp_path / "uptime").write_text("0 0")
    rendered = format_system_info(
        collector.collect_system_info(project_path=tmp_path, proc_root=tmp_path)
    )
    assert "Memory available: 0.00 GiB" in rendered
    assert "Uptime: 0d 0h 0m 0s" in rendered
