from __future__ import annotations

from typing import Dict

from ..models.order_models import AppSettings
from .database import create_connection

_DEFAULTS: Dict[str, str] = {
    "business_name": "Wicker Made Sales",
    "low_inventory_threshold": "5",
    "order_number_format": "ORD-{seq:04d}",
    "order_number_next": "1",
    "dashboard_show_business_name": "1",
    "dashboard_logo_path": "",
    "dashboard_logo_alignment": "top-left",
    "dashboard_logo_size": "160",
    "dashboard_home_city": "",
    "dashboard_home_state": "",
}


def get_setting(key: str) -> str:
    key = key.strip()
    with create_connection() as connection:
        row = connection.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()

    if row is None:
        return _DEFAULTS.get(key, "")
    return row["value"]


def set_setting(key: str, value: str) -> None:
    key = key.strip()
    with create_connection() as connection:
        connection.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        connection.commit()


def get_app_settings() -> AppSettings:
    business_name = get_setting("business_name") or _DEFAULTS["business_name"]
    try:
        low_inventory = int(get_setting("low_inventory_threshold") or _DEFAULTS["low_inventory_threshold"])
    except ValueError:
        low_inventory = int(_DEFAULTS["low_inventory_threshold"])

    order_number_format = get_setting("order_number_format") or _DEFAULTS["order_number_format"]
    try:
        order_number_next = int(get_setting("order_number_next") or _DEFAULTS["order_number_next"])
    except ValueError:
        order_number_next = int(_DEFAULTS["order_number_next"])

    show_name_raw = get_setting("dashboard_show_business_name")
    if not show_name_raw:
        show_name_raw = _DEFAULTS["dashboard_show_business_name"]
    show_name_clean = show_name_raw.strip().lower()
    show_name = show_name_clean not in {"0", "false", "no"}

    logo_path = get_setting("dashboard_logo_path") or _DEFAULTS["dashboard_logo_path"]
    alignment = get_setting("dashboard_logo_alignment") or _DEFAULTS["dashboard_logo_alignment"]
    alignment = alignment.strip().lower() or _DEFAULTS["dashboard_logo_alignment"]
    if alignment not in {
        "top-left",
        "top-center",
        "top-right",
        "bottom-left",
        "bottom-center",
        "bottom-right",
    }:
        alignment = _DEFAULTS["dashboard_logo_alignment"]

    try:
        logo_size = int(get_setting("dashboard_logo_size") or _DEFAULTS["dashboard_logo_size"])
    except ValueError:
        logo_size = int(_DEFAULTS["dashboard_logo_size"])
    logo_size = max(24, min(1024, logo_size))

    home_city = get_setting("dashboard_home_city") or _DEFAULTS["dashboard_home_city"]
    home_state = get_setting("dashboard_home_state") or _DEFAULTS["dashboard_home_state"]
    legacy_zip = get_setting("dashboard_user_zip") or ""

    city_clean = home_city.strip()
    state_clean = home_state.strip().upper()[:2]

    if (not city_clean or not state_clean) and legacy_zip:
        # Legacy fallback: if a previous version stored "City, ST", reuse it
        parts = [segment.strip() for segment in legacy_zip.split(",") if segment.strip()]
        if len(parts) == 2:
            city_candidate, state_candidate = parts
            city_clean = city_clean or city_candidate
            state_candidate = state_candidate.upper()[:2]
            state_clean = state_clean or state_candidate

    return AppSettings(
        business_name=business_name,
        low_inventory_threshold=max(0, low_inventory),
        order_number_format=order_number_format.strip() or _DEFAULTS["order_number_format"],
        order_number_next=max(1, order_number_next),
        dashboard_show_business_name=show_name,
        dashboard_logo_path=logo_path.strip(),
        dashboard_logo_alignment=alignment,
        dashboard_logo_size=logo_size,
        dashboard_home_city=city_clean,
        dashboard_home_state=state_clean,
    )
