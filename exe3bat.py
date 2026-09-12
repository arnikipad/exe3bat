#!/usr/bin/env python3
"""exe3bat - Massive, safe Windows command launcher and project utility.

This program intentionally does NOT disable security controls, delete user data,
modify boot records, or perform destructive system changes. It provides a
menu-driven toolbox for inspecting the environment, validating Python, running
local project commands, creating backups, and generating diagnostics.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP = "exe3bat"
VERSION = "2.0.0"
ROOT = Path(__file__).resolve().parent
LOG = ROOT / "exe3bat.log"


def write_log(message: str) -> None:
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {message}\n")


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input("\nPress Enter to continue...")


def header(title: str) -> None:
    clear()
    print("=" * 78)
    print(f"  {APP.upper()}  |  v{VERSION}")
    print(f"  {title}")
    print("=" * 78)


def run_command(args: list[str], timeout: int = 30) -> int:
    print("\n> " + " ".join(args))
    try:
        result = subprocess.run(args, cwd=ROOT, timeout=timeout, check=False)
        write_log(f"command={args!r} returncode={result.returncode}")
        return result.returncode
    except FileNotFoundError:
        print("Command not found.")
        write_log(f"command-not-found={args!r}")
        return 127
    except subprocess.TimeoutExpired:
        print("Command timed out.")
        write_log(f"command-timeout={args!r}")
        return 124


def system_info() -> None:
    header("System information")
    info = {
        "Python": sys.version.replace("\n", " "),
        "Executable": sys.executable,
        "Platform": platform.platform(),
        "Machine": platform.machine(),
        "Processor": platform.processor() or "unknown",
        "Architecture": platform.architecture()[0],
        "Working directory": str(Path.cwd()),
        "Script directory": str(ROOT),
    }
    for key, value in info.items():
        print(f"{key:20}: {value}")
    write_log("viewed system information")
    pause()


def environment() -> None:
    header("Environment")
    names = ["PATH", "TEMP", "TMP", "USERPROFILE", "USERNAME", "COMSPEC", "OS"]
    for name in names:
        value = os.environ.get(name, "<not set>")
        if name == "PATH":
            print(f"{name}: {len(value)} characters")
        else:
            print(f"{name:12}: {value}")
    pause()


def project_tree(path: Path, depth: int = 3, prefix: str = "") -> None:
    if depth < 0:
        return
    try:
        items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError as exc:
        print(prefix + f"[unreadable: {exc}]")
        return
    for item in items:
        if item.name in {".git", "__pycache__", ".venv", "venv"}:
            continue
        print(prefix + ("[F] " if item.is_file() else "[D] ") + item.name)
        if item.is_dir():
            project_tree(item, depth - 1, prefix + "    ")


def show_tree() -> None:
    header("Project tree")
    print(ROOT)
    project_tree(ROOT, 4)
    pause()


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_inventory() -> None:
    header("File inventory and SHA-256")
    count = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            size = path.stat().st_size
            digest = hash_file(path)
            rel = path.relative_to(ROOT)
            print(f"{rel} | {size:,} bytes | {digest[:16]}...")
            count += 1
        except OSError as exc:
            print(f"{path.name} | ERROR: {exc}")
    print(f"\nFiles: {count}")
    pause()


def backup_project() -> None:
    header("Create local project backup")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = ROOT / f"backup-{stamp}"
    try:
        destination.mkdir()
        for item in ROOT.iterdir():
            if item.name in {".git", destination.name} or item.name.startswith("backup-"):
                continue
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        print(f"Backup created: {destination}")
        write_log(f"backup-created={destination}")
    except OSError as exc:
        print(f"Backup failed: {exc}")
        write_log(f"backup-failed={exc}")
    pause()


def json_report() -> None:
    header("Generate diagnostic report")
    report = {
        "application": APP,
        "version": VERSION,
        "generated": dt.datetime.now().astimezone().isoformat(),
        "system": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "architecture": platform.architecture()[0],
        },
        "project": {
            "root": str(ROOT),
            "files": [],
        },
    }
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            try:
                report["project"]["files"].append({
                    "path": str(path.relative_to(ROOT)),
                    "bytes": path.stat().st_size,
                    "sha256": hash_file(path),
                })
            except OSError:
                pass
    out = ROOT / "diagnostic-report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Written: {out}")
    write_log("generated diagnostic-report.json")
    pause()


def python_check() -> None:
    header("Python validation")
    print(f"Python executable: {sys.executable}")
    print(f"Python version   : {platform.python_version()}")
    print(f"Python major/minor: {sys.version_info.major}.{sys.version_info.minor}")
    print("Standard library imports: OK")
    write_log("python validation passed")
    pause()


def safe_shell() -> None:
    header("Safe command runner")
    print("Run a single explicitly entered local command.")
    print("This runner blocks commands intended to disable security controls or erase disks/data.")
    command = input("\nCommand (blank to cancel): ").strip()
    if not command:
        return
    lowered = command.lower()
    blocked_terms = [
        "format ", "diskpart", "cipher /w", "bcdedit /delete", "reg delete",
        "defender", "smartscreen", "disableantispyware", "shutdown /s", "taskkill /f /im explorer",
    ]
    if any(term in lowered for term in blocked_terms):
        print("Blocked by the safe command policy.")
        write_log(f"blocked-command={command!r}")
        pause()
        return
    import shlex
    try:
        args = shlex.split(command, posix=(os.name != "nt"))
    except ValueError as exc:
        print(f"Invalid command syntax: {exc}")
        pause()
        return
    if args:
        run_command(args)
    pause()


def create_launcher() -> None:
    header("Create Windows launcher")
    launcher = ROOT / "run-exe3bat.bat"
    launcher.write_text(
        "@echo off\n"
        "setlocal\n"
        "cd /d \"%~dp0\"\n"
        "py -3 exe3bat.py\n"
        "if errorlevel 1 python exe3bat.py\n"
        "endlocal\n",
        encoding="utf-8",
    )
    print(f"Created: {launcher}")
    pause()


def main() -> None:
    write_log("application-start")
    while True:
        header("Main menu")
        print("  [1] System information")
        print("  [2] Environment overview")
        print("  [3] Project tree")
        print("  [4] File inventory + SHA-256")
        print("  [5] Create local backup")
        print("  [6] Generate JSON diagnostic report")
        print("  [7] Validate Python")
        print("  [8] Safe command runner")
        print("  [9] Create Windows .BAT launcher")
        print("  [0] Exit")
        choice = input("\nSelect: ").strip()
        actions = {
            "1": system_info,
            "2": environment,
            "3": show_tree,
            "4": file_inventory,
            "5": backup_project,
            "6": json_report,
            "7": python_check,
            "8": safe_shell,
            "9": create_launcher,
        }
        if choice == "0":
            write_log("application-exit")
            print("Goodbye.")
            return
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Unknown selection.")
            pause()


if __name__ == "__main__":
    main()
