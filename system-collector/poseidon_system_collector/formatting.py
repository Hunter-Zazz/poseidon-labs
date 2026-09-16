"""Turn collected values into readable text without collecting more data."""


def _display(value):
    return "unavailable" if value is None else str(value)


def _bytes(value):
    return "unavailable" if value is None else f"{value / 1024**3:.2f} GiB"


def format_system_info(info: dict) -> str:
    """Format a collector snapshot for the terminal."""
    uptime = info["uptime_seconds"]
    if uptime is None:
        duration = "unavailable"
    else:
        days, remaining = divmod(int(uptime), 86400)
        hours, remaining = divmod(remaining, 3600)
        minutes, seconds = divmod(remaining, 60)
        duration = f"{days}d {hours}h {minutes}m {seconds}s"
    return "\n".join([
        f"Collected (UTC): {_display(info['collected_at_utc'])}",
        f"OS: {_display(info['os'])}",
        f"Kernel: {_display(info['kernel'])}",
        f"Python: {_display(info['python_version'])}",
        f"CPU architecture: {_display(info['cpu']['architecture'])}",
        f"Logical CPUs: {_display(info['cpu']['logical_count'])}",
        f"Memory total: {_bytes(info['memory']['total_bytes'])}",
        f"Memory available: {_bytes(info['memory']['available_bytes'])}",
        f"Filesystem path: {info['disk']['path']}",
        f"Disk total: {_bytes(info['disk']['total_bytes'])}",
        f"Disk used: {_bytes(info['disk']['used_bytes'])}",
        f"Disk free: {_bytes(info['disk']['free_bytes'])}",
        f"Uptime: {duration}",
    ])
