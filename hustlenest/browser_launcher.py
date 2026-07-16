from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional

from .data import settings_repository


_BROWSER_CANDIDATES = (
    ("edge", "Microsoft Edge", (("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"), ("PROGRAMFILES", "Microsoft/Edge/Application/msedge.exe"))),
    ("chrome", "Google Chrome", (("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"), ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"), ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"))),
    ("firefox", "Mozilla Firefox", (("PROGRAMFILES", "Mozilla Firefox/firefox.exe"), ("PROGRAMFILES(X86)", "Mozilla Firefox/firefox.exe"))),
    ("brave", "Brave", (("LOCALAPPDATA", "BraveSoftware/Brave-Browser/Application/brave.exe"), ("PROGRAMFILES", "BraveSoftware/Brave-Browser/Application/brave.exe"))),
)


def available_browsers() -> list[dict[str, str]]:
    browsers = [{"id": "system", "label": "System default"}]
    for browser_id, label, candidates in _BROWSER_CANDIDATES:
        if _browser_path(candidates):
            browsers.append({"id": browser_id, "label": label})
    return browsers


def _browser_path(candidates: tuple[tuple[str, str], ...]) -> Optional[Path]:
    for environment_key, relative_path in candidates:
        root = os.environ.get(environment_key, "").strip()
        if not root:
            continue
        path = Path(root) / Path(relative_path)
        if path.is_file():
            return path
    return None


def launch_configured_browser(url: str) -> bool:
    mode = (settings_repository.get_setting("browser_launch_mode") or "system").strip().casefold()
    if mode == "none":
        return False
    browser_id = (settings_repository.get_setting("browser_id") or "system").strip().casefold()
    if mode == "system" or browser_id == "system":
        return bool(webbrowser.open(url, new=2))
    for candidate_id, _label, candidates in _BROWSER_CANDIDATES:
        if candidate_id != browser_id:
            continue
        executable = _browser_path(candidates)
        if executable is None:
            return False
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        subprocess.Popen([str(executable), url], close_fds=True, creationflags=creation_flags)
        return True
    return False
