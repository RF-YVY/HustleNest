from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from itertools import zip_longest
from typing import Optional, Tuple

APP_VERSION = "v1.0"
REPOSITORY = "RF-YVY/Sales-Tracking"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
RELEASES_URL = f"{REPOSITORY_URL}/releases"
_LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
_TAGS_API = f"https://api.github.com/repos/{REPOSITORY}/tags"
_USER_AGENT = "HustleNest-Updater"


@dataclass
class UpdateResult:
    is_newer: bool
    latest_version: Optional[str]
    download_url: Optional[str]
    error: Optional[str] = None


def check_for_updates(timeout: float = 5.0) -> UpdateResult:
    latest, error = _fetch_latest_release(timeout)
    if latest is None:
        latest, fallback_error = _fetch_latest_tag(timeout)
        if latest is None:
            return UpdateResult(False, None, None, fallback_error or error or "Unable to determine latest version.")

    latest_version, download_url = latest
    if _is_remote_newer(latest_version, APP_VERSION):
        return UpdateResult(True, latest_version, download_url or RELEASES_URL)

    return UpdateResult(False, latest_version, download_url or RELEASES_URL, error=None)


def _fetch_latest_release(timeout: float) -> Tuple[Optional[Tuple[str, Optional[str]]], Optional[str]]:
    data, error = _fetch_json(_LATEST_RELEASE_API, timeout)
    if data is None:
        return None, error

    tag_name = _safe_str(data.get("tag_name") or data.get("name"))
    html_url = _safe_str(data.get("html_url"))
    if tag_name:
        return (tag_name, html_url or RELEASES_URL), None

    return None, "Latest release did not include a version tag."


def _fetch_latest_tag(timeout: float) -> Tuple[Optional[Tuple[str, Optional[str]]], Optional[str]]:
    data, error = _fetch_json(_TAGS_API, timeout)
    if data is None:
        return None, error

    if isinstance(data, list) and data:
        first = data[0]
        name = _safe_str(first.get("name"))
        if name:
            return (name, RELEASES_URL), None
    return None, "No tags available for repository."


def _fetch_json(url: str, timeout: float) -> Tuple[Optional[object], Optional[str]]:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None, f"HTTP {response.status} while contacting update server."
            payload = response.read()
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code} error from update server."
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return None, f"Network error: {reason}"
    except (TimeoutError, socket.timeout):
        return None, "Update check timed out."

    try:
        return json.loads(payload.decode("utf-8")), None
    except json.JSONDecodeError:
        return None, "Received invalid response when checking for updates."


def _is_remote_newer(remote: str, current: str) -> bool:
    remote_parts = _parse_version(remote)
    current_parts = _parse_version(current)
    for remote_part, current_part in zip_longest(remote_parts, current_parts, fillvalue=0):
        if remote_part > current_part:
            return True
        if remote_part < current_part:
            return False
    return False


def _parse_version(value: str) -> Tuple[int, ...]:
    cleaned = _safe_str(value).lstrip("vV").strip()
    if not cleaned:
        return (0,)
    parts = []
    for raw_part in cleaned.split("."):
        digits = "".join(ch for ch in raw_part if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def _safe_str(value: Optional[object]) -> str:
    return str(value).strip() if value is not None else ""
