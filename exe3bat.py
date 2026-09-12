#!/usr/bin/env python3
"""EXE3BAT X - advanced cross-platform developer/system toolbox.

Safe by design: inspection, hashing, diagnostics, backups, process viewing,
network information, project analysis, and controlled command execution.
Destructive disk operations, security-control bypasses, credential collection,
and stealth/persistence behavior are intentionally excluded.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

APP = "EXE3BAT X"
VERSION = "3.0.0"
ROOT = Path(__file__).resolve().parent
LOG = ROOT / "exe3bat.log"
REPORT = ROOT / "diagnostic-report.json"

BLOCKED = {
    "diskpart", "format", "cipher", "bcdedit", "bootrec", "reg", "powershell",
    "wmic", "schtasks", "sc", "takeown", "icacls", "vssadmin", "wbadmin",
}
BLOCKED_TEXT = ("disableantispyware", "smartscreen", "securitycenter", "windefender")


@dataclass(slots=True)
class FileRecord:
    path: str
    bytes: int
    sha256: str
    modified: str


def log(message: str) -> None:
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{dt.datetime.now().astimezone().isoformat(timespec='seconds')}] {message}\n")
    except OSError:
        pass


def clear() -> None:
    if sys.stdout.isatty():
        os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    if sys.stdin.isatty():
        input("\nPress Enter to continue...")


def title(text: str) -> None:
    clear()
    print("╔" + "═" * 76 + "╗")
    print("║" + f" {APP}  v{VERSION}".ljust(76) + "║")
    print("║" + f" {text}".ljust(76) + "║")
    print("╚" + "═" * 76 + "╝")


def fmt_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    n = float(value)
    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{value} B"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def files(root: Path = ROOT) -> Iterable[Path]:
    excluded = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}
    for p in root.rglob("*"):
        if p.is_file() and not any(part in excluded for part in p.parts):
            yield p


def records() -> list[FileRecord]:
    result: list[FileRecord] = []
    for p in sorted(files(), key=lambda x: str(x).lower()):
        try:
            stat = p.stat()
            result.append(FileRecord(str(p.relative_to(ROOT)), stat.st_size,
                                     sha256(p), dt.datetime.fromtimestamp(stat.st_mtime).isoformat()))
        except OSError as exc:
            log(f"hash-error {p}: {exc}")
    return result


def system_snapshot() -> dict:
    return {
        "python": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "architecture": platform.architecture()[0],
        "hostname": socket.gethostname(),
        "cwd": str(Path.cwd()),
        "root": str(ROOT),
        "cpu_count": os.cpu_count(),
    }


def show_system() -> None:
    title("SYSTEM SNAPSHOT")
    for key, value in system_snapshot().items():
        print(f"{key:22} : {value}")
    log("system snapshot")
    pause()


def show_environment() -> None:
    title("ENVIRONMENT")
    for key in ("OS", "COMSPEC", "USERPROFILE", "USERNAME", "HOME", "SHELL", "TEMP", "TMP"):
        print(f"{key:22} : {os.environ.get(key, '<not set>')}")
    path = os.environ.get("PATH", "")
    print(f"{'PATH entries':22} : {len(path.split(os.pathsep)) if path else 0}")
    pause()


def show_network() -> None:
    title("NETWORK OVERVIEW")
    try:
        print(f"Hostname : {socket.gethostname()}")
        print(f"FQDN     : {socket.getfqdn()}")
        print(f"Local IP : {socket.gethostbyname(socket.gethostname())}")
    except OSError as exc:
        print(f"Lookup error: {exc}")
    print("\nInterfaces/routes are not modified by this tool.")
    pause()


def tree(path: Path, depth: int = 3, prefix: str = "") -> None:
    if depth < 0:
        return
    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError as exc:
        print(prefix + f"└─ [error: {exc}]")
        return
    visible = [p for p in entries if p.name not in {".git", "__pycache__", ".venv", "venv"}]
    for i, p in enumerate(visible):
        last = i == len(visible) - 1
        branch = "└─ " if last else "├─ "
        print(prefix + branch + p.name + ("/" if p.is_dir() else ""))
        if p.is_dir():
            tree(p, depth - 1, prefix + ("   " if last else "│  "))


def show_tree() -> None:
    title("PROJECT TREE")
    print(ROOT)
    tree(ROOT, 5)
    pause()


def inventory() -> None:
    title("FILE INVENTORY")
    data = records()
    total = 0
    for r in data:
        total += r.bytes
        print(f"{r.path}\n  {fmt_bytes(r.bytes):>12}  SHA256 {r.sha256}\n")
    print(f"Files: {len(data)}    Total: {fmt_bytes(total)}")
    log(f"inventory files={len(data)} bytes={total}")
    pause()


def extension_stats() -> None:
    title("PROJECT ANALYTICS")
    stats: dict[str, list[int]] = {}
    for p in files():
        ext = p.suffix.lower() or "[none]"
        try:
            size = p.stat().st_size
        except OSError:
            continue
        bucket = stats.setdefault(ext, [0, 0])
        bucket[0] += 1
        bucket[1] += size
    for ext, (count, size) in sorted(stats.items(), key=lambda x: (-x[1][0], x[0])):
        print(f"{ext:12} {count:5} files  {fmt_bytes(size):>12}")
    pause()


def duplicate_scan() -> None:
    title("DUPLICATE DETECTOR")
    by_size: dict[int, list[Path]] = {}
    for p in files():
        try:
            by_size.setdefault(p.stat().st_size, []).append(p)
        except OSError:
            pass
    groups = 0
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        hashes: dict[str, list[Path]] = {}
        for p in candidates:
            try:
                hashes.setdefault(sha256(p), []).append(p)
            except OSError:
                pass
        for digest, same in hashes.items():
            if len(same) > 1:
                groups += 1
                print(f"\n{fmt_bytes(size)}  {digest}")
                for p in same:
                    print(f"  - {p.relative_to(ROOT)}")
    print(f"\nDuplicate groups: {groups}")
    pause()


def backup() -> None:
    title("LOCAL BACKUP")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = ROOT / f"backup-{stamp}"
    destination.mkdir(exist_ok=False)
    count = 0
    for source in files():
        relative = source.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source, target)
            count += 1
        except OSError as exc:
            log(f"backup-error {source}: {exc}")
    print(f"Backup: {destination}")
    print(f"Files copied: {count}")
    log(f"backup created {destination} files={count}")
    pause()


def report() -> None:
    title("DIAGNOSTIC REPORT")
    data = {
        "application": APP,
        "version": VERSION,
        "generated": dt.datetime.now().astimezone().isoformat(),
        "system": system_snapshot(),
        "environment": {k: os.environ.get(k) for k in ("OS", "COMSPEC", "TEMP", "TMP", "USERPROFILE")},
        "files": [asdict(r) for r in records()],
    }
    REPORT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Written: {REPORT}")
    log("diagnostic report generated")
    pause()


def processes() -> None:
    title("PROCESS VIEW")
    if os.name == "nt":
        command = ["tasklist", "/fo", "table"]
    else:
        command = ["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        print(result.stdout[:18000])
        if result.stderr:
            print("\n" + result.stderr[:2000])
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Process query failed: {exc}")
    pause()


def safe_command(command: str) -> int:
    import shlex
    try:
        args = shlex.split(command, posix=os.name != "nt")
    except ValueError as exc:
        print(f"Parse error: {exc}")
        return 2
    if not args:
        return 0
    base = Path(args[0]).name.lower()
    normalized = command.lower()
    if base in BLOCKED or any(token in normalized for token in BLOCKED_TEXT):
        print("Blocked: this command can alter security settings or critical system state.")
        log(f"blocked command: {command!r}")
        return 126
    if base in {"del", "erase", "rmdir", "rd"}:
        print("Blocked: destructive file deletion is not available in the command runner.")
        return 126
    try:
        completed = subprocess.run(args, cwd=ROOT, check=False)
        log(f"command={args!r} code={completed.returncode}")
        return completed.returncode
    except OSError as exc:
        print(f"Execution error: {exc}")
        return 127


def command_menu() -> None:
    title("CONTROLLED COMMAND RUNNER")
    print("Only non-destructive development commands should be used.")
    print("Examples: python --version, git --version, py --version")
    command = input("\n> ").strip()
    if command:
        code = safe_command(command)
        print(f"\nExit code: {code}")
    pause()


def benchmark() -> None:
    title("SHA-256 BENCHMARK")
    payload = b"EXE3BAT-X" * 1_000_000
    start = time.perf_counter()
    digest = hashlib.sha256(payload).hexdigest()
    elapsed = time.perf_counter() - start
    mb = len(payload) / 1024 / 1024
    print(f"Payload : {mb:.2f} MiB")
    print(f"Time    : {elapsed:.4f} sec")
    print(f"Speed   : {mb / elapsed:.2f} MiB/s")
    print(f"Digest  : {digest}")
    pause()


def self_check() -> None:
    title("SELF CHECK")
    checks = {
        "Python >= 3.10": sys.version_info >= (3, 10),
        "Project root exists": ROOT.is_dir(),
        "Script exists": Path(__file__).is_file(),
        "Report path writable": os.access(ROOT, os.W_OK),
        "SHA-256 available": callable(hashlib.sha256),
        "JSON available": callable(json.dumps),
    }
    for name, passed in checks.items():
        print(f"[{'OK' if passed else 'FAIL'}] {name}")
    pause()


def menu() -> None:
    actions = {
        "1": show_system, "2": show_environment, "3": show_network,
        "4": show_tree, "5": inventory, "6": extension_stats,
        "7": duplicate_scan, "8": backup, "9": report,
        "10": processes, "11": command_menu, "12": benchmark,
        "13": self_check,
    }
    while True:
        title("MAIN CONTROL CENTER")
        print("  [ 1] System snapshot")
        print("  [ 2] Environment")
        print("  [ 3] Network overview")
        print("  [ 4] Project tree")
        print("  [ 5] SHA-256 inventory")
        print("  [ 6] Extension analytics")
        print("  [ 7] Duplicate detector")
        print("  [ 8] Local backup")
        print("  [ 9] JSON diagnostic report")
        print("  [10] Process viewer")
        print("  [11] Controlled command runner")
        print("  [12] Hash benchmark")
        print("  [13] Self-check")
        print("  [ 0] Exit")
        choice = input("\nSelect: ").strip()
        if choice == "0":
            log("application exit")
            print("Goodbye.")
            return
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Unknown selection.")
            time.sleep(0.8)


def cli() -> None:
    parser = argparse.ArgumentParser(description=f"{APP} v{VERSION}")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--report", action="store_true", help="generate diagnostic JSON")
    parser.add_argument("--inventory", action="store_true", help="print file inventory")
    parser.add_argument("--tree", action="store_true", help="print project tree")
    parser.add_argument("--self-check", action="store_true", help="run self-check")
    args = parser.parse_args()
    if args.report:
        report_cli()
    elif args.inventory:
        for r in records():
            print(f"{r.path}\t{r.bytes}\t{r.sha256}")
    elif args.tree:
        tree(ROOT, 8)
    elif args.self_check:
        for name, passed in {
            "Python >= 3.10": sys.version_info >= (3, 10),
            "Root exists": ROOT.is_dir(),
            "Script exists": Path(__file__).is_file(),
        }.items():
            print(f"[{'OK' if passed else 'FAIL'}] {name}")
    else:
        menu()


def report_cli() -> None:
    data = {
        "application": APP, "version": VERSION,
        "generated": dt.datetime.now().astimezone().isoformat(),
        "system": system_snapshot(),
        "files": [asdict(r) for r in records()],
    }
    REPORT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    log("start")
    try:
        cli()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        log("keyboard interrupt")
