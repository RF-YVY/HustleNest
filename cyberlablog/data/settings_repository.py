from __future__ import annotations

from typing import Dict

from ..models.order_models import AppSettings
from .database import create_connection

_DEFAULTS: Dict[str, str] = {
    "business_name": "Wicker Made Sales",
    "low_inventory_threshold": "5",
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

    return AppSettings(
        business_name=business_name,
        low_inventory_threshold=max(0, low_inventory),
    )
