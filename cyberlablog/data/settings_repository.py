from __future__ import annotations

import json
from typing import Dict, List

from ..models.order_models import AppSettings, PaymentOption
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
    "tax_rate_percent": "0",
    "tax_show_on_invoice": "0",
    "tax_add_to_total": "0",
    "invoice_slogan": "",
    "invoice_street": "",
    "invoice_city": "",
    "invoice_state": "",
    "invoice_zip": "",
    "invoice_phone": "",
    "invoice_fax": "",
    "invoice_terms": "Due on receipt",
    "invoice_comments": "",
    "invoice_contact_name": "",
    "invoice_contact_phone": "",
    "invoice_contact_email": "",
    "payment_options": "[]",
    "payment_paypal": "",
    "payment_venmo": "",
    "payment_cash_app": "",
    "payment_other": "",
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

    invoice_slogan = get_setting("invoice_slogan") or _DEFAULTS["invoice_slogan"]
    invoice_street = get_setting("invoice_street") or _DEFAULTS["invoice_street"]
    invoice_city = get_setting("invoice_city") or _DEFAULTS["invoice_city"]
    invoice_state = get_setting("invoice_state") or _DEFAULTS["invoice_state"]
    invoice_zip = get_setting("invoice_zip") or _DEFAULTS["invoice_zip"]
    invoice_phone = get_setting("invoice_phone") or _DEFAULTS["invoice_phone"]
    invoice_fax = get_setting("invoice_fax") or _DEFAULTS["invoice_fax"]
    invoice_terms = get_setting("invoice_terms") or _DEFAULTS["invoice_terms"]
    invoice_comments = get_setting("invoice_comments") or _DEFAULTS["invoice_comments"]
    invoice_contact_name = get_setting("invoice_contact_name") or _DEFAULTS["invoice_contact_name"]
    invoice_contact_phone = get_setting("invoice_contact_phone") or _DEFAULTS["invoice_contact_phone"]
    invoice_contact_email = get_setting("invoice_contact_email") or _DEFAULTS["invoice_contact_email"]

    raw_payment_options = get_setting("payment_options") or _DEFAULTS["payment_options"]
    try:
        parsed_payment_options = json.loads(raw_payment_options)
    except json.JSONDecodeError:
        parsed_payment_options = []

    payment_options: List[PaymentOption] = []
    if isinstance(parsed_payment_options, list):
        for entry in parsed_payment_options:
            if not isinstance(entry, dict):
                continue
            label_text = str(entry.get("label", "")).strip()
            value_text = str(entry.get("value", "")).strip()
            if label_text and value_text:
                payment_options.append(PaymentOption(label=label_text, value=value_text))

    legacy_sources = [
        ("PayPal", get_setting("payment_paypal")),
        ("Venmo", get_setting("payment_venmo")),
        ("Cash App", get_setting("payment_cash_app")),
    ]
    existing_labels = {option.label.lower() for option in payment_options}
    for label_text, raw_value in legacy_sources:
        value_text = (raw_value or "").strip()
        if not value_text:
            continue
        normalized_label = label_text.strip().lower()
        if normalized_label not in existing_labels:
            payment_options.append(PaymentOption(label=label_text, value=value_text))
            existing_labels.add(normalized_label)

    payment_other = get_setting("payment_other") or _DEFAULTS["payment_other"]

    tax_rate_raw = get_setting("tax_rate_percent")
    if not tax_rate_raw:
        tax_rate_raw = _DEFAULTS["tax_rate_percent"]
    try:
        tax_rate_percent = max(0.0, min(100.0, float(tax_rate_raw)))
    except ValueError:
        tax_rate_percent = 0.0

    show_tax_raw = (get_setting("tax_show_on_invoice") or _DEFAULTS["tax_show_on_invoice"]).strip().lower()
    tax_show_on_invoice = show_tax_raw not in {"0", "false", "no"}

    include_tax_raw = (get_setting("tax_add_to_total") or _DEFAULTS["tax_add_to_total"]).strip().lower()
    tax_add_to_total = include_tax_raw not in {"0", "false", "no"}

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
        invoice_slogan=invoice_slogan.strip(),
        invoice_street=invoice_street.strip(),
        invoice_city=invoice_city.strip(),
        invoice_state=invoice_state.strip().upper()[:2],
        invoice_zip=invoice_zip.strip(),
        invoice_phone=invoice_phone.strip(),
        invoice_fax=invoice_fax.strip(),
        invoice_terms=invoice_terms.strip() or _DEFAULTS["invoice_terms"],
        invoice_comments=invoice_comments.strip(),
        invoice_contact_name=invoice_contact_name.strip(),
        invoice_contact_phone=invoice_contact_phone.strip(),
        invoice_contact_email=invoice_contact_email.strip(),
        payment_options=payment_options,
        payment_other=payment_other.strip(),
        tax_rate_percent=tax_rate_percent,
        tax_show_on_invoice=tax_show_on_invoice,
        tax_add_to_total=tax_add_to_total,
    )
