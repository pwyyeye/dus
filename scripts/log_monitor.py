#!/usr/bin/env python3
"""
Backend log monitor for DUS.

Watches log files for ERROR/CRITICAL/Traceback patterns.
Only surfaces errors when the main agent appears idle (no recent file changes).
Writes notifications to .dus/log_errors.json for the Claude Code scheduled task to read.

Usage:
    python scripts/log_monitor.py [--config .dus/log_monitor.json]
"""

import json
import os
import re
import sys
import time
from pathlib import Path

DEFAULT_CONFIG = {
    "log_files": [
        ".dus/bridge-stdout.log",
        "cloud/uvicorn.log",
    ],
    "project_dir": ".",
    "idle_threshold_seconds": 30,
    "scan_interval_seconds": 10,
    "error_output": ".dus/log_errors.json",
    "error_patterns": [
        r"\bERROR\b",
        r"\bCRITICAL\b",
        r"\bTraceback\b",
        r"Exception:",
        r"\b500\b.*\berror\b",
        r"Internal Server Error",
    ],
    "ignore_patterns": [
        r"health",
        r"ping",
    ],
}

STATE_FILE = ".dus/log_monitor_state.json"


def load_config(config_path=None):
    config = DEFAULT_CONFIG.copy()
    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config.update(user_config)
    return config


def load_state(state_path):
    if Path(state_path).exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"file_positions": {}, "reported_hashes": []}


def save_state(state_path, state):
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_notifications(output_path):
    if Path(output_path).exists():
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"errors": [], "last_updated": None}


def save_notifications(output_path, data):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_last_modified_time(dirs, extensions=None):
    """Get the most recent file modification time across directories."""
    if extensions is None:
        extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml", ".json"}

    latest = 0
    for d in dirs:
        d = Path(d)
        if not d.exists():
            continue
        try:
            for f in d.rglob("*"):
                if f.is_file() and f.suffix in extensions:
                    try:
                        mt = f.stat().st_mtime
                        if mt > latest:
                            latest = mt
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            continue
    return latest


def is_agent_idle(project_dir, threshold):
    """Check if the main agent is idle by looking at recent file modifications."""
    watch_dirs = [
        os.path.join(project_dir, "cloud"),
        os.path.join(project_dir, "bridge"),
        os.path.join(project_dir, "frontend", "src"),
    ]
    last_modified = get_last_modified_time(watch_dirs)
    if last_modified == 0:
        return True
    return (time.time() - last_modified) > threshold


def hash_error(source, line_no, message):
    """Create a simple hash for deduplication."""
    return f"{source}:{line_no}:{message[:100]}"


def scan_log_file(filepath, start_pos, error_patterns, ignore_patterns):
    """Scan a log file for error patterns starting from a position."""
    errors = []
    filepath = Path(filepath)
    if not filepath.exists():
        return errors, start_pos

    try:
        size = filepath.stat().st_size
        if size < start_pos:
            # File was truncated/rotated
            start_pos = 0

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            f.seek(start_pos)
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                # Check ignore patterns first
                if any(re.search(p, line, re.IGNORECASE) for p in ignore_patterns):
                    continue

                for pattern in error_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        errors.append({
                            "source": filepath.name,
                            "line_no": start_pos + line_no,
                            "message": line[:500],
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        })
                        break

            new_pos = f.tell()
    except (OSError, PermissionError) as e:
        return errors, start_pos

    return errors, new_pos


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)

    project_dir = config["project_dir"]
    state_path = os.path.join(project_dir, STATE_FILE)
    output_path = os.path.join(project_dir, config["error_output"])
    idle_threshold = config["idle_threshold_seconds"]
    scan_interval = config["scan_interval_seconds"]

    state = load_state(state_path)
    file_positions = state.get("file_positions", {})
    reported_hashes = set(state.get("reported_hashes", []))

    print(f"[log_monitor] Watching {len(config['log_files'])} log files")
    print(f"[log_monitor] Idle threshold: {idle_threshold}s, scan interval: {scan_interval}s")
    print(f"[log_monitor] Notifications -> {output_path}")

    error_re = [re.compile(p, re.IGNORECASE) for p in config["error_patterns"]]
    ignore_re = [re.compile(p, re.IGNORECASE) for p in config["ignore_patterns"]]

    try:
        while True:
            all_new_errors = []

            for log_file in config["log_files"]:
                log_path = os.path.join(project_dir, log_file)
                pos = file_positions.get(log_file, 0)
                new_errors, new_pos = scan_log_file(
                    log_path, pos, error_re, ignore_re
                )
                file_positions[log_file] = new_pos
                all_new_errors.extend(new_errors)

            if all_new_errors:
                # Deduplicate
                unique_errors = []
                for err in all_new_errors:
                    h = hash_error(err["source"], err["line_no"], err["message"])
                    if h not in reported_hashes:
                        reported_hashes.add(h)
                        unique_errors.append(err)

                if unique_errors:
                    idle = is_agent_idle(project_dir, idle_threshold)
                    status = "idle" if idle else "coding"

                    if idle:
                        # Agent is idle — write notification
                        notifications = load_notifications(output_path)
                        notifications["errors"].extend(unique_errors)
                        notifications["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        save_notifications(output_path, notifications)
                        print(f"[log_monitor] {status} | NOTIFIED {len(unique_errors)} new error(s)")
                    else:
                        print(f"[log_monitor] {status} | suppressed {len(unique_errors)} error(s) (agent active)")

                    for err in unique_errors:
                        print(f"  [{err['source']}] {err['message'][:120]}")

            # Trim reported_hashes to prevent unbounded growth
            if len(reported_hashes) > 5000:
                reported_hashes = set(list(reported_hashes)[-2000:])

            # Save state
            state["file_positions"] = file_positions
            state["reported_hashes"] = list(reported_hashes)
            save_state(state_path, state)

            time.sleep(scan_interval)

    except KeyboardInterrupt:
        print("\n[log_monitor] Stopped")
        state["file_positions"] = file_positions
        state["reported_hashes"] = list(reported_hashes)
        save_state(state_path, state)


if __name__ == "__main__":
    main()
