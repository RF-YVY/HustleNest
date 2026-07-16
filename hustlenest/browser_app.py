"""Unified source launcher for the local backend and browser workspace."""
from __future__ import annotations

import argparse
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from hustlenest import web_bridge


def _raise_keyboard_interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def _default_web_directory() -> Path:
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "web"
    if getattr(sys, "frozen", False) and bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parent.parent / "web"


def _node_executable() -> Optional[str]:
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", "")) / "runtime" / ("node.exe" if os.name == "nt" else "node")
        if bundled.is_file():
            return str(bundled)
    return shutil.which("node.exe" if os.name == "nt" else "node")


def _wait_for_frontend(process: subprocess.Popen, host: str, port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"The browser UI stopped during startup (exit code {process.returncode}).")
        try:
            with socket.create_connection((host, port), timeout=0.4):
                return
        except OSError:
            time.sleep(0.15)
    raise RuntimeError(f"The browser UI did not become ready at http://{host}:{port}.")


def _windows_listener_pids(port: int) -> set[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        check=False,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        if parts[1].rsplit(":", 1)[-1] != str(port):
            continue
        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    return pids


def _stop_frontend(process: subprocess.Popen, port: int) -> None:
    if os.name == "nt":
        pids = _windows_listener_pids(port)
        if process.poll() is None:
            pids.add(process.pid)
        for pid in pids:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def run(
    *,
    web_directory: Path,
    frontend_host: str = "127.0.0.1",
    frontend_port: int = 3000,
    backend_host: str = web_bridge.DEFAULT_HOST,
    backend_port: int = web_bridge.DEFAULT_PORT,
    launch_browser: bool = True,
) -> None:
    web_directory = web_directory.resolve()
    if not (web_directory / "package.json").is_file():
        raise RuntimeError(f"Browser workspace not found: {web_directory}")
    if not (web_directory / "dist" / "server" / "index.js").is_file():
        raise RuntimeError("The browser production build is missing. Run `npm install` and `npm run build` in the web directory.")
    node = _node_executable()
    local_server = web_directory / "start-local.mjs"
    vinext_server = web_directory / "node_modules" / "vinext" / "dist" / "server" / "prod-server.js"
    if not node or not local_server.is_file() or not vinext_server.is_file():
        raise RuntimeError("Node.js and the installed browser dependencies are required. Run `npm install` in the web directory.")

    command = [node, str(local_server), "-H", frontend_host, "-p", str(frontend_port)]
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    frontend = subprocess.Popen(command, cwd=web_directory, creationflags=creation_flags)
    try:
        _wait_for_frontend(frontend, frontend_host, frontend_port)
        browser_host = "localhost" if frontend_host in {"127.0.0.1", "0.0.0.0"} else frontend_host
        web_bridge.run(backend_host, backend_port, f"http://{browser_host}:{frontend_port}" if launch_browser else None)
    finally:
        _stop_frontend(frontend, frontend_port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the local HustleNest backend and browser UI together.")
    parser.add_argument("--web-dir", type=Path, default=_default_web_directory())
    parser.add_argument("--frontend-host", default="127.0.0.1")
    parser.add_argument("--frontend-port", default=3000, type=int)
    parser.add_argument("--backend-host", default=web_bridge.DEFAULT_HOST)
    parser.add_argument("--backend-port", default=web_bridge.DEFAULT_PORT, type=int)
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser for this launch.")
    args = parser.parse_args()
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _raise_keyboard_interrupt)
    try:
        run(
            web_directory=args.web_dir,
            frontend_host=args.frontend_host,
            frontend_port=args.frontend_port,
            backend_host=args.backend_host,
            backend_port=args.backend_port,
            launch_browser=not args.no_browser,
        )
    except RuntimeError as exc:
        print(f"HustleNest could not start: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
