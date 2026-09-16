import json
from pathlib import Path
import subprocess
import sys


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-S", "-m", "poseidon_system_collector.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_cli_json(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    result = run_cli("--json", "--disk-path", str(tmp_path), cwd=project_root)
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["disk"]["path"] == str(tmp_path.resolve())
    assert "collected_at_utc" in payload


def test_cli_text(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    result = run_cli("--disk-path", str(tmp_path), cwd=project_root)
    assert result.returncode == 0
    assert "POSEIDON SYSTEM COLLECTOR" in result.stdout
    assert f"Filesystem path: {tmp_path.resolve()}" in result.stdout


def test_cli_invalid_disk_path(tmp_path):
    missing = tmp_path / "missing"
    project_root = Path(__file__).resolve().parents[1]
    result = run_cli("--disk-path", str(missing), cwd=project_root)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "--disk-path: invalid directory" in result.stderr
    assert "Traceback" not in result.stderr


def test_output_file_is_private_and_exclusive(tmp_path):
    destination = tmp_path / "report.json"
    project_root = Path(__file__).resolve().parents[1]
    result = run_cli(
        "--json",
        "--disk-path",
        str(tmp_path),
        "--output",
        str(destination),
        cwd=project_root,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert destination.exists()
    assert destination.stat().st_mode & 0o777 == 0o600

    second = run_cli(
        "--json",
        "--disk-path",
        str(tmp_path),
        "--output",
        str(destination),
        cwd=project_root,
    )
    assert second.returncode == 1
    assert "cannot save report" in second.stderr
