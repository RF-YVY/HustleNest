from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import logging
import mimetypes
import shutil
import sqlite3
from math import isfinite
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from .data import (
    crm_repository,
    document_repository,
    expense_repository,
    goal_repository,
    loss_repository,
    material_repository,
    order_repository,
    product_repository,
    settings_repository,
    vendor_repository,
)
from .data.database import close_database_for_replacement, create_connection, get_database_path, get_storage_root, initialize
from .models.order_models import BusinessGoal, CostComponent, CRMContact, CRMInteraction, DocumentRecord, Expense, GoalCheckpoint, LossRecord, Material, Order, OrderItem, PaymentOption, Product, RecurringExpense, Vendor
from .browser_launcher import available_browsers, launch_configured_browser
from .versioning import APP_VERSION, RELEASES_URL, REPOSITORY_URL
from .services import cloud_sync_service, crm_service, finance_service, goal_service, import_service, order_service, report_service, soft_delete_service


LOGGER = logging.getLogger("hustlenest.web_bridge")
ORDER_STATUSES = ("Received", "Paid", "Processing", "Ready to Ship", "Shipped")
RECURRING_FREQUENCIES = {"daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"}
GOAL_METRICS = {"revenue", "sales", "profit", "orders", "expenses", "losses", "crm-followups"}
US_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
DASHBOARD_SECTIONS = {
    "product_sales": "Product sales breakdown",
    "top_customers": "Top customers",
    "notifications": "Notifications",
    "outstanding_orders": "Outstanding orders",
    "completed_orders": "Completed orders",
}
APPEARANCE_THEMES = {"light", "dark", "minty", "solar", "mission-control", "glass"}
APPEARANCE_TEXT_SCALES = {1.0, 1.1, 1.25, 1.4}
CLOUD_SYNC_PROVIDERS = {
    "local-folder": {"label": "Local folder (sync client)", "fields": (("directory", "Directory", True, False, ""), ("file_name", "Remote file name", False, False, "hustlenest.db"))},
    "google-drive": {"label": "Personal Google Drive", "fields": (("token_path", "Token JSON path", True, True, ""), ("client_secrets_path", "Client secrets path", False, True, ""), ("folder_id", "Folder ID", False, False, "root"), ("file_name", "Remote file name", False, False, "hustlenest.db"))},
    "dropbox": {"label": "Dropbox", "fields": (("access_token", "Access token", True, True, ""), ("remote_path", "Remote path", True, False, "/Apps/HustleNest/hustlenest.db"))},
    "onedrive": {"label": "Microsoft OneDrive", "fields": (("client_id", "Client ID", True, False, ""), ("client_secret", "Client secret", True, True, ""), ("tenant_id", "Tenant", True, False, "consumers"), ("refresh_token", "Refresh token", True, True, ""), ("remote_path", "Remote path", False, False, "Documents/hustlenest.db"))},
    "sftp": {"label": "Self-hosted SFTP", "fields": (("host", "Host", True, False, ""), ("port", "Port", False, False, "22"), ("username", "Username", True, False, ""), ("password", "Password", False, True, ""), ("private_key_path", "Private key path", False, True, ""), ("remote_path", "Remote path", True, False, "/hustlenest/hustlenest.db"))},
}
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MUTATION_LOCK = threading.RLock()
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_PRODUCT_PHOTO_BYTES = 8 * 1024 * 1024
MAX_BRAND_LOGO_BYTES = 8 * 1024 * 1024
MAX_PROFILE_AVATAR_BYTES = 5 * 1024 * 1024
MAX_IMPORT_BYTES = 12 * 1024 * 1024
MAX_JSON_BODY_BYTES = 30 * 1024 * 1024


class BridgeError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: HTTPStatus,
        fields: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields or {}


@dataclass(frozen=True)
class BinaryDownload:
    filename: str
    content_type: str
    content: bytes


def _money(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def _record_revision(values: dict[str, Any]) -> str:
    source = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _required_text(values: dict[str, Any], field: str, label: str, maximum: int = 200) -> str:
    value = str(values.get(field, "")).strip()
    if not value:
        raise BridgeError("validation_failed", f"{label} is required.", HTTPStatus.BAD_REQUEST, {field: "required"})
    return value[:maximum]


def _optional_text(values: dict[str, Any], field: str, maximum: int = 500) -> str:
    return str(values.get(field, "")).strip()[:maximum]


def _nonnegative_number(values: dict[str, Any], field: str, label: str, *, positive: bool = False) -> float:
    try:
        value = float(values.get(field, 0))
    except (TypeError, ValueError) as exc:
        raise BridgeError("validation_failed", f"{label} must be a number.", HTTPStatus.BAD_REQUEST, {field: "invalid_number"}) from exc
    if not isfinite(value):
        raise BridgeError("validation_failed", f"{label} must be a finite number.", HTTPStatus.BAD_REQUEST, {field: "invalid_number"})
    if value < 0 or (positive and value <= 0):
        code = "must_be_positive" if positive else "must_be_nonnegative"
        raise BridgeError("validation_failed", f"{label} must be {'greater than zero' if positive else 'zero or more'}.", HTTPStatus.BAD_REQUEST, {field: code})
    return value


def _optional_id(values: dict[str, Any], field: str) -> Optional[int]:
    raw = values.get(field)
    if raw in {None, ""}:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise BridgeError("validation_failed", "The selected record is invalid.", HTTPStatus.BAD_REQUEST, {field: "invalid_id"}) from exc
    return value if value > 0 else None


def _cost_components(values: dict[str, Any]) -> list[CostComponent]:
    raw = values.get("cost_components", [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except json.JSONDecodeError as exc:
            raise BridgeError("validation_failed", "Product cost components are invalid.", HTTPStatus.BAD_REQUEST, {"cost_components": "invalid"}) from exc
    if not isinstance(raw, list) or len(raw) > 20:
        raise BridgeError("validation_failed", "Use no more than 20 product cost components.", HTTPStatus.BAD_REQUEST, {"cost_components": "invalid"})
    components: list[CostComponent] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise BridgeError("validation_failed", "A product cost component is invalid.", HTTPStatus.BAD_REQUEST, {f"cost_components.{index}": "invalid"})
        label = str(item.get("label", "")).strip()[:100]
        if not label:
            raise BridgeError("validation_failed", "Each extra cost needs a label.", HTTPStatus.BAD_REQUEST, {f"cost_components.{index}.label": "required"})
        amount = _nonnegative_number(item, "amount", f"{label} amount")
        components.append(CostComponent(label, amount))
    return components


def _product_status(values: dict[str, Any]) -> str:
    requested = str(values.get("status", "Available")).strip()
    match = next((item for item in order_service.list_product_statuses() if item.casefold() == requested.casefold()), None)
    if match is None:
        raise BridgeError("validation_failed", "Product status is invalid.", HTTPStatus.BAD_REQUEST, {"status": "invalid_choice"})
    return match


def _entry_date(values: dict[str, Any]) -> date:
    raw = str(values.get("date", "")).strip()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise BridgeError("validation_failed", "Choose a valid date.", HTTPStatus.BAD_REQUEST, {"date": "invalid_date"}) from exc


def _date_field(values: dict[str, Any], field: str, label: str, *, required: bool = True) -> Optional[date]:
    raw = str(values.get(field, "")).strip()
    if not raw and not required:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise BridgeError("validation_failed", f"Choose a valid {label.lower()}.", HTTPStatus.BAD_REQUEST, {field: "invalid_date"}) from exc


def _recurring_schedule(values: dict[str, Any]) -> tuple[str, date, Optional[date], date]:
    frequency = str(values.get("frequency", "monthly")).strip().casefold()
    if frequency not in RECURRING_FREQUENCIES:
        raise BridgeError("validation_failed", "Choose a supported frequency.", HTTPStatus.BAD_REQUEST, {"frequency": "invalid_choice"})
    start_date = _date_field(values, "start_date", "Start date")
    next_occurrence = _date_field(values, "next_occurrence", "Next occurrence")
    end_date = _date_field(values, "end_date", "End date", required=False)
    assert start_date is not None and next_occurrence is not None
    if next_occurrence < start_date:
        raise BridgeError("validation_failed", "Next occurrence cannot be before the start date.", HTTPStatus.BAD_REQUEST, {"next_occurrence": "before_start"})
    if end_date and (end_date < start_date or next_occurrence > end_date):
        raise BridgeError("validation_failed", "The end date must include the next occurrence.", HTTPStatus.BAD_REQUEST, {"end_date": "invalid_range"})
    return frequency.title(), start_date, end_date, next_occurrence


def _contact_index() -> dict[str, CRMContact]:
    return {
        contact.customer_name.strip().casefold(): contact
        for contact in crm_repository.list_contacts()
        if contact.customer_name.strip()
    }


def _customer_revision(contact: CRMContact) -> str:
    return _record_revision({
        "id": contact.id, "name": contact.customer_name, "company": contact.company,
        "email": contact.email, "phone": contact.phone, "address": contact.address,
        "tags": contact.tags, "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "last_contacted": contact.last_contacted.isoformat() if contact.last_contacted else None,
        "next_follow_up": contact.next_follow_up.isoformat() if contact.next_follow_up else None,
        "preferred_channel": contact.preferred_channel, "notes": contact.notes,
    })


def _customer_dto(contact: CRMContact) -> dict[str, Any]:
    payload = {
        "id": contact.id,
        "key": f"crm:{contact.id}",
        "name": contact.customer_name,
        "company": contact.company,
        "email": contact.email,
        "phone": contact.phone,
        "address": contact.address,
        "notes": contact.notes,
        "last_contacted": contact.last_contacted.isoformat() if contact.last_contacted else None,
        "next_follow_up": contact.next_follow_up.isoformat() if contact.next_follow_up else None,
        "preferred_channel": contact.preferred_channel,
    }
    payload["revision"] = _customer_revision(contact)
    return payload


def _interaction_dto(interaction: CRMInteraction) -> dict[str, Any]:
    payload = {
        "id": interaction.id,
        "contact_id": interaction.contact_id,
        "interaction_date": interaction.interaction_date.isoformat(),
        "channel": interaction.channel,
        "summary": interaction.summary,
        "follow_up_date": interaction.follow_up_date.isoformat() if interaction.follow_up_date else None,
        "follow_up_action": interaction.follow_up_action,
        "order_id": interaction.order_id,
    }
    payload["revision"] = _record_revision(payload)
    return payload


def get_customer_detail(contact_id: int) -> dict[str, Any]:
    contact = crm_repository.get_contact(contact_id)
    if contact is None:
        raise BridgeError("not_found", "Customer not found.", HTTPStatus.NOT_FOUND)
    payload = _customer_dto(contact)
    payload["interactions"] = [_interaction_dto(item) for item in crm_repository.list_interactions(contact_id, limit=100)]
    return payload


def log_customer_interaction(contact_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    values = payload.get("values")
    if not isinstance(values, dict):
        raise BridgeError("validation_failed", "Interaction values are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})
    interaction_day = _date_field(values, "interaction_date", "Interaction date")
    follow_up = _date_field(values, "follow_up_date", "Follow-up date", required=False)
    assert interaction_day is not None
    if follow_up and follow_up < interaction_day:
        raise BridgeError("validation_failed", "Follow-up cannot be before the interaction.", HTTPStatus.BAD_REQUEST, {"follow_up_date": "before_interaction"})
    channel = _optional_text(values, "channel", 80)
    summary = _required_text(values, "summary", "Interaction summary", 1000)
    order_id = _optional_id(values, "order_id")

    with MUTATION_LOCK:
        contact = crm_repository.get_contact(contact_id)
        if contact is None:
            raise BridgeError("not_found", "Customer not found.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _customer_revision(contact))
        if order_id:
            order = order_repository.fetch_order(order_id)
            if order is None or order.customer_name.strip().casefold() != contact.customer_name.strip().casefold():
                raise BridgeError("validation_failed", "Choose an order for this customer.", HTTPStatus.BAD_REQUEST, {"order_id": "invalid_relationship"})
        crm_repository.save_interaction(CRMInteraction(
            id=None,
            contact_id=contact_id,
            interaction_date=datetime.combine(interaction_day, datetime.min.time()),
            channel=channel,
            summary=summary,
            follow_up_date=follow_up,
            follow_up_action=_optional_text(values, "follow_up_action", 300),
            order_id=order_id,
        ))
        if contact.last_contacted is None or interaction_day >= contact.last_contacted:
            contact.last_contacted = interaction_day
        if follow_up is not None:
            contact.next_follow_up = follow_up
        if channel:
            contact.preferred_channel = channel
        crm_repository.save_contact(contact)
    return get_customer_detail(contact_id)


def delete_customer_interaction(contact_id: int, interaction_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with MUTATION_LOCK:
        interaction = next((item for item in crm_repository.list_interactions(contact_id, limit=1000) if item.id == interaction_id), None)
        if interaction is None:
            raise BridgeError("not_found", "Interaction not found.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _interaction_dto(interaction)["revision"])
        crm_repository.delete_interaction(interaction_id)
    return get_customer_detail(contact_id)


def search_customers(query: str = "", limit: int = 20) -> list[dict[str, Any]]:
    term = query.strip().casefold()
    merged: dict[str, dict[str, Any]] = {}
    for contact in crm_repository.list_contacts():
        normalized = contact.customer_name.strip().casefold()
        if normalized:
            merged[normalized] = _customer_dto(contact)

    for name, address in order_repository.fetch_distinct_customers():
        normalized = name.strip().casefold()
        if not normalized:
            continue
        existing = merged.get(normalized)
        if existing:
            if not existing["address"] and address:
                existing["address"] = address
            continue
        merged[normalized] = {
            "id": None,
            "key": f"order:{normalized}",
            "name": name,
            "company": "",
            "email": "",
            "phone": "",
            "address": address,
            "notes": "",
            "last_contacted": None,
            "next_follow_up": None,
            "preferred_channel": "",
            "revision": "",
        }

    matches = []
    for customer in sorted(merged.values(), key=lambda item: item["name"].casefold()):
        searchable = " ".join(
            str(customer[field]) for field in ("name", "company", "email", "phone", "address")
        ).casefold()
        if term and term not in searchable:
            continue
        matches.append(customer)
        if len(matches) >= min(max(limit, 1), 250):
            break
    return matches


def promote_order_customer(payload: dict[str, Any]) -> dict[str, Any]:
    name = _required_text(payload, "name", "Customer name")
    source = next(((candidate, address) for candidate, address in order_repository.fetch_distinct_customers() if candidate.strip().casefold() == name.casefold()), None)
    if source is None:
        raise BridgeError("customer_not_found", "That order customer no longer exists.", HTTPStatus.NOT_FOUND)
    with MUTATION_LOCK:
        existing = next((item for item in crm_repository.list_contacts() if item.customer_name.strip().casefold() == name.casefold()), None)
        if existing:
            return _customer_dto(existing)
        contact_id = crm_repository.save_contact(CRMContact(id=None, customer_name=source[0], address=source[1] or ""))
    contact = crm_repository.get_contact(contact_id)
    assert contact is not None
    return _customer_dto(contact)


def _product_dto(product: Any, forecast: Any = None) -> dict[str, Any]:
    photo = order_service.resolve_product_photo(product.photo_path)
    payload = {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "inventory_count": product.inventory_count,
        "status": product.status,
        "unit_price": _money(product.default_unit_price),
        "base_unit_cost": _money(product.base_unit_cost),
        "unit_cost": _money(product.total_unit_cost),
        "additional_unit_cost": _money(product.additional_unit_cost),
        "cost_components": [{"label": item.label, "amount": _money(item.amount)} for item in product.pricing_components],
        "photo_configured": bool(product.photo_path),
        "photo_available": bool(photo),
        "is_complete": bool(product.is_complete),
    }
    payload["revision"] = _record_revision(payload)
    payload["forecast"] = {
        "average_weekly_sales": forecast.average_weekly_sales if forecast else 0,
        "days_until_stockout": forecast.days_until_stockout if forecast else None,
        "needs_reorder": forecast.needs_reorder if forecast else product.inventory_count <= order_service.get_low_inventory_threshold(),
    }
    return payload


def search_products(query: str = "", limit: int = 30) -> list[dict[str, Any]]:
    term = query.strip().casefold()
    matches = []
    forecasts = {item.product_id: item for item in order_service.list_inventory_forecast(limit=100) if item.product_id is not None}
    for product in product_repository.list_products():
        searchable = " ".join((product.sku, product.name, product.description, product.status)).casefold()
        if term and term not in searchable:
            continue
        matches.append(_product_dto(product, forecasts.get(product.id)))
        if len(matches) >= min(max(limit, 1), 100):
            break
    return matches


def _decode_product_photo(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    upload = payload.get("file")
    if not isinstance(upload, dict):
        raise BridgeError("validation_failed", "Choose a product image.", HTTPStatus.BAD_REQUEST, {"file": "required"})
    try:
        content = base64.b64decode(str(upload.get("content_base64", "")), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise BridgeError("validation_failed", "The product image could not be read.", HTTPStatus.BAD_REQUEST, {"file": "invalid_content"}) from exc
    if not content:
        raise BridgeError("validation_failed", "The product image is empty.", HTTPStatus.BAD_REQUEST, {"file": "empty"})
    if len(content) > MAX_PRODUCT_PHOTO_BYTES:
        raise BridgeError("validation_failed", "Product images must be 8 MB or smaller.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"file": "too_large"})
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return content, ".png", "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return content, ".jpg", "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return content, ".gif", "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return content, ".webp", "image/webp"
    raise BridgeError("validation_failed", "Use a PNG, JPEG, GIF, or WebP product image.", HTTPStatus.BAD_REQUEST, {"file": "unsupported_type"})


def save_product_photo(product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    content, suffix, _content_type = _decode_product_photo(payload)
    with MUTATION_LOCK:
        product = product_repository.get_product_by_id(product_id)
        if product is None:
            raise BridgeError("product_not_found", "Product not found.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _product_dto(product)["revision"])
        media_root = get_storage_root() / "media" / "products"
        media_root.mkdir(parents=True, exist_ok=True)
        safe_sku = "".join(character.lower() if character.isalnum() else "-" for character in product.sku).strip("-") or "product"
        destination = media_root / f"{safe_sku}_{hashlib.sha256(content).hexdigest()[:16]}{suffix}"
        destination.write_bytes(content)
        previous = product.photo_path
        product.photo_path = str(destination.relative_to(get_storage_root()))
        try:
            saved = order_service.update_product(product)
        except Exception:
            destination.unlink(missing_ok=True)
            product.photo_path = previous
            raise
    return _product_dto(saved)


def delete_product_photo(product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with MUTATION_LOCK:
        product = product_repository.get_product_by_id(product_id)
        if product is None:
            raise BridgeError("product_not_found", "Product not found.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _product_dto(product)["revision"])
        product.photo_path = ""
        saved = order_service.update_product(product)
    return _product_dto(saved)


def download_product_photo(product_id: int) -> BinaryDownload:
    product = product_repository.get_product_by_id(product_id)
    if product is None:
        raise BridgeError("product_not_found", "Product not found.", HTTPStatus.NOT_FOUND)
    path = order_service.resolve_product_photo(product.photo_path)
    if path is None:
        raise BridgeError("file_missing", "The product image could not be found.", HTTPStatus.NOT_FOUND)
    return BinaryDownload(filename=path.name, content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", content=path.read_bytes())


def _vendor_dto(vendor: Any) -> dict[str, Any]:
    payload = {
        "id": vendor.id,
        "name": vendor.name,
        "contact_name": vendor.contact_name,
        "email": vendor.email,
        "phone": vendor.phone,
        "website": vendor.website,
        "account_number": vendor.account_number,
        "notes": vendor.notes,
        "preferred_payment_method": vendor.preferred_payment_method,
    }
    payload["revision"] = _record_revision(payload)
    return payload


def _vendor_workspace_dto(vendor: Any, materials: list[Any]) -> dict[str, Any]:
    linked = [material for material in materials if material.vendor_id == vendor.id]
    reorder_count = sum(material.quantity_on_hand <= material.reorder_point for material in linked)
    payload = _vendor_dto(vendor)
    payload.update(
        {
            "material_count": len(linked),
            "inventory_value": _money(sum(material.inventory_value for material in linked)),
            "reorder_count": reorder_count,
        }
    )
    return payload


def search_vendors(query: str = "", limit: int = 100) -> list[dict[str, Any]]:
    term = query.strip().casefold()
    materials = material_repository.list_materials()
    matches = []
    for vendor in vendor_repository.list_vendors():
        searchable = " ".join(
            (
                vendor.name,
                vendor.contact_name,
                vendor.email,
                vendor.phone,
                vendor.account_number,
                vendor.preferred_payment_method,
            )
        ).casefold()
        if term and term not in searchable:
            continue
        matches.append(_vendor_workspace_dto(vendor, materials))
        if len(matches) >= min(max(limit, 1), 250):
            break
    return matches


def _monthly_recurring_amount(amount: float, frequency: str) -> float:
    normalized = frequency.strip().casefold().replace("-", " ")
    factors = {
        "daily": 365 / 12,
        "weekly": 52 / 12,
        "biweekly": 26 / 12,
        "bi weekly": 26 / 12,
        "monthly": 1,
        "quarterly": 1 / 3,
        "yearly": 1 / 12,
        "annual": 1 / 12,
        "annually": 1 / 12,
    }
    return amount * factors.get(normalized, 1)


def _expense_revision(expense: Any) -> str:
    return _record_revision({
        "id": expense.id, "category": expense.category, "amount": _money(expense.amount),
        "expense_date": expense.expense_date.isoformat(), "description": expense.description,
        "payment_method": expense.payment_method, "vendor_id": expense.vendor_id,
        "is_recurring": expense.is_recurring, "recurring_id": expense.recurring_id,
        "document_id": expense.document_id, "tags": expense.tags, "notes": expense.notes,
    })


def _loss_revision(item: Any) -> str:
    return _record_revision({
        "id": item.id, "category": item.category, "amount": _money(item.amount),
        "loss_date": item.loss_date.isoformat(), "description": item.description,
        "details": item.details, "is_product_loss": item.is_product_loss,
        "recorded_by": item.recorded_by, "quantity": item.quantity, "unit": item.unit,
        "order_id": item.order_id, "order_item_id": item.order_item_id,
        "product_id": item.product_id, "material_id": item.material_id,
    })


def _recurring_revision(item: Any) -> str:
    return _record_revision({
        "id": item.id, "category": item.category, "amount": _money(item.amount),
        "frequency": item.frequency, "start_date": item.start_date.isoformat() if item.start_date else None,
        "end_date": item.end_date.isoformat() if item.end_date else None,
        "day_of_month": item.day_of_month,
        "next_occurrence": item.next_occurrence.isoformat() if item.next_occurrence else None,
        "auto_record": item.auto_record, "notes": item.notes, "vendor_id": item.vendor_id,
    })


def finance_workspace(limit: int = 200) -> dict[str, Any]:
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    upcoming_end = today + timedelta(days=30)
    vendors = {vendor.id: _vendor_dto(vendor) for vendor in vendor_repository.list_vendors()}
    recent = expense_repository.list_expenses(limit=min(max(limit, 1), 500))
    year_expenses = expense_repository.list_expenses(start_date=year_start, end_date=today)
    month_expenses = expense_repository.list_expenses(start_date=month_start, end_date=today)
    recurring = expense_repository.list_recurring_expenses()
    recent_losses = loss_repository.fetch_losses(limit=min(max(limit, 1), 500))
    year_losses = loss_repository.fetch_losses(start_date=year_start, end_date=today)
    month_losses = loss_repository.fetch_losses(start_date=month_start, end_date=today)

    category_totals: dict[str, dict[str, Any]] = {}
    for expense in year_expenses:
        category = expense.category.strip() or "Uncategorized"
        entry = category_totals.setdefault(category, {"name": category, "total": 0.0, "count": 0})
        entry["total"] += expense.amount
        entry["count"] += 1
    year_total = sum(expense.amount for expense in year_expenses)
    categories = []
    for entry in sorted(category_totals.values(), key=lambda item: item["total"], reverse=True):
        categories.append(
            {
                "name": entry["name"],
                "total": _money(entry["total"]),
                "count": entry["count"],
                "percent": round((entry["total"] / year_total * 100) if year_total else 0, 1),
            }
        )

    loss_category_totals: dict[str, dict[str, Any]] = {}
    for loss in year_losses:
        category = loss.category.strip() or "Uncategorized"
        entry = loss_category_totals.setdefault(category, {"name": category, "total": 0.0, "count": 0})
        entry["total"] += loss.amount
        entry["count"] += 1
    year_loss_total = sum(loss.amount for loss in year_losses)
    loss_categories = [
        {
            "name": entry["name"],
            "total": _money(entry["total"]),
            "count": entry["count"],
            "percent": round((entry["total"] / year_loss_total * 100) if year_loss_total else 0, 1),
        }
        for entry in sorted(loss_category_totals.values(), key=lambda item: item["total"], reverse=True)
    ]

    def expense_dto(expense: Any) -> dict[str, Any]:
        return {
            "id": expense.id,
            "category": expense.category,
            "amount": _money(expense.amount),
            "expense_date": expense.expense_date.isoformat(),
            "description": expense.description,
            "payment_method": expense.payment_method,
            "vendor_id": expense.vendor_id,
            "vendor": vendors.get(expense.vendor_id),
            "is_recurring": expense.is_recurring,
            "tags": expense.tags,
            "notes": expense.notes,
            "revision": _expense_revision(expense),
        }

    def recurring_dto(item: Any) -> dict[str, Any]:
        return {
            "id": item.id,
            "category": item.category,
            "amount": _money(item.amount),
            "frequency": item.frequency,
            "start_date": item.start_date.isoformat() if item.start_date else None,
            "end_date": item.end_date.isoformat() if item.end_date else None,
            "day_of_month": item.day_of_month,
            "next_occurrence": item.next_occurrence.isoformat() if item.next_occurrence else None,
            "auto_record": item.auto_record,
            "notes": item.notes,
            "vendor_id": item.vendor_id,
            "vendor": vendors.get(item.vendor_id),
            "revision": _recurring_revision(item),
        }

    def loss_dto(item: Any) -> dict[str, Any]:
        return {
            "id": item.id,
            "category": item.category,
            "amount": _money(item.amount),
            "loss_date": item.loss_date.isoformat(),
            "description": item.description,
            "details": item.details,
            "is_product_loss": item.is_product_loss,
            "recorded_by": item.recorded_by,
            "quantity": item.quantity,
            "unit": item.unit,
            "order_id": item.order_id,
            "product_id": item.product_id,
            "material_id": item.material_id,
            "product_name": item.product_name,
            "material_name": item.material_name,
            "revision": _loss_revision(item),
        }

    active_recurring = [item for item in recurring if not item.end_date or item.end_date >= today]
    upcoming_total = sum(
        item.amount
        for item in active_recurring
        if item.next_occurrence and today <= item.next_occurrence <= upcoming_end
    )
    return {
        "expenses": [expense_dto(expense) for expense in recent],
        "recurring": [recurring_dto(item) for item in recurring],
        "losses": [loss_dto(item) for item in recent_losses],
        "categories": categories,
        "loss_categories": loss_categories,
        "metrics": {
            "year_to_date_expenses": _money(year_total),
            "month_expenses": _money(sum(expense.amount for expense in month_expenses)),
            "recurring_monthly_estimate": _money(
                sum(_monthly_recurring_amount(item.amount, item.frequency) for item in active_recurring)
            ),
            "upcoming_30_days": _money(upcoming_total),
            "category_count": len(category_totals),
            "year_to_date_losses": _money(year_loss_total),
            "month_losses": _money(sum(loss.amount for loss in month_losses)),
            "loss_category_count": len(loss_category_totals),
        },
    }


def _report_period(period: str) -> tuple[Optional[date], date, str]:
    today = date.today()
    normalized = period.strip().casefold()
    if normalized == "this_month":
        return today.replace(day=1), today, "This month"
    if normalized == "this_quarter":
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=quarter_month, day=1), today, "This quarter"
    if normalized == "last_90_days":
        return today - timedelta(days=89), today, "Last 90 days"
    if normalized == "all_time":
        return None, today, "All time"
    return today.replace(month=1, day=1), today, "This year"


def reports_workspace(period: str = "this_year") -> dict[str, Any]:
    start, end, label = _report_period(period)
    orders = order_repository.fetch_order_report(start, end)
    products = (
        order_repository.get_product_sales_summary(start, end)
        if start
        else order_repository.fetch_product_sales_summary()
    )
    expenses = expense_repository.list_expenses(start_date=start, end_date=end)
    losses = loss_repository.fetch_losses(start_date=start, end_date=end)
    revenue = sum(order.total_amount for order in orders)
    cost = sum(order.total_cost for order in orders)
    gross_profit = revenue - cost
    expense_total = sum(item.amount for item in expenses)
    loss_total = sum(item.amount for item in losses)
    net = gross_profit - expense_total - loss_total

    previous_revenue = 0.0
    if start:
        window_days = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=window_days - 1)
        previous_revenue = sum(
            order.total_amount
            for order in order_repository.fetch_order_report(previous_start, previous_end)
        )
    revenue_change = (
        ((revenue - previous_revenue) / previous_revenue * 100)
        if previous_revenue
        else (100.0 if revenue else 0.0)
    )

    customer_totals: dict[str, dict[str, Any]] = {}
    status_totals: dict[str, dict[str, Any]] = {}
    trend_totals: dict[str, dict[str, Any]] = {}
    daily_buckets = bool(start and (end - start).days <= 45)
    for order in orders:
        customer = customer_totals.setdefault(
            order.customer_name,
            {"name": order.customer_name, "orders": 0, "revenue": 0.0, "profit": 0.0},
        )
        customer["orders"] += 1
        customer["revenue"] += order.total_amount
        customer["profit"] += order.profit
        status = status_totals.setdefault(order.status, {"status": order.status, "count": 0, "revenue": 0.0})
        status["count"] += 1
        status["revenue"] += order.total_amount
        bucket_key = order.order_date.isoformat() if daily_buckets else order.order_date.strftime("%Y-%m")
        bucket_label = order.order_date.strftime("%b %d") if daily_buckets else order.order_date.strftime("%b %Y")
        bucket = trend_totals.setdefault(bucket_key, {"label": bucket_label, "revenue": 0.0, "profit": 0.0})
        bucket["revenue"] += order.total_amount
        bucket["profit"] += order.profit

    return {
        "period": {
            "key": period if period in {"this_month", "this_quarter", "this_year", "last_90_days", "all_time"} else "this_year",
            "label": label,
            "start": start.isoformat() if start else None,
            "end": end.isoformat(),
        },
        "metrics": {
            "revenue": _money(revenue),
            "revenue_change": round(revenue_change, 1),
            "gross_profit": _money(gross_profit),
            "gross_margin": round((gross_profit / revenue * 100) if revenue else 0, 1),
            "expenses": _money(expense_total),
            "losses": _money(loss_total),
            "net_after_overhead": _money(net),
            "order_count": len(orders),
            "average_order": _money(revenue / len(orders) if orders else 0),
        },
        "trend": [
            {"label": item["label"], "revenue": _money(item["revenue"]), "profit": _money(item["profit"])}
            for _, item in sorted(trend_totals.items())[-12:]
        ],
        "products": [
            {
                "name": item.product_name,
                "quantity": item.total_quantity,
                "revenue": _money(item.total_sales),
                "profit": _money(item.total_profit),
                "margin": round(item.margin * 100, 1),
            }
            for item in products[:8]
        ],
        "customers": [
            {
                "name": item["name"],
                "orders": item["orders"],
                "revenue": _money(item["revenue"]),
                "profit": _money(item["profit"]),
            }
            for item in sorted(customer_totals.values(), key=lambda value: value["revenue"], reverse=True)[:8]
        ],
        "fulfillment": [
            {"status": item["status"], "count": item["count"], "revenue": _money(item["revenue"])}
            for item in sorted(status_totals.values(), key=lambda value: value["count"], reverse=True)
        ],
        "recent_orders": [
            {
                "id": item.order_id,
                "number": item.order_number,
                "customer": item.customer_name,
                "date": item.order_date.isoformat(),
                "status": item.status,
                "revenue": _money(item.total_amount),
                "profit": _money(item.profit),
            }
            for item in orders[:8]
        ],
    }


def about_workspace() -> dict[str, str]:
    return {
        "app_name": "HustleNest",
        "app_version": APP_VERSION,
        "browser_version": "0.35.0",
        "repository_url": REPOSITORY_URL,
        "releases_url": RELEASES_URL,
        "runtime": "Local Python backend + browser UI",
    }


def _safe_download_stem(value: str, fallback: str = "HustleNest") -> str:
    stem = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value.strip())
    return stem.strip("_") or fallback


def _comparison_periods(mode: str) -> tuple[date, date, date, date, str, str]:
    today = date.today()
    if mode == "month_vs_month":
        current_start = today.replace(day=1)
        previous_end = current_start - timedelta(days=1)
        return current_start, today, previous_end.replace(day=1), previous_end, "This Month", "Last Month"
    if mode == "quarter_vs_quarter":
        quarter = (today.month - 1) // 3
        current_start = date(today.year, quarter * 3 + 1, 1)
        previous_end = current_start - timedelta(days=1)
        previous_quarter = (previous_end.month - 1) // 3
        previous_start = date(previous_end.year, previous_quarter * 3 + 1, 1)
        return current_start, today, previous_start, previous_end, "This Quarter", "Last Quarter"
    return date(today.year, 1, 1), today, date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), str(today.year), str(today.year - 1)


def report_download(query: dict[str, list[str]]) -> BinaryDownload:
    kind = query.get("kind", ["orders_csv"])[0].strip().casefold()
    period = query.get("period", ["this_year"])[0].strip().casefold()
    start, end, label = _report_period(period)
    effective_start = start or date(2000, 1, 1)
    settings = settings_repository.get_app_settings()
    business = _safe_download_stem(settings.business_name)
    label_stem = _safe_download_stem(label, "Report")

    with TemporaryDirectory(prefix="hustlenest-report-") as directory:
        root = Path(directory)
        if kind == "orders_csv":
            filename = f"{business}_Orders_{label_stem}.csv"
            path = order_service.export_order_report(order_repository.fetch_order_report(start, end), str(root / filename))
            content_type = "text/csv; charset=utf-8"
        elif kind in {"tax_csv", "tax_pdf"}:
            extension = "csv" if kind == "tax_csv" else "pdf"
            filename = f"{business}_SalesTax_{label_stem}.{extension}"
            exporter = order_service.export_sales_tax_summary_csv if kind == "tax_csv" else order_service.export_sales_tax_summary_pdf
            path = exporter(effective_start, end, str(root / filename), period_label=label)
            content_type = "text/csv; charset=utf-8" if extension == "csv" else "application/pdf"
        else:
            report_labels = {
                "sales_pdf": "SalesReport",
                "inventory_pdf": "InventoryReport",
                "pnl_pdf": "ProfitLoss",
                "customer_pdf": "CustomerReport",
                "comparison_pdf": "Comparison",
            }
            if kind not in report_labels:
                raise BridgeError("invalid_report_kind", "Choose a valid report export.", HTTPStatus.BAD_REQUEST)
            if kind == "sales_pdf":
                html = report_service.generate_sales_report_html(effective_start, end, settings, include_details=True)
            elif kind == "inventory_pdf":
                html = report_service.generate_inventory_report_html(settings)
            elif kind == "pnl_pdf":
                html = report_service.generate_pnl_report_html(effective_start, end, settings)
            elif kind == "customer_pdf":
                html = report_service.generate_customer_report_html(effective_start, end, settings)
            else:
                comparison = query.get("comparison", ["year_vs_year"])[0].strip().casefold()
                p1_start, p1_end, p2_start, p2_end, p1_label, p2_label = _comparison_periods(comparison)
                html = report_service.generate_comparison_report_html(p1_start, p1_end, p2_start, p2_end, p1_label, p2_label, settings)
            filename = f"{business}_{report_labels[kind]}_{label_stem}.pdf"
            path = root / filename
            order_service._write_pdf_from_html(html, path)
            content_type = "application/pdf"
        return BinaryDownload(filename=path.name, content_type=content_type, content=path.read_bytes())


def home_workspace() -> dict[str, Any]:
    today = date.today()
    report = reports_workspace("this_year")
    finance = finance_workspace(25)
    orders = list_orders(100)
    materials = search_materials("", 250)
    followups = crm_service.list_pending_followups(limit=8, days_ahead=14)
    goals = goal_service.evaluate_goals()
    cash_flow = finance_service.summarize_cash_flow(30)
    priorities: list[dict[str, Any]] = []

    for order in orders:
        reasons = order["attention_reasons"]
        if not reasons:
            continue
        overdue = "overdue" in reasons or "due_today" in reasons
        priorities.append(
            {
                "key": f"order:{order['id']}",
                "kind": "order",
                "severity": "critical" if overdue else "warning",
                "title": f"{order['number']} · {order['customer_name']}",
                "detail": "Order is overdue or due today." if overdue else "Payment is still outstanding.",
                "value": order["total"],
                "target_view": "orders",
                "target_id": order["id"],
            }
        )
    for material in materials:
        if material["stock_status"] == "healthy":
            continue
        priorities.append(
            {
                "key": f"material:{material['id']}",
                "kind": "material",
                "severity": "critical" if material["stock_status"] == "reorder" else "warning",
                "title": material["name"],
                "detail": f"{material['quantity_on_hand']:g} {material['unit_of_measure'] or 'units'} on hand · reorder at {material['reorder_point']:g}.",
                "value": None,
                "target_view": "materials",
                "target_id": material["id"],
            }
        )
    for contact in followups:
        days = (contact.next_follow_up - today).days if contact.next_follow_up else 0
        status = f"overdue by {-days} days" if days < 0 else ("due today" if days == 0 else f"due in {days} days")
        priorities.append(
            {
                "key": f"customer:{contact.id}",
                "kind": "customer",
                "severity": "critical" if days < 0 else "info",
                "title": contact.customer_name,
                "detail": f"Customer follow-up {status}.",
                "value": None,
                "target_view": "customers",
                "target_id": contact.id,
            }
        )
    for recurring in finance["recurring"]:
        occurrence = recurring["next_occurrence"]
        if not occurrence or occurrence > (today + timedelta(days=30)).isoformat():
            continue
        priorities.append(
            {
                "key": f"recurring:{recurring['id']}",
                "kind": "finance",
                "severity": "info",
                "title": recurring["category"],
                "detail": f"Recurring {recurring['frequency'].lower()} cost due {occurrence}.",
                "value": recurring["amount"],
                "target_view": "finance",
                "target_id": recurring["id"],
            }
        )
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    priorities.sort(key=lambda item: (severity_rank[item["severity"]], item["title"].casefold()))

    return {
        "metrics": {
            "open_orders": sum(order["status"] != "Shipped" for order in orders),
            "revenue_ytd": report["metrics"]["revenue"],
            "net_ytd": report["metrics"]["net_after_overhead"],
            "cash_projection_30": _money(cash_flow.net_projection),
            "inventory_value": _money(sum(float(material["inventory_value"]) for material in materials)),
        },
        "priorities": priorities[:12],
        "goals": [
            {
                "id": goal.id,
                "name": goal.name,
                "metric_type": goal.metric_type,
                "current_value": _money(goal.current_value) if goal.metric_type.casefold() in {"revenue", "sales", "profit", "expenses", "losses"} else str(round(goal.current_value, 1)),
                "target_value": _money(goal.target_value) if goal.metric_type.casefold() in {"revenue", "sales", "profit", "expenses", "losses"} else str(round(goal.target_value, 1)),
                "progress_percent": round(goal.progress_ratio * 100, 1),
                "status": goal.status,
                "end_date": goal.end_date.isoformat() if goal.end_date else None,
                "owner": goal.owner,
            }
            for goal in goals[:6]
        ],
        "sales_trend": report["trend"],
        "fulfillment": report["fulfillment"],
        "recent_orders": report["recent_orders"][:6],
        "counts": {
            "customers": len(search_customers("", 250)),
            "products": len(search_products("", 100)),
            "materials_needing_attention": sum(material["stock_status"] != "healthy" for material in materials),
            "priorities": len(priorities),
        },
    }


def geography_workspace() -> dict[str, Any]:
    destinations = order_service.list_order_destinations()
    orders = order_repository.fetch_orders(200)
    order_index = {order.order_number: order for order in orders}
    state_counts: dict[str, int] = {}
    payload: list[dict[str, Any]] = []
    for destination in destinations:
        state = destination.state.strip().upper()
        state_counts[state] = state_counts.get(state, 0) + destination.count
        related = [order_index[number] for number in destination.order_numbers if number in order_index]
        payload.append({
            "key": f"{destination.city.casefold()}:{state.casefold()}",
            "city": destination.city,
            "state": state,
            "state_name": US_STATE_NAMES.get(state, state),
            "count": destination.count,
            "order_numbers": destination.order_numbers,
            "orders": [
                {"id": order.id, "number": order.order_number, "customer": order.customer_name, "status": order.status, "total": _money(order.display_total)}
                for order in related[:20]
            ],
        })
    states = [
        {"code": code, "name": US_STATE_NAMES.get(code, code), "count": count}
        for code, count in sorted(state_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    settings = settings_repository.get_app_settings()
    return {
        "destinations": payload,
        "states": states,
        "home": {
            "city": settings.dashboard_home_city,
            "state": settings.dashboard_home_state.strip().upper(),
            "configured": bool(settings.dashboard_home_city.strip() and settings.dashboard_home_state.strip()),
        },
        "metrics": {
            "mapped_orders": sum(destination.count for destination in destinations),
            "destinations": len(destinations),
            "states": len(states),
            "top_state": states[0]["name"] if states else None,
        },
    }


def _deleted_item_dto(item: Any) -> dict[str, Any]:
    payload = {
        "id": item.id,
        "type": item.item_type,
        "name": item.name,
        "details": item.details,
        "deleted_at": item.deleted_at.isoformat(),
    }
    payload["revision"] = _record_revision(payload)
    return payload


def trash_workspace() -> dict[str, Any]:
    items = [_deleted_item_dto(item) for item in soft_delete_service.list_all_deleted_items()]
    order_count = sum(item["type"] == "order" for item in items)
    product_count = len(items) - order_count
    return {
        "items": items,
        "metrics": {
            "total": len(items),
            "orders": order_count,
            "products": product_count,
        },
    }


def move_record_to_trash(item_type: str, item_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with MUTATION_LOCK:
        if item_type == "order":
            order = order_repository.fetch_order(item_id)
            if order is None:
                raise BridgeError("order_not_found", "Order not found.", HTTPStatus.NOT_FOUND)
            expected_status = str(payload.get("expected_status", "")).strip()
            if expected_status and expected_status != order.status:
                raise BridgeError("record_conflict", "This order changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
            moved = soft_delete_service.soft_delete_order(item_id)
            label = order.order_number
        elif item_type == "product":
            product = product_repository.get_product_by_id(item_id)
            if product is None:
                raise BridgeError("product_not_found", "Product not found.", HTTPStatus.NOT_FOUND)
            _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _product_dto(product)["revision"])
            moved = soft_delete_service.soft_delete_product(item_id)
            label = product.name
        else:
            raise BridgeError("invalid_trash_type", "Only orders and products can be moved to trash.", HTTPStatus.BAD_REQUEST)
        if not moved:
            raise BridgeError("record_conflict", "This item is no longer available. Refresh and try again.", HTTPStatus.CONFLICT)
    return {"id": item_id, "type": item_type, "name": label, "trashed": True}


def mutate_trash_item(item_type: str, item_id: int, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if item_type not in {"order", "product"}:
        raise BridgeError("invalid_trash_type", "Only orders and products can be managed in trash.", HTTPStatus.BAD_REQUEST)
    with MUTATION_LOCK:
        current = next(
            (item for item in soft_delete_service.list_all_deleted_items() if item.item_type == item_type and item.id == item_id),
            None,
        )
        if current is None:
            raise BridgeError("trash_item_not_found", "This item is no longer in trash.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _deleted_item_dto(current)["revision"])
        if action == "restore":
            changed = soft_delete_service.restore_order(item_id) if item_type == "order" else soft_delete_service.restore_product(item_id)
        elif action == "delete":
            if payload.get("confirm") is not True:
                raise BridgeError("confirmation_required", "Confirm permanent deletion before continuing.", HTTPStatus.BAD_REQUEST)
            changed = soft_delete_service.permanent_delete_order(item_id) if item_type == "order" else soft_delete_service.permanent_delete_product(item_id)
        else:
            raise BridgeError("invalid_trash_action", "Trash action is invalid.", HTTPStatus.BAD_REQUEST)
        if not changed:
            raise BridgeError("record_conflict", "This item changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    return {"id": item_id, "type": item_type, "action": action}


def empty_browser_trash(payload: dict[str, Any]) -> dict[str, Any]:
    if str(payload.get("confirmation", "")).strip().upper() != "EMPTY TRASH":
        raise BridgeError("confirmation_required", "Type EMPTY TRASH to permanently delete every item.", HTTPStatus.BAD_REQUEST, {"confirmation": "required"})
    with MUTATION_LOCK:
        current_count = soft_delete_service.get_deleted_count()
        try:
            expected_count = int(payload.get("expected_count", -1))
        except (TypeError, ValueError) as exc:
            raise BridgeError("validation_failed", "Trash count is invalid.", HTTPStatus.BAD_REQUEST) from exc
        if expected_count != current_count:
            raise BridgeError("record_conflict", "Trash changed in another window. Refresh and review it again.", HTTPStatus.CONFLICT)
        orders, products = soft_delete_service.empty_trash()
    return {"deleted": orders + products, "orders": orders, "products": products}


def _goal_revision(goal: BusinessGoal) -> str:
    return _record_revision({
        "id": goal.id,
        "name": goal.name,
        "metric_type": goal.metric_type,
        "target_value": goal.target_value,
        "start_date": goal.start_date.isoformat() if goal.start_date else None,
        "end_date": goal.end_date.isoformat() if goal.end_date else None,
        "current_value": None if goal.auto_calculate else goal.current_value,
        "owner": goal.owner,
        "progress_notes": goal.progress_notes,
        "threshold_warning": goal.threshold_warning,
        "threshold_critical": goal.threshold_critical,
        "auto_calculate": goal.auto_calculate,
        "checkpoints": [
            {
                "id": checkpoint.id,
                "date": checkpoint.checkpoint_date.isoformat(),
                "actual": checkpoint.actual_value,
                "forecast": checkpoint.forecast_value,
                "notes": checkpoint.notes,
            }
            for checkpoint in goal.checkpoints
        ],
    })


def _goal_dto(goal: BusinessGoal) -> dict[str, Any]:
    currency_metric = goal.metric_type.casefold() in {"revenue", "sales", "profit", "expenses", "losses"}
    return {
        "id": goal.id,
        "name": goal.name,
        "metric_type": goal.metric_type,
        "target_value": _money(goal.target_value),
        "current_value": _money(goal.current_value),
        "display_target": _money(goal.target_value) if currency_metric else str(round(goal.target_value, 1)),
        "display_current": _money(goal.current_value) if currency_metric else str(round(goal.current_value, 1)),
        "start_date": goal.start_date.isoformat() if goal.start_date else None,
        "end_date": goal.end_date.isoformat() if goal.end_date else None,
        "owner": goal.owner,
        "progress_notes": goal.progress_notes,
        "threshold_warning": goal.threshold_warning,
        "threshold_critical": goal.threshold_critical,
        "auto_calculate": goal.auto_calculate,
        "progress_percent": round(goal.progress_ratio * 100, 1),
        "status": goal.status,
        "checkpoints": [
            {
                "id": checkpoint.id,
                "checkpoint_date": checkpoint.checkpoint_date.isoformat(),
                "actual_value": _money(checkpoint.actual_value),
                "forecast_value": _money(checkpoint.forecast_value),
                "notes": checkpoint.notes,
            }
            for checkpoint in reversed(goal.checkpoints)
        ],
        "revision": _goal_revision(goal),
    }


def goals_workspace() -> dict[str, Any]:
    return {
        "goals": [_goal_dto(goal) for goal in goal_service.evaluate_goals()],
        "metric_options": ["revenue", "sales", "profit", "orders", "expenses", "losses", "crm-followups"],
    }


def _goal_from_values(values: dict[str, Any], *, goal_id: Optional[int] = None) -> BusinessGoal:
    metric = _required_text(values, "metric_type", "Metric", 40).casefold()
    if metric not in GOAL_METRICS:
        raise BridgeError("validation_failed", "Choose a supported goal metric.", HTTPStatus.BAD_REQUEST, {"metric_type": "invalid_choice"})
    start_date = _date_field(values, "start_date", "Start date", required=False)
    end_date = _date_field(values, "end_date", "End date", required=False)
    if start_date and end_date and end_date < start_date:
        raise BridgeError("validation_failed", "End date cannot be before the start date.", HTTPStatus.BAD_REQUEST, {"end_date": "before_start"})
    warning = _nonnegative_number(values, "threshold_warning", "Warning threshold")
    critical = _nonnegative_number(values, "threshold_critical", "Critical threshold")
    if warning > 1 or critical > 1 or critical > warning:
        raise BridgeError("validation_failed", "Thresholds must be between 0 and 1, with critical no higher than warning.", HTTPStatus.BAD_REQUEST, {"threshold_critical": "invalid_thresholds"})
    auto_calculate = _setting_bool(values.get("auto_calculate", True), "auto_calculate")
    return BusinessGoal(
        id=goal_id,
        name=_required_text(values, "name", "Goal name", 200),
        metric_type=metric,
        target_value=_nonnegative_number(values, "target_value", "Target value", positive=True),
        start_date=start_date,
        end_date=end_date,
        current_value=0 if auto_calculate else _nonnegative_number(values, "current_value", "Current value"),
        owner=_optional_text(values, "owner", 160),
        progress_notes=_optional_text(values, "progress_notes", 2000),
        threshold_warning=warning,
        threshold_critical=critical,
        auto_calculate=auto_calculate,
    )


def save_goal_from_browser(payload: dict[str, Any], goal_id: Optional[int] = None) -> dict[str, Any]:
    values = payload.get("values")
    if not isinstance(values, dict):
        raise BridgeError("validation_failed", "Goal values are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})
    with MUTATION_LOCK:
        existing = goal_repository.get_goal(goal_id) if goal_id else None
        if goal_id and existing is None:
            raise BridgeError("not_found", "Goal not found.", HTTPStatus.NOT_FOUND)
        if existing:
            _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _goal_revision(existing))
        goal = _goal_from_values(values, goal_id=goal_id)
        if existing:
            goal.checkpoints = existing.checkpoints
        saved_id = goal_repository.save_goal(goal)
    saved = next(item for item in goal_service.evaluate_goals() if item.id == saved_id)
    return _goal_dto(saved)


def add_goal_checkpoint(goal_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    values = payload.get("values")
    if not isinstance(values, dict):
        raise BridgeError("validation_failed", "Checkpoint values are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})
    checkpoint_date = _date_field(values, "checkpoint_date", "Checkpoint date")
    assert checkpoint_date is not None
    with MUTATION_LOCK:
        goal = goal_repository.get_goal(goal_id)
        if goal is None:
            raise BridgeError("not_found", "Goal not found.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _goal_revision(goal))
        goal_repository.save_checkpoint(GoalCheckpoint(
            id=None,
            goal_id=goal_id,
            checkpoint_date=checkpoint_date,
            actual_value=_nonnegative_number(values, "actual_value", "Actual value"),
            forecast_value=_nonnegative_number(values, "forecast_value", "Forecast value"),
            notes=_optional_text(values, "notes", 1000),
        ))
    saved = next(item for item in goal_service.evaluate_goals() if item.id == goal_id)
    return _goal_dto(saved)


def delete_goal_from_browser(goal_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with MUTATION_LOCK:
        goal = goal_repository.get_goal(goal_id)
        if goal is None:
            raise BridgeError("not_found", "Goal not found.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _goal_revision(goal))
        goal_repository.delete_goal(goal_id)
    return {"id": goal_id, "deleted": True}


def _document_entity(entity_type: str, entity_id: Optional[int]) -> dict[str, Any]:
    normalized = entity_type.strip().casefold().rstrip("s")
    if entity_id is None:
        return {"type": normalized or "general", "id": None, "label": "General business", "detail": "Unlinked document", "target_view": None}
    if normalized == "order":
        record = order_repository.fetch_order(entity_id)
        if record:
            return {"type": "order", "id": entity_id, "label": record.order_number, "detail": record.customer_name, "target_view": "orders"}
    if normalized in {"customer", "contact", "crm"}:
        record = crm_repository.get_contact(entity_id)
        if record:
            return {"type": "customer", "id": entity_id, "label": record.customer_name, "detail": record.company or record.email, "target_view": "customers"}
    if normalized == "product":
        record = product_repository.get_product_by_id(entity_id)
        if record:
            return {"type": "product", "id": entity_id, "label": record.name, "detail": record.sku, "target_view": "products"}
    if normalized == "material":
        record = material_repository.get_material(entity_id)
        if record:
            return {"type": "material", "id": entity_id, "label": record.name, "detail": record.sku, "target_view": "materials"}
    if normalized == "vendor":
        record = vendor_repository.get_vendor(entity_id)
        if record:
            return {"type": "vendor", "id": entity_id, "label": record.name, "detail": record.contact_name, "target_view": "vendors"}
    return {"type": normalized or "general", "id": entity_id, "label": f"{entity_type or 'Record'} #{entity_id}", "detail": "Linked record unavailable", "target_view": None}


def _document_revision(document: DocumentRecord) -> str:
    return _record_revision({
        "id": document.id,
        "entity_type": document.entity_type,
        "entity_id": document.entity_id,
        "file_path": document.file_path,
        "category": document.category,
        "description": document.description,
        "tags": document.tags,
        "stored_at": document.stored_at,
        "checksum": document.checksum,
        "created_at": document.created_at.isoformat() if document.created_at else None,
    })


def _managed_documents_root() -> Path:
    root = get_storage_root() / "documents"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_managed_document(path: Path) -> bool:
    try:
        path.resolve().relative_to(_managed_documents_root().resolve())
        return True
    except (OSError, ValueError):
        return False


def _validate_document_entity(entity_type: str, entity_id: Optional[int]) -> tuple[str, Optional[int]]:
    normalized = entity_type.strip().casefold().rstrip("s") or "general"
    if normalized == "general":
        return normalized, None
    if normalized not in {"order", "customer", "product", "material", "vendor"} or entity_id is None:
        raise BridgeError("validation_failed", "Choose a valid business record.", HTTPStatus.BAD_REQUEST, {"entity_id": "invalid_relationship"})
    exists = {
        "order": lambda: order_repository.fetch_order(entity_id),
        "customer": lambda: crm_repository.get_contact(entity_id),
        "product": lambda: product_repository.get_product_by_id(entity_id),
        "material": lambda: material_repository.get_material(entity_id),
        "vendor": lambda: vendor_repository.get_vendor(entity_id),
    }[normalized]()
    if exists is None:
        raise BridgeError("validation_failed", "The linked record no longer exists.", HTTPStatus.BAD_REQUEST, {"entity_id": "not_found"})
    return normalized, entity_id


def _document_values(values: dict[str, Any]) -> tuple[str, Optional[int], str, str, list[str]]:
    entity_type, entity_id = _validate_document_entity(_optional_text(values, "entity_type", 40), _optional_id(values, "entity_id"))
    category = _required_text(values, "category", "Category", 120)
    raw_tags = values.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = raw_tags.split(",")
    if not isinstance(raw_tags, list):
        raise BridgeError("validation_failed", "Tags must be a list.", HTTPStatus.BAD_REQUEST, {"tags": "invalid_list"})
    tags = list(dict.fromkeys(str(tag).strip()[:80] for tag in raw_tags if str(tag).strip()))[:20]
    return entity_type, entity_id, category, _optional_text(values, "description", 1000), tags


def create_document_from_browser(payload: dict[str, Any]) -> dict[str, Any]:
    values = payload.get("values")
    upload = payload.get("file")
    if not isinstance(values, dict) or not isinstance(upload, dict):
        raise BridgeError("validation_failed", "Document details and a file are required.", HTTPStatus.BAD_REQUEST, {"file": "required"})
    original_name = Path(str(upload.get("name", ""))).name.strip()
    if not original_name or original_name in {".", ".."}:
        raise BridgeError("validation_failed", "Choose a file to upload.", HTTPStatus.BAD_REQUEST, {"file": "required"})
    try:
        content = base64.b64decode(str(upload.get("content_base64", "")), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise BridgeError("validation_failed", "The uploaded file could not be read.", HTTPStatus.BAD_REQUEST, {"file": "invalid_content"}) from exc
    if not content:
        raise BridgeError("validation_failed", "The uploaded file is empty.", HTTPStatus.BAD_REQUEST, {"file": "empty"})
    if len(content) > MAX_DOCUMENT_BYTES:
        raise BridgeError("validation_failed", "Files must be 20 MB or smaller.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"file": "too_large"})
    entity_type, entity_id, category, description, tags = _document_values(values)
    safe_stem = "".join(character if character.isalnum() or character in {"-", "_", " "} else "_" for character in Path(original_name).stem).strip()[:120] or "document"
    safe_suffix = "".join(character for character in Path(original_name).suffix.lower() if character.isalnum() or character == ".")[:16]
    digest = hashlib.sha256(content).hexdigest()
    with MUTATION_LOCK:
        destination = _managed_documents_root() / f"{safe_stem}{safe_suffix}"
        sequence = 2
        while destination.exists():
            destination = _managed_documents_root() / f"{safe_stem} ({sequence}){safe_suffix}"
            sequence += 1
        destination.write_bytes(content)
        try:
            document_id = document_repository.save_document(DocumentRecord(
                id=None, entity_type=entity_type, entity_id=entity_id, file_path=str(destination),
                category=category, description=description, tags=tags, stored_at="managed-local", checksum=digest,
            ))
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return next(item for item in documents_workspace()["documents"] if item["id"] == document_id)


def update_document_from_browser(document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    values = payload.get("values")
    if not isinstance(values, dict):
        raise BridgeError("validation_failed", "Document details are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})
    entity_type, entity_id, category, description, tags = _document_values(values)
    with MUTATION_LOCK:
        document = document_repository.get_document(document_id)
        if document is None:
            raise BridgeError("not_found", "Document not found.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _document_revision(document))
        document.entity_type = entity_type
        document.entity_id = entity_id
        document.category = category
        document.description = description
        document.tags = tags
        document_repository.save_document(document)
    return next(item for item in documents_workspace()["documents"] if item["id"] == document_id)


def download_document(document_id: int) -> BinaryDownload:
    document = document_repository.get_document(document_id)
    if document is None:
        raise BridgeError("not_found", "Document not found.", HTTPStatus.NOT_FOUND)
    path = Path(document.file_path).expanduser()
    if not path.is_file():
        raise BridgeError("file_missing", "The saved file could not be found.", HTTPStatus.NOT_FOUND)
    return BinaryDownload(filename=path.name, content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", content=path.read_bytes())


def delete_document_from_browser(document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with MUTATION_LOCK:
        document = document_repository.get_document(document_id)
        if document is None:
            raise BridgeError("not_found", "Document not found.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _document_revision(document))
        path = Path(document.file_path).expanduser()
        delete_file = _setting_bool(payload.get("delete_file", False), "delete_file")
        if delete_file and not _is_managed_document(path):
            raise BridgeError("unmanaged_file", "Only files uploaded into HustleNest can be deleted here.", HTTPStatus.BAD_REQUEST)
        document_repository.delete_document(document_id)
        file_deleted = False
        if delete_file and path.is_file():
            try:
                path.unlink()
                file_deleted = True
            except OSError:
                LOGGER.warning("Unable to remove managed document file %s", path)
    return {"id": document_id, "deleted": True, "file_deleted": file_deleted}


def documents_workspace() -> dict[str, Any]:
    documents = document_repository.list_documents()
    categories: dict[str, int] = {}
    entity_counts: dict[str, int] = {}
    payload = []
    missing_count = 0
    linked_count = 0
    for document in documents:
        file_path = Path(document.file_path).expanduser()
        try:
            exists = file_path.is_file()
            size_bytes = file_path.stat().st_size if exists else None
        except OSError:
            exists = False
            size_bytes = None
        if not exists:
            missing_count += 1
        if document.entity_id is not None:
            linked_count += 1
        category = document.category.strip() or "Uncategorized"
        categories[category] = categories.get(category, 0) + 1
        entity = _document_entity(document.entity_type, document.entity_id)
        entity_counts[entity["type"]] = entity_counts.get(entity["type"], 0) + 1
        payload.append(
            {
                "id": document.id,
                "name": file_path.name or document.file_path,
                "extension": file_path.suffix.lstrip(".").upper() or "FILE",
                "path": document.file_path,
                "exists": exists,
                "size_bytes": size_bytes,
                "category": category,
                "description": document.description,
                "tags": document.tags,
                "stored_at": document.stored_at,
                "checksum": document.checksum,
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "managed": _is_managed_document(file_path),
                "revision": _document_revision(document),
                "entity": entity,
            }
        )
    return {
        "documents": payload,
        "categories": [{"name": name, "count": count} for name, count in sorted(categories.items(), key=lambda item: (-item[1], item[0].casefold()))],
        "entity_types": [{"name": name, "count": count} for name, count in sorted(entity_counts.items(), key=lambda item: (-item[1], item[0]))],
        "metrics": {"total": len(payload), "linked": linked_count, "missing": missing_count, "category_count": len(categories)},
    }


def _dashboard_section_settings() -> list[dict[str, Any]]:
    try:
        raw = json.loads(settings_repository.get_setting("dashboard_sections_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return [
        {
            "key": key,
            "label": label,
            "visible": bool(raw.get(key, {}).get("visible", True)) if isinstance(raw.get(key, {}), dict) else True,
            "collapsed": bool(raw.get(key, {}).get("collapsed", False)) if isinstance(raw.get(key, {}), dict) else False,
        }
        for key, label in DASHBOARD_SECTIONS.items()
    ]


def _resolve_dashboard_logo(path_value: str) -> Optional[Path]:
    raw = (path_value or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = get_storage_root() / path
    try:
        resolved = path.resolve()
    except OSError:
        return None
    return resolved if resolved.is_file() else None


def _profile_initials(display_name: str) -> str:
    words = [word for word in display_name.replace("-", " ").split() if word]
    if not words:
        return "?"
    return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()


def settings_workspace() -> dict[str, Any]:
    settings = settings_repository.get_app_settings()
    theme = (settings_repository.get_setting("app_theme") or "light").strip().casefold()
    if theme == "terminal-green":
        theme = "glass"
    if theme not in APPEARANCE_THEMES:
        theme = "light"
    try:
        text_scale = float(settings_repository.get_setting("browser_text_scale") or "1")
    except (TypeError, ValueError):
        text_scale = 1.0
    if not isfinite(text_scale) or text_scale not in APPEARANCE_TEXT_SCALES:
        text_scale = 1.0
    address = ", ".join(
        part
        for part in (
            settings.invoice_street,
            " ".join(part for part in (settings.invoice_city, settings.invoice_state, settings.invoice_zip) if part),
        )
        if part
    )
    home_location = ", ".join(part for part in (settings.dashboard_home_city, settings.dashboard_home_state) if part)
    invoice_fields = (
        settings.invoice_street,
        settings.invoice_city,
        settings.invoice_state,
        settings.invoice_zip,
        settings.invoice_phone,
        settings.invoice_contact_name,
        settings.invoice_contact_email,
    )
    configured_sections = sum(
        (
            bool(settings.business_name),
            any(invoice_fields),
            settings.tax_rate_percent > 0 or settings.tax_show_on_invoice,
            bool(settings.payment_options or settings.payment_other),
            settings.cloud_sync_enabled,
        )
    )
    payload = {
        "profile": {
            "display_name": (settings_repository.get_setting("profile_display_name") or "River Young").strip(),
            "role": (settings_repository.get_setting("profile_role") or "Owner").strip(),
            "email": (settings_repository.get_setting("profile_email") or "").strip(),
            "initials": _profile_initials(settings_repository.get_setting("profile_display_name") or "River Young"),
            "avatar_configured": bool(settings_repository.get_setting("profile_avatar_path")),
            "avatar_available": bool(_resolve_dashboard_logo(settings_repository.get_setting("profile_avatar_path"))),
        },
        "business": {
            "name": settings.business_name,
            "home_location": home_location,
            "show_name_on_dashboard": settings.dashboard_show_business_name,
            "logo_configured": bool(settings.dashboard_logo_path),
            "logo_available": bool(_resolve_dashboard_logo(settings.dashboard_logo_path)),
            "logo_alignment": settings.dashboard_logo_alignment,
            "logo_size": settings.dashboard_logo_size,
        },
        "appearance": {
            "theme": theme,
            "text_scale": text_scale,
            "logo_alignment": settings.dashboard_logo_alignment,
            "logo_size": settings.dashboard_logo_size,
            "dashboard_sections": _dashboard_section_settings(),
        },
        "orders": {
            "number_format": settings.order_number_format,
            "next_sequence": settings.order_number_next,
            "next_number": _order_number(False),
            "low_inventory_threshold": settings.low_inventory_threshold,
        },
        "invoice": {
            "slogan": settings.invoice_slogan,
            "address": address,
            "street": settings.invoice_street,
            "city": settings.invoice_city,
            "state": settings.invoice_state,
            "zip": settings.invoice_zip,
            "phone": settings.invoice_phone,
            "fax": settings.invoice_fax,
            "terms": settings.invoice_terms,
            "comments": settings.invoice_comments,
            "contact_name": settings.invoice_contact_name,
            "contact_phone": settings.invoice_contact_phone,
            "contact_email": settings.invoice_contact_email,
        },
        "tax": {
            "rate_percent": _money(settings.tax_rate_percent),
            "show_on_invoice": settings.tax_show_on_invoice,
            "add_to_total": settings.tax_add_to_total,
        },
        "payments": {
            "methods": [{"source_index": index, "label": option.label, "configured": bool(option.value)} for index, option in enumerate(settings.payment_options)],
            "other_configured": bool(settings.payment_other),
        },
        "sync": {
            "enabled": settings.cloud_sync_enabled,
            "provider": settings.cloud_sync_provider,
            "interval_minutes": settings.cloud_sync_interval_minutes,
            "configured_field_count": sum(bool(str(value).strip()) for value in settings.cloud_sync_config.values()),
        },
        "browser": {
            "launch_mode": (settings_repository.get_setting("browser_launch_mode") or "system").strip().casefold(),
            "browser_id": (settings_repository.get_setting("browser_id") or "system").strip().casefold(),
            "available": available_browsers(),
        },
        "summary": {
            "configured_sections": configured_sections,
            "payment_method_count": len(settings.payment_options) + int(bool(settings.payment_other)),
            "sensitive_values_excluded": True,
            "editing_surface": "browser",
        },
    }
    sensitive_revision = _record_revision({
        "payment_options": [(option.label, option.value) for option in settings.payment_options],
        "payment_other": settings.payment_other,
        "cloud_sync_config": settings.cloud_sync_config,
    })
    revision_source = json.dumps(payload, sort_keys=True, separators=(",", ":")) + sensitive_revision
    payload["summary"]["revision"] = hashlib.sha256(revision_source.encode("utf-8")).hexdigest()[:16]
    return payload


def _setting_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().casefold() in {"true", "1", "yes", "on"}:
        return True
    if isinstance(value, str) and value.strip().casefold() in {"false", "0", "no", "off"}:
        return False
    raise BridgeError("validation_failed", "Some settings need attention.", HTTPStatus.BAD_REQUEST, {field: "invalid_boolean"})


def _setting_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BridgeError("validation_failed", "Some settings need attention.", HTTPStatus.BAD_REQUEST, {field: "invalid_number"}) from exc
    if parsed < minimum or parsed > maximum:
        raise BridgeError("validation_failed", "Some settings need attention.", HTTPStatus.BAD_REQUEST, {field: "out_of_range"})
    return parsed


def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
    section = str(payload.get("section", "")).strip().casefold()
    values = payload.get("values")
    if not isinstance(values, dict):
        raise BridgeError("validation_failed", "Settings values are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})
    current = settings_workspace()
    expected_revision = str(payload.get("expected_revision", "")).strip()
    if expected_revision and expected_revision != current["summary"]["revision"]:
        raise BridgeError("settings_conflict", "Settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    updates: dict[str, str] = {}
    if section == "business":
        name = str(values.get("name", "")).strip()
        if not name:
            raise BridgeError("validation_failed", "Business name is required.", HTTPStatus.BAD_REQUEST, {"name": "required"})
        updates = {
            "business_name": name[:160],
            "dashboard_home_city": str(values.get("home_city", "")).strip()[:100],
            "dashboard_home_state": str(values.get("home_state", "")).strip().upper()[:2],
            "dashboard_show_business_name": "1" if _setting_bool(values.get("show_name_on_dashboard", True), "show_name_on_dashboard") else "0",
        }
    elif section == "profile":
        display_name = str(values.get("display_name", "")).strip()
        role = str(values.get("role", "")).strip()
        email = str(values.get("email", "")).strip()
        if not display_name:
            raise BridgeError("validation_failed", "Display name is required.", HTTPStatus.BAD_REQUEST, {"display_name": "required"})
        if not role:
            raise BridgeError("validation_failed", "Role is required.", HTTPStatus.BAD_REQUEST, {"role": "required"})
        if email and ("@" not in email or " " in email):
            raise BridgeError("validation_failed", "Enter a valid email address.", HTTPStatus.BAD_REQUEST, {"email": "invalid_email"})
        updates = {
            "profile_display_name": display_name[:160],
            "profile_role": role[:100],
            "profile_email": email[:254],
        }
    elif section == "orders":
        number_format = str(values.get("number_format", "")).strip()
        if "{seq" not in number_format:
            raise BridgeError("validation_failed", "Order format must include {seq}.", HTTPStatus.BAD_REQUEST, {"number_format": "missing_sequence"})
        try:
            number_format.format(seq=1)
        except (KeyError, ValueError, IndexError) as exc:
            raise BridgeError("validation_failed", "Order format is invalid.", HTTPStatus.BAD_REQUEST, {"number_format": "invalid_format"}) from exc
        updates = {
            "order_number_format": number_format[:80],
            "order_number_next": str(_setting_int(values.get("next_sequence"), "next_sequence", 1, 999999999)),
            "low_inventory_threshold": str(_setting_int(values.get("low_inventory_threshold"), "low_inventory_threshold", 0, 999999)),
        }
    elif section == "invoice":
        field_map = {
            "slogan": "invoice_slogan", "street": "invoice_street", "city": "invoice_city", "state": "invoice_state",
            "zip": "invoice_zip", "phone": "invoice_phone", "fax": "invoice_fax", "terms": "invoice_terms",
            "comments": "invoice_comments", "contact_name": "invoice_contact_name", "contact_phone": "invoice_contact_phone",
            "contact_email": "invoice_contact_email",
        }
        updates = {setting_key: str(values.get(field, "")).strip()[:500] for field, setting_key in field_map.items()}
        updates["invoice_state"] = updates["invoice_state"].upper()[:2]
        if not updates["invoice_terms"]:
            updates["invoice_terms"] = "Due on receipt"
    elif section == "tax":
        try:
            rate = float(values.get("rate_percent", 0))
        except (TypeError, ValueError) as exc:
            raise BridgeError("validation_failed", "Tax rate must be a number.", HTTPStatus.BAD_REQUEST, {"rate_percent": "invalid_number"}) from exc
        if rate < 0 or rate > 100:
            raise BridgeError("validation_failed", "Tax rate must be between 0 and 100.", HTTPStatus.BAD_REQUEST, {"rate_percent": "out_of_range"})
        updates = {
            "tax_rate_percent": f"{rate:.4f}",
            "tax_show_on_invoice": "1" if _setting_bool(values.get("show_on_invoice", False), "show_on_invoice") else "0",
            "tax_add_to_total": "1" if _setting_bool(values.get("add_to_total", False), "add_to_total") else "0",
        }
    elif section == "payments":
        raw_methods = values.get("methods")
        if not isinstance(raw_methods, list):
            raise BridgeError("validation_failed", "Payment methods are required.", HTTPStatus.BAD_REQUEST, {"methods": "required"})
        if len(raw_methods) > 12:
            raise BridgeError("validation_failed", "Use no more than 12 payment methods.", HTTPStatus.BAD_REQUEST, {"methods": "too_many"})
        current_settings = settings_repository.get_app_settings()
        payment_options: list[PaymentOption] = []
        used_indexes: set[int] = set()
        for position, raw_method in enumerate(raw_methods):
            if not isinstance(raw_method, dict):
                raise BridgeError("validation_failed", "A payment method is invalid.", HTTPStatus.BAD_REQUEST, {f"methods.{position}": "invalid"})
            label = str(raw_method.get("label", "")).strip()[:80]
            if not label:
                raise BridgeError("validation_failed", "Each payment method needs a label.", HTTPStatus.BAD_REQUEST, {f"methods.{position}.label": "required"})
            source_index = raw_method.get("source_index")
            replacement = str(raw_method.get("replacement", "")).strip()[:500]
            if source_index is None:
                if not replacement:
                    raise BridgeError("validation_failed", "New payment methods need a destination.", HTTPStatus.BAD_REQUEST, {f"methods.{position}.replacement": "required"})
                value = replacement
            else:
                try:
                    parsed_index = int(source_index)
                except (TypeError, ValueError) as exc:
                    raise BridgeError("validation_failed", "A payment method reference is invalid.", HTTPStatus.BAD_REQUEST, {f"methods.{position}.source_index": "invalid"}) from exc
                if parsed_index < 0 or parsed_index >= len(current_settings.payment_options) or parsed_index in used_indexes:
                    raise BridgeError("validation_failed", "A payment method reference is invalid.", HTTPStatus.BAD_REQUEST, {f"methods.{position}.source_index": "invalid"})
                used_indexes.add(parsed_index)
                value = replacement or current_settings.payment_options[parsed_index].value
            payment_options.append(PaymentOption(label=label, value=value))
        other_action = str(values.get("other_action", "keep")).strip().casefold()
        if other_action not in {"keep", "replace", "remove"}:
            raise BridgeError("validation_failed", "Payment notes action is invalid.", HTTPStatus.BAD_REQUEST, {"other_action": "invalid"})
        if other_action == "keep":
            payment_other = current_settings.payment_other
        elif other_action == "remove":
            payment_other = ""
        else:
            payment_other = str(values.get("other_replacement", "")).strip()[:1000]
            if not payment_other:
                raise BridgeError("validation_failed", "Enter replacement payment notes.", HTTPStatus.BAD_REQUEST, {"other_replacement": "required"})
        updates = {
            "payment_options": json.dumps([{"label": option.label, "value": option.value} for option in payment_options], ensure_ascii=False),
            "payment_other": payment_other,
            "payment_paypal": "",
            "payment_venmo": "",
            "payment_cash_app": "",
        }
    elif section == "appearance":
        current_appearance = current["appearance"]
        theme = str(values.get("theme", current_appearance["theme"])).strip().casefold()
        if theme not in APPEARANCE_THEMES:
            raise BridgeError("validation_failed", "Choose an available color theme.", HTTPStatus.BAD_REQUEST, {"theme": "invalid_choice"})
        try:
            text_scale = float(values.get("text_scale", current_appearance["text_scale"]))
        except (TypeError, ValueError):
            text_scale = 0.0
        if not isfinite(text_scale) or text_scale not in APPEARANCE_TEXT_SCALES:
            raise BridgeError("validation_failed", "Choose an available text size.", HTTPStatus.BAD_REQUEST, {"text_scale": "invalid_choice"})
        alignment = str(values.get("logo_alignment", current_appearance["logo_alignment"])).strip().casefold()
        if alignment not in {"top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"}:
            raise BridgeError("validation_failed", "Logo alignment is invalid.", HTTPStatus.BAD_REQUEST, {"logo_alignment": "invalid_choice"})
        logo_size = _setting_int(values.get("logo_size", current_appearance["logo_size"]), "logo_size", 24, 1024)
        raw_sections = values.get("dashboard_sections", current_appearance["dashboard_sections"])
        if not isinstance(raw_sections, list):
            raise BridgeError("validation_failed", "Dashboard sections are invalid.", HTTPStatus.BAD_REQUEST, {"dashboard_sections": "invalid"})
        incoming = {str(item.get("key", "")): item for item in raw_sections if isinstance(item, dict)}
        sections = {
            key: {
                "visible": _setting_bool(incoming.get(key, {}).get("visible", True), f"dashboard_sections.{key}.visible"),
                "collapsed": _setting_bool(incoming.get(key, {}).get("collapsed", False), f"dashboard_sections.{key}.collapsed"),
            }
            for key in DASHBOARD_SECTIONS
        }
        updates = {
            "app_theme": theme,
            "browser_text_scale": f"{text_scale:g}",
            "dashboard_logo_alignment": alignment,
            "dashboard_logo_size": str(logo_size),
            "dashboard_sections_json": json.dumps(sections, separators=(",", ":")),
        }
    elif section == "browser":
        mode = str(values.get("launch_mode", "system")).strip().casefold()
        browser_id = str(values.get("browser_id", "system")).strip().casefold()
        if mode not in {"system", "specific", "none"}:
            raise BridgeError("validation_failed", "Browser launch mode is invalid.", HTTPStatus.BAD_REQUEST, {"launch_mode": "invalid_choice"})
        available_ids = {browser["id"] for browser in available_browsers()}
        if mode == "specific" and (browser_id == "system" or browser_id not in available_ids):
            raise BridgeError("validation_failed", "Select an installed browser.", HTTPStatus.BAD_REQUEST, {"browser_id": "unavailable"})
        updates = {"browser_launch_mode": mode, "browser_id": browser_id if mode == "specific" else "system"}
    else:
        raise BridgeError("invalid_section", "That settings section is not editable here.", HTTPStatus.BAD_REQUEST)
    settings_repository.set_settings(updates)
    return settings_workspace()


def _decode_brand_logo(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    upload = payload.get("file")
    if not isinstance(upload, dict):
        raise BridgeError("validation_failed", "Choose a business logo.", HTTPStatus.BAD_REQUEST, {"file": "required"})
    try:
        content = base64.b64decode(str(upload.get("content_base64", "")), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise BridgeError("validation_failed", "The logo could not be read.", HTTPStatus.BAD_REQUEST, {"file": "invalid_content"}) from exc
    if not content:
        raise BridgeError("validation_failed", "The logo is empty.", HTTPStatus.BAD_REQUEST, {"file": "empty"})
    if len(content) > MAX_BRAND_LOGO_BYTES:
        raise BridgeError("validation_failed", "Business logos must be 8 MB or smaller.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"file": "too_large"})
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return content, ".png", "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return content, ".jpg", "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return content, ".gif", "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return content, ".webp", "image/webp"
    raise BridgeError("validation_failed", "Use a PNG, JPEG, GIF, or WebP logo.", HTTPStatus.BAD_REQUEST, {"file": "unsupported_type"})


def _delete_managed_brand_logo(path_value: str) -> None:
    path = _resolve_dashboard_logo(path_value)
    if path is None:
        return
    managed_root = (get_storage_root() / "media" / "branding").resolve()
    try:
        path.relative_to(managed_root)
    except ValueError:
        return
    path.unlink(missing_ok=True)


def save_dashboard_logo(payload: dict[str, Any]) -> dict[str, Any]:
    current = settings_workspace()
    expected_revision = str(payload.get("expected_revision", "")).strip()
    if expected_revision and expected_revision != current["summary"]["revision"]:
        raise BridgeError("settings_conflict", "Settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    content, suffix, _ = _decode_brand_logo(payload)
    with MUTATION_LOCK:
        previous = settings_repository.get_app_settings().dashboard_logo_path
        folder = get_storage_root() / "media" / "branding"
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / f"dashboard_{hashlib.sha256(content).hexdigest()[:16]}{suffix}"
        destination.write_bytes(content)
        settings_repository.set_setting("dashboard_logo_path", str(destination.relative_to(get_storage_root())))
        if previous != str(destination.relative_to(get_storage_root())):
            _delete_managed_brand_logo(previous)
    return settings_workspace()


def delete_dashboard_logo(payload: dict[str, Any]) -> dict[str, Any]:
    current = settings_workspace()
    expected_revision = str(payload.get("expected_revision", "")).strip()
    if expected_revision and expected_revision != current["summary"]["revision"]:
        raise BridgeError("settings_conflict", "Settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    with MUTATION_LOCK:
        previous = settings_repository.get_app_settings().dashboard_logo_path
        settings_repository.set_setting("dashboard_logo_path", "")
        _delete_managed_brand_logo(previous)
    return settings_workspace()


def download_dashboard_logo() -> BinaryDownload:
    path = _resolve_dashboard_logo(settings_repository.get_app_settings().dashboard_logo_path)
    if path is None:
        raise BridgeError("file_missing", "The business logo could not be found.", HTTPStatus.NOT_FOUND)
    return BinaryDownload(path.name, mimetypes.guess_type(path.name)[0] or "application/octet-stream", path.read_bytes())


def _decode_profile_avatar(payload: dict[str, Any]) -> tuple[bytes, str]:
    upload = payload.get("file")
    if not isinstance(upload, dict):
        raise BridgeError("validation_failed", "Choose a profile photo.", HTTPStatus.BAD_REQUEST, {"file": "required"})
    try:
        content = base64.b64decode(str(upload.get("content_base64", "")), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise BridgeError("validation_failed", "The profile photo could not be read.", HTTPStatus.BAD_REQUEST, {"file": "invalid_content"}) from exc
    if not content:
        raise BridgeError("validation_failed", "The profile photo is empty.", HTTPStatus.BAD_REQUEST, {"file": "empty"})
    if len(content) > MAX_PROFILE_AVATAR_BYTES:
        raise BridgeError("validation_failed", "Profile photos must be 5 MB or smaller.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"file": "too_large"})
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return content, ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return content, ".jpg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return content, ".gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return content, ".webp"
    raise BridgeError("validation_failed", "Use a PNG, JPEG, GIF, or WebP profile photo.", HTTPStatus.BAD_REQUEST, {"file": "unsupported_type"})


def _delete_managed_profile_avatar(path_value: str) -> None:
    path = _resolve_dashboard_logo(path_value)
    if path is None:
        return
    managed_root = (get_storage_root() / "media" / "profiles").resolve()
    try:
        path.relative_to(managed_root)
    except ValueError:
        return
    path.unlink(missing_ok=True)


def save_profile_avatar(payload: dict[str, Any]) -> dict[str, Any]:
    current = settings_workspace()
    expected_revision = str(payload.get("expected_revision", "")).strip()
    if expected_revision and expected_revision != current["summary"]["revision"]:
        raise BridgeError("settings_conflict", "Settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    content, suffix = _decode_profile_avatar(payload)
    with MUTATION_LOCK:
        previous = settings_repository.get_setting("profile_avatar_path")
        folder = get_storage_root() / "media" / "profiles"
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / f"owner_{hashlib.sha256(content).hexdigest()[:16]}{suffix}"
        destination.write_bytes(content)
        relative = str(destination.relative_to(get_storage_root()))
        settings_repository.set_setting("profile_avatar_path", relative)
        if previous != relative:
            _delete_managed_profile_avatar(previous)
    return settings_workspace()


def delete_profile_avatar(payload: dict[str, Any]) -> dict[str, Any]:
    current = settings_workspace()
    expected_revision = str(payload.get("expected_revision", "")).strip()
    if expected_revision and expected_revision != current["summary"]["revision"]:
        raise BridgeError("settings_conflict", "Settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    with MUTATION_LOCK:
        previous = settings_repository.get_setting("profile_avatar_path")
        settings_repository.set_setting("profile_avatar_path", "")
        _delete_managed_profile_avatar(previous)
    return settings_workspace()


def download_profile_avatar() -> BinaryDownload:
    path = _resolve_dashboard_logo(settings_repository.get_setting("profile_avatar_path"))
    if path is None:
        raise BridgeError("file_missing", "The profile photo could not be found.", HTTPStatus.NOT_FOUND)
    return BinaryDownload(path.name, mimetypes.guess_type(path.name)[0] or "application/octet-stream", path.read_bytes())


def cloud_sync_workspace() -> dict[str, Any]:
    settings = settings_repository.get_app_settings()
    provider = settings.cloud_sync_provider.strip().casefold()
    config = settings.cloud_sync_config if provider in CLOUD_SYNC_PROVIDERS else {}
    providers = []
    for provider_key, definition in CLOUD_SYNC_PROVIDERS.items():
        providers.append({
            "key": provider_key,
            "label": definition["label"],
            "fields": [
                {"key": key, "label": label, "required": required, "sensitive": sensitive, "default": default, "configured": provider_key == provider and bool(str(config.get(key, "")).strip())}
                for key, label, required, sensitive, default in definition["fields"]
            ],
        })
    active = next((item for item in providers if item["key"] == provider), None)
    ready = bool(active) and all(not field["required"] or field["configured"] for field in (active["fields"] if active else []))
    if provider == "sftp":
        ready = ready and bool(config.get("password", "").strip() or config.get("private_key_path", "").strip())
    payload = {
        "enabled": settings.cloud_sync_enabled,
        "provider": provider,
        "interval_minutes": settings.cloud_sync_interval_minutes,
        "providers": providers,
        "ready": ready,
        "configured_field_count": sum(bool(str(value).strip()) for key, value in config.items() if key != "file_id"),
        "revision": settings_workspace()["summary"]["revision"],
    }
    return payload


def update_cloud_sync_from_browser(payload: dict[str, Any]) -> dict[str, Any]:
    current_workspace = cloud_sync_workspace()
    expected_revision = str(payload.get("expected_revision", "")).strip()
    if expected_revision and expected_revision != current_workspace["revision"]:
        raise BridgeError("settings_conflict", "Cloud sync settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    enabled = _setting_bool(payload.get("enabled", False), "enabled")
    provider = str(payload.get("provider", "")).strip().casefold()
    if provider not in CLOUD_SYNC_PROVIDERS and (enabled or provider):
        raise BridgeError("validation_failed", "Select a supported sync provider.", HTTPStatus.BAD_REQUEST, {"provider": "invalid_choice"})
    interval = _setting_int(payload.get("interval_minutes", 5), "interval_minutes", 1, 1440)
    current = settings_repository.get_app_settings()
    config = dict(current.cloud_sync_config) if provider and provider == current.cloud_sync_provider.strip().casefold() else {}
    raw_fields = payload.get("fields", [])
    if not isinstance(raw_fields, list):
        raise BridgeError("validation_failed", "Provider fields are invalid.", HTTPStatus.BAD_REQUEST, {"fields": "invalid"})
    actions = {str(item.get("key", "")): item for item in raw_fields if isinstance(item, dict)}
    schema = CLOUD_SYNC_PROVIDERS.get(provider, {"fields": ()})["fields"]
    allowed = {field[0] for field in schema}
    for key in allowed:
        item = actions.get(key, {})
        action = str(item.get("action", "keep")).strip().casefold()
        if action not in {"keep", "replace", "remove"}:
            raise BridgeError("validation_failed", "A provider field action is invalid.", HTTPStatus.BAD_REQUEST, {f"fields.{key}": "invalid_action"})
        if action == "remove":
            config.pop(key, None)
        elif action == "replace":
            replacement = str(item.get("replacement", "")).strip()[:4096]
            if replacement:
                config[key] = replacement
            else:
                config.pop(key, None)
    if provider != "google-drive":
        config.pop("file_id", None)
    if enabled:
        missing = [key for key, label, required, _sensitive, _default in schema if required and not str(config.get(key, "")).strip()]
        if provider == "sftp" and not (str(config.get("password", "")).strip() or str(config.get("private_key_path", "")).strip()):
            missing.append("password")
        if missing:
            raise BridgeError("validation_failed", "Complete the required provider fields before enabling sync.", HTTPStatus.BAD_REQUEST, {f"fields.{key}": "required" for key in missing})
    settings_repository.set_settings({
        "cloud_sync_enabled": "1" if enabled else "0",
        "cloud_sync_provider": provider,
        "cloud_sync_interval_minutes": str(interval),
        "cloud_sync_settings_json": json.dumps(config, ensure_ascii=False),
    })
    return cloud_sync_workspace()


def _safe_cloud_message(message: str) -> str:
    sanitized = str(message or "")
    settings = settings_repository.get_app_settings()
    protected = [str(value).strip() for value in settings.cloud_sync_config.values() if str(value).strip()]
    protected.append(str(get_database_path()))
    for value in sorted(set(protected), key=len, reverse=True):
        sanitized = sanitized.replace(value, "[protected]")
    return sanitized


def upload_cloud_database(payload: dict[str, Any]) -> dict[str, Any]:
    workspace = cloud_sync_workspace()
    expected_revision = str(payload.get("expected_revision", "")).strip()
    if expected_revision and expected_revision != workspace["revision"]:
        raise BridgeError("settings_conflict", "Cloud sync settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    outcome = cloud_sync_service.upload_database(settings_repository.get_app_settings())
    if not outcome.success:
        raise BridgeError("sync_failed", _safe_cloud_message(outcome.message) or "The database could not be uploaded.", HTTPStatus.BAD_REQUEST)
    return {"message": _safe_cloud_message(outcome.message), "uploaded": outcome.uploaded, "workspace": cloud_sync_workspace()}


def pull_cloud_database(payload: dict[str, Any]) -> dict[str, Any]:
    workspace = cloud_sync_workspace()
    expected_revision = str(payload.get("expected_revision", "")).strip()
    if expected_revision and expected_revision != workspace["revision"]:
        raise BridgeError("settings_conflict", "Cloud sync settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    if str(payload.get("confirmation", "")).strip() != "PULL CLOUD DATA":
        raise BridgeError("confirmation_required", "Type PULL CLOUD DATA to continue.", HTTPStatus.BAD_REQUEST, {"confirmation": "mismatch"})
    create_browser_backup(guard_revision=False)
    outcome = cloud_sync_service.download_database_if_newer(settings_repository.get_app_settings())
    if not outcome.success:
        raise BridgeError("sync_failed", _safe_cloud_message(outcome.message) or "Cloud data could not be pulled.", HTTPStatus.BAD_REQUEST)
    return {"message": _safe_cloud_message(outcome.message), "downloaded": outcome.downloaded, "restart_required": outcome.downloaded, "workspace": None if outcome.downloaded else cloud_sync_workspace()}


def authorize_google_cloud(payload: dict[str, Any]) -> dict[str, Any]:
    workspace = cloud_sync_workspace()
    if str(payload.get("expected_revision", "")).strip() not in {"", workspace["revision"]}:
        raise BridgeError("settings_conflict", "Cloud sync settings changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
    settings = settings_repository.get_app_settings()
    if settings.cloud_sync_provider.strip().casefold() != "google-drive":
        raise BridgeError("validation_failed", "Select and save Google Drive first.", HTTPStatus.BAD_REQUEST, {"provider": "google_required"})
    client_path = settings.cloud_sync_config.get("client_secrets_path", "").strip()
    token_path = settings.cloud_sync_config.get("token_path", "").strip()
    if not client_path or not token_path:
        raise BridgeError("validation_failed", "Save both Google client-secrets and token paths before authorizing.", HTTPStatus.BAD_REQUEST)
    outcome = cloud_sync_service.authorize_google_drive(client_path, token_path)
    if not outcome.success:
        raise BridgeError("authorization_failed", _safe_cloud_message(outcome.message) or "Google Drive authorization failed.", HTTPStatus.BAD_REQUEST)
    return {"message": _safe_cloud_message(outcome.message), "workspace": cloud_sync_workspace()}


def _browser_import_file(payload: dict[str, Any], folder: Path) -> tuple[Path, bytes]:
    upload = payload.get("file")
    if not isinstance(upload, dict):
        raise BridgeError("validation_failed", "Choose a CSV or Excel file.", HTTPStatus.BAD_REQUEST, {"file": "required"})
    name = Path(str(upload.get("name", ""))).name
    suffix = Path(name).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise BridgeError("validation_failed", "Use a .csv or .xlsx file.", HTTPStatus.BAD_REQUEST, {"file": "unsupported_format"})
    try:
        content = base64.b64decode(str(upload.get("content_base64", "")), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BridgeError("validation_failed", "The import file could not be read.", HTTPStatus.BAD_REQUEST, {"file": "invalid_encoding"}) from exc
    if not content:
        raise BridgeError("validation_failed", "The import file is empty.", HTTPStatus.BAD_REQUEST, {"file": "empty"})
    if len(content) > MAX_IMPORT_BYTES:
        raise BridgeError("validation_failed", "Import files must be 12 MB or smaller.", HTTPStatus.BAD_REQUEST, {"file": "too_large"})
    path = folder / f"import{suffix}"
    path.write_bytes(content)
    return path, content


def _import_type(payload: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]]]:
    import_type = str(payload.get("import_type", "")).strip().casefold()
    fields = import_service.get_field_definitions(import_type)
    if not fields:
        raise BridgeError("validation_failed", "Choose products, orders, or customers.", HTTPStatus.BAD_REQUEST, {"import_type": "unsupported"})
    return import_type, fields


def preview_browser_import(payload: dict[str, Any]) -> dict[str, Any]:
    import_type, fields = _import_type(payload)
    with TemporaryDirectory(prefix="hustlenest-import-") as temporary:
        path, content = _browser_import_file(payload, Path(temporary))
        try:
            if path.suffix == ".csv":
                columns, rows, source_detail = import_service.read_csv_preview(str(path), max_rows=10)
            else:
                columns, rows, source_detail = import_service.read_excel_preview(str(path), max_rows=10)
        except (ImportError, OSError, ValueError) as exc:
            raise BridgeError("invalid_import_file", str(exc), HTTPStatus.BAD_REQUEST, {"file": "unreadable"}) from exc
    auto_mappings = {mapping.source_column: mapping.target_field for mapping in import_service.auto_map_columns(columns, fields)}
    return {
        "import_type": import_type,
        "file": {"name": Path(str(payload["file"].get("name", ""))).name, "size_bytes": len(content), "source_detail": source_detail},
        "columns": [
            {"index": column.index, "name": column.name, "sample_values": column.sample_values, "suggested_field": auto_mappings.get(column.index, "")}
            for column in columns
        ],
        "preview_rows": rows,
        "fields": [
            {"name": name, "label": definition.get("label", name), "required": bool(definition.get("required")), "type": definition.get("type", "text")}
            for name, definition in fields.items()
        ],
    }


def execute_browser_import(payload: dict[str, Any]) -> dict[str, Any]:
    import_type, fields = _import_type(payload)
    raw_mappings = payload.get("mappings")
    if not isinstance(raw_mappings, list):
        raise BridgeError("validation_failed", "Column mappings are required.", HTTPStatus.BAD_REQUEST, {"mappings": "required"})
    mappings: list[import_service.ColumnMapping] = []
    used_targets: set[str] = set()
    for item in raw_mappings:
        if not isinstance(item, dict):
            raise BridgeError("validation_failed", "A column mapping is invalid.", HTTPStatus.BAD_REQUEST, {"mappings": "invalid"})
        try:
            source_column = int(item.get("source_column"))
        except (TypeError, ValueError) as exc:
            raise BridgeError("validation_failed", "A source column is invalid.", HTTPStatus.BAD_REQUEST, {"mappings": "invalid_source"}) from exc
        target = str(item.get("target_field", "")).strip()
        if source_column < 0 or target not in fields or target in used_targets:
            raise BridgeError("validation_failed", "Each mapped field must be valid and used once.", HTTPStatus.BAD_REQUEST, {"mappings": "invalid_target"})
        field_type = fields[target].get("type", "text")
        mappings.append(import_service.ColumnMapping(source_column, target, field_type if field_type in {"date", "number", "boolean"} else None))
        used_targets.add(target)
    missing = [name for name, definition in fields.items() if definition.get("required") and name not in used_targets]
    if missing:
        labels = ", ".join(str(fields[name].get("label", name)) for name in missing)
        raise BridgeError("validation_failed", f"Map the required fields: {labels}.", HTTPStatus.BAD_REQUEST, {"mappings": "missing_required"})

    with TemporaryDirectory(prefix="hustlenest-import-") as temporary:
        path, _ = _browser_import_file(payload, Path(temporary))
        try:
            if path.suffix == ".csv":
                columns, _, _ = import_service.read_csv_preview(str(path), max_rows=1)
            else:
                columns, _, _ = import_service.read_excel_preview(str(path), max_rows=1)
        except (ImportError, OSError, ValueError) as exc:
            raise BridgeError("invalid_import_file", str(exc), HTTPStatus.BAD_REQUEST, {"file": "unreadable"}) from exc
        if any(mapping.source_column >= len(columns) for mapping in mappings):
            raise BridgeError("validation_failed", "A mapped column no longer exists in the selected file.", HTTPStatus.BAD_REQUEST, {"mappings": "source_out_of_range"})
        importer = {
            "products": import_service.import_products,
            "orders": import_service.import_orders,
            "customers": import_service.import_customers,
        }[import_type]
        with MUTATION_LOCK:
            result = importer(str(path), mappings, bool(payload.get("skip_duplicates", True)))
    return {
        "success": result.success,
        "imported_count": result.imported_count,
        "skipped_count": result.skipped_count,
        "error_count": result.error_count,
        "errors": result.errors[:100],
        "warnings": result.warnings[:100],
        "messages_truncated": len(result.errors) > 100 or len(result.warnings) > 100,
    }


def _backup_folder() -> Path:
    configured = (settings_repository.get_setting("backup_folder") or "").strip()
    return Path(configured).expanduser() if configured else get_storage_root() / "backups"


def _backup_rows() -> list[dict[str, Any]]:
    folder = _backup_folder()
    rows: list[dict[str, Any]] = []
    if folder.is_dir():
        for path in folder.glob("hustlenest_backup_*.db"):
            try:
                stat = path.stat()
            except OSError:
                continue
            identity = _record_revision({"name": path.name, "size": stat.st_size, "modified": stat.st_mtime_ns})
            rows.append({"id": identity, "filename": path.name, "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(), "size_bytes": stat.st_size})
    return sorted(rows, key=lambda item: item["created_at"], reverse=True)


def backup_workspace() -> dict[str, Any]:
    enabled = (settings_repository.get_setting("backup_enabled") or "0").strip().casefold() not in {"", "0", "false", "no"}
    frequency = (settings_repository.get_setting("backup_frequency") or "daily").strip().casefold()
    if frequency not in {"daily", "weekly", "manual"}:
        frequency = "daily"
    try:
        max_backups = min(100, max(1, int(settings_repository.get_setting("backup_max_count") or "10")))
    except ValueError:
        max_backups = 10
    last_backup = (settings_repository.get_setting("backup_last_timestamp") or "").strip() or None
    backups = _backup_rows()
    payload = {
        "settings": {"enabled": enabled, "folder": str(_backup_folder()), "using_managed_folder": not bool((settings_repository.get_setting("backup_folder") or "").strip()), "frequency": frequency, "max_backups": max_backups, "last_backup": last_backup},
        "backups": backups,
        "summary": {"count": len(backups), "total_bytes": sum(item["size_bytes"] for item in backups)},
    }
    payload["revision"] = _record_revision(payload)
    return payload


def update_backup_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = backup_workspace()
    _guard_record_revision(str(payload.get("expected_revision", "")).strip(), current["revision"])
    values = payload.get("values")
    if not isinstance(values, dict):
        raise BridgeError("validation_failed", "Backup settings are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})
    enabled = _setting_bool(values.get("enabled", False), "enabled")
    frequency = str(values.get("frequency", "daily")).strip().casefold()
    if frequency not in {"daily", "weekly", "manual"}:
        raise BridgeError("validation_failed", "Backup frequency is invalid.", HTTPStatus.BAD_REQUEST, {"frequency": "invalid_choice"})
    max_backups = _setting_int(values.get("max_backups", 10), "max_backups", 1, 100)
    use_managed = _setting_bool(values.get("using_managed_folder", True), "using_managed_folder")
    folder_text = "" if use_managed else str(values.get("folder", "")).strip()
    if not use_managed:
        folder = Path(folder_text).expanduser()
        if not folder_text or not folder.is_absolute():
            raise BridgeError("validation_failed", "Enter an absolute backup folder path.", HTTPStatus.BAD_REQUEST, {"folder": "absolute_path_required"})
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BridgeError("folder_unavailable", "The backup folder could not be created.", HTTPStatus.BAD_REQUEST, {"folder": "unavailable"}) from exc
    settings_repository.set_settings({"backup_enabled": "1" if enabled else "0", "backup_folder": folder_text, "backup_frequency": frequency, "backup_max_count": str(max_backups)})
    return backup_workspace()


def create_browser_backup(payload: Optional[dict[str, Any]] = None, *, guard_revision: bool = True) -> dict[str, Any]:
    payload = payload or {}
    current = backup_workspace()
    if guard_revision:
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), current["revision"])
    folder = _backup_folder()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BridgeError("folder_unavailable", "The backup folder is unavailable.", HTTPStatus.BAD_REQUEST) from exc
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = folder / f"hustlenest_backup_{timestamp}.db"
    temporary = destination.with_suffix(".tmp")
    with MUTATION_LOCK:
        source = None
        target = None
        try:
            source = create_connection()
            target = sqlite3.connect(temporary)
            source.backup(target)
            target.commit()
            target.close()
            target = None
            source.close()
            source = None
            temporary.replace(destination)
        except (OSError, sqlite3.Error) as exc:
            if target is not None:
                target.close()
            if source is not None:
                source.close()
            temporary.unlink(missing_ok=True)
            raise BridgeError("backup_failed", "The database backup could not be created.", HTTPStatus.INTERNAL_SERVER_ERROR) from exc
        settings_repository.set_setting("backup_last_timestamp", datetime.now().isoformat())
        rows = _backup_rows()
        max_backups = current["settings"]["max_backups"]
        for stale in rows[max_backups:]:
            match = next((path for path in folder.glob("hustlenest_backup_*.db") if path.name == stale["filename"]), None)
            if match:
                match.unlink(missing_ok=True)
    return backup_workspace()


def _backup_path(backup_id: str) -> tuple[Path, dict[str, Any]]:
    row = next((item for item in _backup_rows() if item["id"] == backup_id), None)
    if row is None:
        raise BridgeError("backup_not_found", "That backup is no longer available.", HTTPStatus.NOT_FOUND)
    return _backup_folder() / row["filename"], row


def download_backup(backup_id: str) -> BinaryDownload:
    path, row = _backup_path(backup_id)
    return BinaryDownload(filename=row["filename"], content_type="application/vnd.sqlite3", content=path.read_bytes())


def restore_browser_backup(backup_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = backup_workspace()
    _guard_record_revision(str(payload.get("expected_revision", "")).strip(), current["revision"])
    path, row = _backup_path(backup_id)
    if str(payload.get("confirmation", "")).strip() != f"RESTORE {row['filename']}":
        raise BridgeError("confirmation_required", f"Type RESTORE {row['filename']} to continue.", HTTPStatus.BAD_REQUEST, {"confirmation": "required"})
    candidate = None
    try:
        candidate = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        check = candidate.execute("PRAGMA quick_check").fetchone()
        if not check or str(check[0]).casefold() != "ok":
            raise sqlite3.DatabaseError("quick_check failed")
    except sqlite3.Error as exc:
        raise BridgeError("invalid_backup", "The selected backup is not a healthy SQLite database.", HTTPStatus.BAD_REQUEST) from exc
    finally:
        if candidate is not None:
            candidate.close()
    database = get_database_path()
    safety = database.with_suffix(".db.restore-safety")
    with MUTATION_LOCK:
        source = None
        target = None
        try:
            source = create_connection()
            target = sqlite3.connect(safety)
            source.backup(target)
            target.commit()
            target.close()
            target = None
            source.close()
            source = None
            release_error = close_database_for_replacement()
            if release_error:
                raise OSError(release_error)
            shutil.copy2(path, database)
            initialize()
        except Exception as exc:
            if target is not None:
                target.close()
            if source is not None:
                source.close()
            if safety.is_file():
                shutil.copy2(safety, database)
                initialize()
            raise BridgeError("restore_failed", "The backup could not be restored; the current database was preserved.", HTTPStatus.INTERNAL_SERVER_ERROR) from exc
        finally:
            safety.unlink(missing_ok=True)
    return {"restored": True, "filename": row["filename"], "restart_required": True}


def _automatic_backup_due() -> bool:
    workspace = backup_workspace()
    settings = workspace["settings"]
    if not settings["enabled"] or settings["frequency"] == "manual":
        return False
    last = settings["last_backup"]
    if not last:
        return True
    try:
        elapsed = datetime.now() - datetime.fromisoformat(last)
    except ValueError:
        return True
    return elapsed >= (timedelta(days=1) if settings["frequency"] == "daily" else timedelta(days=7))


def _browser_backup_worker(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            if _automatic_backup_due():
                create_browser_backup(guard_revision=False)
        except Exception:
            LOGGER.exception("Automatic browser-backend backup failed")
        stop_event.wait(60 * 60)


def create_quick_entry(payload: dict[str, Any]) -> dict[str, Any]:
    entry_type = str(payload.get("type", "")).strip().casefold()
    values = payload.get("values")
    if not isinstance(values, dict):
        raise BridgeError("validation_failed", "Entry values are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})

    with MUTATION_LOCK:
        if entry_type == "customer":
            name = _required_text(values, "name", "Customer name")
            existing = next((item for item in crm_repository.list_contacts() if item.customer_name.strip().casefold() == name.casefold()), None)
            if existing:
                raise BridgeError("duplicate_customer", "A customer with that name already exists.", HTTPStatus.CONFLICT, {"name": "duplicate"})
            record_id = crm_repository.save_contact(CRMContact(
                id=None,
                customer_name=name,
                company=_optional_text(values, "company", 160),
                email=_optional_text(values, "email", 254),
                phone=_optional_text(values, "phone", 80),
                address=_optional_text(values, "address", 300),
                notes=_optional_text(values, "notes", 1000),
            ))
            label = name
        elif entry_type == "product":
            sku = _required_text(values, "sku", "Product SKU", 80).upper()
            name = _required_text(values, "name", "Product name")
            if product_repository.get_product_by_sku(sku):
                raise BridgeError("duplicate_sku", "That product SKU already exists.", HTTPStatus.CONFLICT, {"sku": "duplicate"})
            inventory = _nonnegative_number(values, "inventory_count", "Inventory quantity")
            if not inventory.is_integer():
                raise BridgeError("validation_failed", "Product inventory must be a whole number.", HTTPStatus.BAD_REQUEST, {"inventory_count": "whole_number_required"})
            created = product_repository.create_product(sku, name, mark_complete=True)
            try:
                saved = product_repository.update_product(Product(
                    id=created.id,
                    sku=sku,
                    name=name,
                    description=_optional_text(values, "description", 1000),
                    photo_path="",
                    inventory_count=int(inventory),
                    is_complete=True,
                    status=_product_status(values),
                    base_unit_cost=_nonnegative_number(values, "unit_cost", "Unit cost"),
                    default_unit_price=_nonnegative_number(values, "unit_price", "Unit price"),
                    pricing_components=_cost_components(values),
                ))
            except Exception:
                if created.id is not None:
                    product_repository.delete_product(created.id)
                raise
            record_id = int(saved.id or 0)
            label = name
        elif entry_type == "vendor":
            name = _required_text(values, "name", "Vendor name")
            existing = next((item for item in vendor_repository.list_vendors() if item.name.strip().casefold() == name.casefold()), None)
            if existing:
                raise BridgeError("duplicate_vendor", "A vendor with that name already exists.", HTTPStatus.CONFLICT, {"name": "duplicate"})
            record_id = vendor_repository.save_vendor(Vendor(
                id=None,
                name=name,
                contact_name=_optional_text(values, "contact_name", 160),
                email=_optional_text(values, "email", 254),
                phone=_optional_text(values, "phone", 80),
                website=_optional_text(values, "website", 300),
                account_number=_optional_text(values, "account_number", 160),
                notes=_optional_text(values, "notes", 1000),
                preferred_payment_method=_optional_text(values, "preferred_payment_method", 120),
            ))
            label = name
        elif entry_type == "material":
            sku = _required_text(values, "sku", "Material SKU", 80).upper()
            name = _required_text(values, "name", "Material name")
            if any(item.sku.strip().casefold() == sku.casefold() for item in material_repository.list_materials(include_archived=True)):
                raise BridgeError("duplicate_sku", "That material SKU already exists.", HTTPStatus.CONFLICT, {"sku": "duplicate"})
            vendor_id = _optional_id(values, "vendor_id")
            if vendor_id and vendor_repository.get_vendor(vendor_id) is None:
                raise BridgeError("validation_failed", "The selected vendor no longer exists.", HTTPStatus.BAD_REQUEST, {"vendor_id": "not_found"})
            record_id = material_repository.save_material(Material(
                id=None,
                sku=sku,
                name=name,
                category=_optional_text(values, "category", 120),
                description=_optional_text(values, "description", 1000),
                unit_of_measure=_optional_text(values, "unit_of_measure", 60),
                quantity_on_hand=_nonnegative_number(values, "quantity_on_hand", "Quantity on hand"),
                reorder_point=_nonnegative_number(values, "reorder_point", "Reorder point"),
                cost_per_unit=_nonnegative_number(values, "cost_per_unit", "Cost per unit"),
                vendor_id=vendor_id,
                notes=_optional_text(values, "notes", 1000),
            ))
            label = name
        elif entry_type == "recurring":
            category = _required_text(values, "category", "Expense category", 120)
            vendor_id = _optional_id(values, "vendor_id")
            if vendor_id and vendor_repository.get_vendor(vendor_id) is None:
                raise BridgeError("validation_failed", "The selected vendor no longer exists.", HTTPStatus.BAD_REQUEST, {"vendor_id": "not_found"})
            frequency, start_date, end_date, next_occurrence = _recurring_schedule(values)
            record_id = expense_repository.save_recurring_expense(RecurringExpense(
                id=None,
                category=category,
                amount=_nonnegative_number(values, "amount", "Recurring amount", positive=True),
                frequency=frequency,
                start_date=start_date,
                end_date=end_date,
                next_occurrence=next_occurrence,
                auto_record=_setting_bool(values.get("auto_record", False), "auto_record"),
                notes=_optional_text(values, "notes", 1000),
                vendor_id=vendor_id,
            ))
            label = category
        elif entry_type == "expense":
            category = _required_text(values, "category", "Expense category", 120)
            vendor_id = _optional_id(values, "vendor_id")
            if vendor_id and vendor_repository.get_vendor(vendor_id) is None:
                raise BridgeError("validation_failed", "The selected vendor no longer exists.", HTTPStatus.BAD_REQUEST, {"vendor_id": "not_found"})
            record_id = expense_repository.save_expense(Expense(
                id=None,
                category=category,
                amount=_nonnegative_number(values, "amount", "Expense amount", positive=True),
                expense_date=_entry_date(values),
                description=_optional_text(values, "description", 500),
                payment_method=_optional_text(values, "payment_method", 100),
                vendor_id=vendor_id,
                notes=_optional_text(values, "notes", 1000),
            ))
            label = category
        elif entry_type == "loss":
            category = _required_text(values, "category", "Loss category", 120)
            record_id = loss_repository.create_loss(LossRecord(
                id=None,
                amount=_nonnegative_number(values, "amount", "Loss amount", positive=True),
                loss_date=_entry_date(values),
                category=category,
                description=_optional_text(values, "description", 500),
                details=_optional_text(values, "notes", 1000),
            ))
            label = category
        else:
            raise BridgeError("invalid_entry_type", "That Quick Add record type is not supported.", HTTPStatus.BAD_REQUEST)

    return {"type": entry_type, "id": record_id, "label": label}


def _guard_record_revision(expected: str, actual: str) -> None:
    if expected and expected != actual:
        raise BridgeError("record_conflict", "This record changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)


def update_operational_entry(entry_type: str, record_id: int, values: dict[str, Any], expected_revision: str = "") -> dict[str, Any]:
    entry_type = entry_type.strip().casefold()
    with MUTATION_LOCK:
        if entry_type == "customer":
            existing = crm_repository.get_contact(record_id)
            if existing is None:
                raise BridgeError("customer_not_found", "Customer not found.", HTTPStatus.NOT_FOUND)
            _guard_record_revision(expected_revision, _customer_dto(existing)["revision"])
            name = _required_text(values, "name", "Customer name")
            duplicate = next((item for item in crm_repository.list_contacts() if item.id != record_id and item.customer_name.strip().casefold() == name.casefold()), None)
            if duplicate:
                raise BridgeError("duplicate_customer", "A customer with that name already exists.", HTTPStatus.CONFLICT, {"name": "duplicate"})
            existing.customer_name = name
            existing.company = _optional_text(values, "company", 160)
            existing.email = _optional_text(values, "email", 254)
            existing.phone = _optional_text(values, "phone", 80)
            existing.address = _optional_text(values, "address", 300)
            existing.notes = _optional_text(values, "notes", 1000)
            crm_repository.save_contact(existing)
            label = name
        elif entry_type == "product":
            existing_product = product_repository.get_product_by_id(record_id)
            if existing_product is None:
                raise BridgeError("product_not_found", "Product not found.", HTTPStatus.NOT_FOUND)
            _guard_record_revision(expected_revision, _product_dto(existing_product)["revision"])
            sku = _required_text(values, "sku", "Product SKU", 80).upper()
            name = _required_text(values, "name", "Product name")
            duplicate_product = product_repository.get_product_by_sku(sku)
            if duplicate_product and duplicate_product.id != record_id:
                raise BridgeError("duplicate_sku", "That product SKU already exists.", HTTPStatus.CONFLICT, {"sku": "duplicate"})
            inventory = _nonnegative_number(values, "inventory_count", "Inventory quantity")
            if not inventory.is_integer():
                raise BridgeError("validation_failed", "Product inventory must be a whole number.", HTTPStatus.BAD_REQUEST, {"inventory_count": "whole_number_required"})
            existing_product.sku = sku
            existing_product.name = name
            existing_product.description = _optional_text(values, "description", 1000)
            existing_product.inventory_count = int(inventory)
            existing_product.base_unit_cost = _nonnegative_number(values, "unit_cost", "Unit cost")
            existing_product.default_unit_price = _nonnegative_number(values, "unit_price", "Unit price")
            if "status" in values:
                existing_product.status = _product_status(values)
            if "cost_components" in values:
                existing_product.pricing_components = _cost_components(values)
            product_repository.update_product(existing_product)
            label = name
        elif entry_type == "material":
            existing_material = material_repository.get_material(record_id)
            if existing_material is None:
                raise BridgeError("material_not_found", "Material not found.", HTTPStatus.NOT_FOUND)
            current_vendors = {vendor.id: vendor for vendor in vendor_repository.list_vendors() if vendor.id is not None}
            _guard_record_revision(expected_revision, _material_dto(existing_material, current_vendors)["revision"])
            sku = _required_text(values, "sku", "Material SKU", 80).upper()
            name = _required_text(values, "name", "Material name")
            if any(item.id != record_id and item.sku.strip().casefold() == sku.casefold() for item in material_repository.list_materials(include_archived=True)):
                raise BridgeError("duplicate_sku", "That material SKU already exists.", HTTPStatus.CONFLICT, {"sku": "duplicate"})
            vendor_id = _optional_id(values, "vendor_id")
            if vendor_id and vendor_repository.get_vendor(vendor_id) is None:
                raise BridgeError("validation_failed", "The selected vendor no longer exists.", HTTPStatus.BAD_REQUEST, {"vendor_id": "not_found"})
            existing_material.sku = sku
            existing_material.name = name
            existing_material.category = _optional_text(values, "category", 120)
            existing_material.description = _optional_text(values, "description", 1000)
            existing_material.unit_of_measure = _optional_text(values, "unit_of_measure", 60)
            existing_material.quantity_on_hand = _nonnegative_number(values, "quantity_on_hand", "Quantity on hand")
            existing_material.reorder_point = _nonnegative_number(values, "reorder_point", "Reorder point")
            existing_material.cost_per_unit = _nonnegative_number(values, "cost_per_unit", "Cost per unit")
            existing_material.vendor_id = vendor_id
            existing_material.notes = _optional_text(values, "notes", 1000)
            material_repository.save_material(existing_material)
            label = name
        elif entry_type == "vendor":
            existing_vendor = vendor_repository.get_vendor(record_id)
            if existing_vendor is None:
                raise BridgeError("vendor_not_found", "Vendor not found.", HTTPStatus.NOT_FOUND)
            _guard_record_revision(expected_revision, _vendor_dto(existing_vendor)["revision"])
            name = _required_text(values, "name", "Vendor name")
            duplicate_vendor = next((item for item in vendor_repository.list_vendors() if item.id != record_id and item.name.strip().casefold() == name.casefold()), None)
            if duplicate_vendor:
                raise BridgeError("duplicate_vendor", "A vendor with that name already exists.", HTTPStatus.CONFLICT, {"name": "duplicate"})
            existing_vendor.name = name
            existing_vendor.contact_name = _optional_text(values, "contact_name", 160)
            existing_vendor.email = _optional_text(values, "email", 254)
            existing_vendor.phone = _optional_text(values, "phone", 80)
            existing_vendor.website = _optional_text(values, "website", 300)
            existing_vendor.account_number = _optional_text(values, "account_number", 160)
            existing_vendor.preferred_payment_method = _optional_text(values, "preferred_payment_method", 120)
            existing_vendor.notes = _optional_text(values, "notes", 1000)
            vendor_repository.save_vendor(existing_vendor)
            label = name
        elif entry_type == "recurring":
            existing_recurring = expense_repository.get_recurring_expense(record_id)
            if existing_recurring is None:
                raise BridgeError("recurring_not_found", "Recurring expense not found.", HTTPStatus.NOT_FOUND)
            _guard_record_revision(expected_revision, _recurring_revision(existing_recurring))
            vendor_id = _optional_id(values, "vendor_id")
            if vendor_id and vendor_repository.get_vendor(vendor_id) is None:
                raise BridgeError("validation_failed", "The selected vendor no longer exists.", HTTPStatus.BAD_REQUEST, {"vendor_id": "not_found"})
            frequency, start_date, end_date, next_occurrence = _recurring_schedule(values)
            existing_recurring.category = _required_text(values, "category", "Expense category", 120)
            existing_recurring.amount = _nonnegative_number(values, "amount", "Recurring amount", positive=True)
            existing_recurring.frequency = frequency
            existing_recurring.start_date = start_date
            existing_recurring.end_date = end_date
            existing_recurring.next_occurrence = next_occurrence
            existing_recurring.auto_record = _setting_bool(values.get("auto_record", False), "auto_record")
            existing_recurring.notes = _optional_text(values, "notes", 1000)
            existing_recurring.vendor_id = vendor_id
            expense_repository.save_recurring_expense(existing_recurring)
            label = existing_recurring.category
        elif entry_type == "expense":
            existing_expense = expense_repository.get_expense(record_id)
            if existing_expense is None:
                raise BridgeError("expense_not_found", "Expense not found.", HTTPStatus.NOT_FOUND)
            _guard_record_revision(expected_revision, _expense_revision(existing_expense))
            vendor_id = _optional_id(values, "vendor_id")
            if vendor_id and vendor_repository.get_vendor(vendor_id) is None:
                raise BridgeError("validation_failed", "The selected vendor no longer exists.", HTTPStatus.BAD_REQUEST, {"vendor_id": "not_found"})
            existing_expense.category = _required_text(values, "category", "Expense category", 120)
            existing_expense.amount = _nonnegative_number(values, "amount", "Expense amount", positive=True)
            existing_expense.expense_date = _entry_date(values)
            existing_expense.description = _optional_text(values, "description", 500)
            existing_expense.payment_method = _optional_text(values, "payment_method", 100)
            existing_expense.vendor_id = vendor_id
            existing_expense.notes = _optional_text(values, "notes", 1000)
            expense_repository.save_expense(existing_expense)
            label = existing_expense.category
        elif entry_type == "loss":
            existing_loss = loss_repository.get_loss(record_id)
            if existing_loss is None:
                raise BridgeError("loss_not_found", "Loss not found.", HTTPStatus.NOT_FOUND)
            _guard_record_revision(expected_revision, _loss_revision(existing_loss))
            existing_loss.category = _required_text(values, "category", "Loss category", 120)
            existing_loss.amount = _nonnegative_number(values, "amount", "Loss amount", positive=True)
            existing_loss.loss_date = _entry_date(values)
            existing_loss.description = _optional_text(values, "description", 500)
            existing_loss.details = _optional_text(values, "notes", 1000)
            loss_repository.update_loss(record_id, existing_loss)
            label = existing_loss.category
        else:
            raise BridgeError("invalid_entry_type", "That record type cannot be edited here.", HTTPStatus.BAD_REQUEST)
    return {"type": entry_type, "id": record_id, "label": label}


def delete_operational_entry(entry_type: str, record_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    entry_type = entry_type.strip().casefold()
    expected = str(payload.get("expected_revision", "")).strip()
    if entry_type == "product":
        return move_record_to_trash("product", record_id, payload)

    with MUTATION_LOCK:
        if entry_type == "customer":
            record = crm_repository.get_contact(record_id)
            actual = _customer_dto(record)["revision"] if record else ""
            delete = crm_repository.delete_contact
        elif entry_type == "material":
            record = material_repository.get_material(record_id)
            vendors = {vendor.id: vendor for vendor in vendor_repository.list_vendors() if vendor.id is not None}
            actual = _material_dto(record, vendors)["revision"] if record else ""
            delete = material_repository.delete_material
        elif entry_type == "vendor":
            record = vendor_repository.get_vendor(record_id)
            actual = _vendor_dto(record)["revision"] if record else ""
            delete = vendor_repository.delete_vendor
        elif entry_type == "expense":
            record = expense_repository.get_expense(record_id)
            actual = _expense_revision(record) if record else ""
            delete = expense_repository.delete_expense
        elif entry_type == "recurring":
            record = expense_repository.get_recurring_expense(record_id)
            actual = _recurring_revision(record) if record else ""
            delete = expense_repository.delete_recurring_expense
        elif entry_type == "loss":
            record = loss_repository.get_loss(record_id)
            actual = _loss_revision(record) if record else ""
            delete = loss_repository.delete_loss
        else:
            raise BridgeError("invalid_entry_type", "That record type cannot be deleted here.", HTTPStatus.BAD_REQUEST)
        if record is None:
            raise BridgeError("record_not_found", "This record no longer exists.", HTTPStatus.NOT_FOUND)
        _guard_record_revision(expected, actual)
        try:
            delete(record_id)
        except sqlite3.IntegrityError as exc:
            raise BridgeError("record_in_use", "This record is still used by other business data and cannot be deleted.", HTTPStatus.CONFLICT) from exc
    return {"type": entry_type, "id": record_id, "deleted": True}


def get_vendor_detail(vendor_id: int) -> dict[str, Any]:
    vendor = vendor_repository.get_vendor(vendor_id)
    if vendor is None:
        raise BridgeError("not_found", "Vendor not found.", HTTPStatus.NOT_FOUND)
    materials = material_repository.list_materials()
    vendors = {vendor.id: vendor}
    payload = _vendor_workspace_dto(vendor, materials)
    payload["materials"] = [
        _material_dto(material, vendors)
        for material in materials
        if material.vendor_id == vendor.id
    ]
    return payload


def _material_dto(material: Any, vendors: dict[int, Any]) -> dict[str, Any]:
    vendor = vendors.get(material.vendor_id) if material.vendor_id else None
    if material.quantity_on_hand <= material.reorder_point:
        stock_status = "reorder"
    elif material.quantity_on_hand <= material.reorder_point * 1.5:
        stock_status = "low"
    else:
        stock_status = "healthy"
    payload = {
        "id": material.id,
        "sku": material.sku,
        "name": material.name,
        "category": material.category,
        "description": material.description,
        "unit_of_measure": material.unit_of_measure,
        "quantity_on_hand": material.quantity_on_hand,
        "reorder_point": material.reorder_point,
        "cost_per_unit": _money(material.cost_per_unit),
        "inventory_value": _money(material.inventory_value),
        "vendor_id": material.vendor_id,
        "vendor": _vendor_dto(vendor) if vendor else None,
        "last_restocked": material.last_restocked.isoformat() if material.last_restocked else None,
        "lead_time_days": material.lead_time_days,
        "notes": material.notes,
        "stock_status": stock_status,
    }
    revision_values = {key: value for key, value in payload.items() if key not in {"inventory_value", "vendor", "stock_status"}}
    payload["revision"] = _record_revision(revision_values)
    return payload


def search_materials(query: str = "", limit: int = 100) -> list[dict[str, Any]]:
    term = query.strip().casefold()
    vendors = {vendor.id: vendor for vendor in vendor_repository.list_vendors() if vendor.id is not None}
    matches = []
    for material in material_repository.list_materials():
        vendor = vendors.get(material.vendor_id) if material.vendor_id else None
        searchable = " ".join(
            (material.sku, material.name, material.category, material.description, vendor.name if vendor else "")
        ).casefold()
        if term and term not in searchable:
            continue
        matches.append(_material_dto(material, vendors))
        if len(matches) >= min(max(limit, 1), 250):
            break
    return matches


def get_material_detail(material_id: int) -> dict[str, Any]:
    material = material_repository.get_material(material_id)
    if material is None or material.archived:
        raise BridgeError("not_found", "Material not found.", HTTPStatus.NOT_FOUND)
    vendors = {vendor.id: vendor for vendor in vendor_repository.list_vendors() if vendor.id is not None}
    payload = _material_dto(material, vendors)
    payload["transactions"] = [
        {
            "id": transaction.id,
            "transaction_date": transaction.transaction_date.isoformat(),
            "quantity_delta": transaction.quantity_delta,
            "unit_cost": _money(transaction.unit_cost),
            "reason": transaction.reason,
            "reference_type": transaction.reference_type,
            "reference_id": transaction.reference_id,
            "notes": transaction.notes,
        }
        for transaction in material_repository.fetch_transactions(material_id, limit=20)
    ]
    return payload


def adjust_material_inventory(material_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    values = payload.get("values")
    if not isinstance(values, dict):
        raise BridgeError("validation_failed", "Adjustment values are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})
    action = str(values.get("action", "")).strip().casefold()
    if action not in {"receive", "consume", "count"}:
        raise BridgeError("validation_failed", "Choose how the inventory changed.", HTTPStatus.BAD_REQUEST, {"action": "invalid_choice"})
    quantity = _nonnegative_number(values, "quantity", "Quantity", positive=action != "count")

    with MUTATION_LOCK:
        material = material_repository.get_material(material_id)
        if material is None or material.archived:
            raise BridgeError("not_found", "Material not found.", HTTPStatus.NOT_FOUND)
        vendors = {vendor.id: vendor for vendor in vendor_repository.list_vendors() if vendor.id is not None}
        _guard_record_revision(str(payload.get("expected_revision", "")).strip(), _material_dto(material, vendors)["revision"])

        if action == "receive":
            delta = quantity
            reason = "Stock received"
        elif action == "consume":
            delta = -quantity
            reason = "Material used"
        else:
            delta = quantity - material.quantity_on_hand
            reason = "Stock count correction"
        if abs(delta) < 1e-9:
            raise BridgeError("validation_failed", "The adjustment does not change the quantity on hand.", HTTPStatus.BAD_REQUEST, {"quantity": "no_change"})
        if material.quantity_on_hand + delta < -1e-9:
            raise BridgeError("validation_failed", "This adjustment would make inventory negative.", HTTPStatus.BAD_REQUEST, {"quantity": "exceeds_on_hand"})

        raw_unit_cost = values.get("unit_cost")
        unit_cost = material.cost_per_unit if raw_unit_cost in {None, ""} else _nonnegative_number(values, "unit_cost", "Unit cost")
        material_repository.apply_material_delta(
            material_id,
            delta,
            unit_cost=unit_cost,
            reason=reason,
            reference_type=f"browser_{action}",
            created_by="Browser",
            notes=_optional_text(values, "notes", 1000),
        )
    return get_material_detail(material_id)


def _line_dto(item: OrderItem, line_id: Optional[int] = None) -> dict[str, Any]:
    return {
        "id": line_id,
        "product_id": item.product_id,
        "sku": item.product_sku,
        "name": item.product_name,
        "description": item.product_description,
        "quantity": item.quantity,
        "unit_price": _money(item.unit_price),
        "unit_cost": _money(item.unit_cost),
        "line_total": _money(item.line_total),
        "line_profit": _money(item.line_profit),
        "is_freebie": item.is_freebie,
    }


def _order_event_dto(event: Any, available_order_ids: Optional[set[int]] = None) -> dict[str, Any]:
    event_name = event.event_type.strip().casefold()
    tone = "critical" if any(word in event_name for word in ("cancel", "delete")) else ("positive" if any(word in event_name for word in ("created", "paid", "payment")) else "neutral")
    return {
        "id": event.id,
        "order_id": event.order_id,
        "order_number": event.order_number,
        "event_type": event.event_type,
        "description": event.description,
        "amount_delta": _money(event.amount_delta),
        "created_at": event.created_at.isoformat(),
        "tone": tone,
        "order_available": bool(event.order_id and (available_order_ids is None or event.order_id in available_order_ids)),
    }


def history_workspace(order_query: str = "", start_date: Optional[date] = None, end_date: Optional[date] = None, limit: int = 200) -> dict[str, Any]:
    events = order_service.list_order_history(order_number=order_query or None, start_date=start_date, end_date=end_date, limit=min(max(limit, 1), 500))
    event_order_ids = {event.order_id for event in events if event.order_id is not None}
    available_order_ids: set[int] = set()
    if event_order_ids:
        placeholders = ",".join("?" for _ in event_order_ids)
        with create_connection() as connection:
            rows = connection.execute(f"SELECT id FROM orders WHERE id IN ({placeholders}) AND deleted_at IS NULL", tuple(event_order_ids)).fetchall()
        available_order_ids = {int(row["id"]) for row in rows}
    event_types: dict[str, int] = {}
    for event in events:
        event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
    return {
        "events": [_order_event_dto(event, available_order_ids) for event in events],
        "event_types": [{"name": name, "count": count} for name, count in sorted(event_types.items(), key=lambda item: (-item[1], item[0].casefold()))],
        "metrics": {
            "total": len(events),
            "orders": len({event.order_number for event in events}),
            "net_change": _money(sum(event.amount_delta for event in events)),
            "latest_at": events[0].created_at.isoformat() if events else None,
        },
        "filters": {"query": order_query, "start_date": start_date.isoformat() if start_date else None, "end_date": end_date.isoformat() if end_date else None},
    }


def _attention_reasons(order: Order) -> list[str]:
    reasons: list[str] = []
    if not order.is_paid:
        reasons.append("payment_outstanding")
    if (
        order.target_completion_date
        and order.target_completion_date < date.today()
        and order.status != "Shipped"
    ):
        reasons.append("overdue")
    if order.target_completion_date == date.today() and order.status != "Shipped":
        reasons.append("due_today")
    return reasons


def order_dto(order: Order, contacts: Optional[dict[str, CRMContact]] = None) -> dict[str, Any]:
    contact = (contacts or {}).get(order.customer_name.strip().casefold())
    subtotal = order.total_amount
    total = order.display_total
    customer = {
        "id": contact.id if contact else None,
        "name": order.customer_name,
        "email": contact.email if contact else "",
        "phone": contact.phone if contact else "",
        "address": order.customer_address or (contact.address if contact else ""),
    }
    return {
        "id": order.id,
        "number": order.order_number,
        "customer_id": customer["id"],
        "customer_name": order.customer_name,
        "customer": customer,
        "order_date": order.order_date.isoformat(),
        "target_completion_date": (
            order.target_completion_date.isoformat() if order.target_completion_date else None
        ),
        "ship_date": order.ship_date.isoformat() if order.ship_date else None,
        "status": order.status,
        "payment_status": "paid" if order.is_paid else "unpaid",
        "subtotal": _money(subtotal),
        "tax_rate": _money(order.tax_rate),
        "tax_amount": _money(order.tax_amount),
        "total": _money(total),
        "item_count": sum(item.quantity for item in order.items),
        "attention_reasons": _attention_reasons(order),
        "items": [_line_dto(item) for item in order.items],
        "shipping": {
            "address": order.customer_address,
            "carrier": order.carrier,
            "tracking_number": order.tracking_number,
        },
        "notes": order.notes,
        "documents": [],
        "activity": [],
    }


def list_orders(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = min(max(int(limit), 1), 200)
    contacts = _contact_index()
    return [order_dto(order, contacts) for order in order_repository.fetch_orders(safe_limit)]


def get_order(order_id: int) -> dict[str, Any]:
    order = order_repository.fetch_order(order_id)
    if order is None:
        raise BridgeError("not_found", "Order not found.", HTTPStatus.NOT_FOUND)
    payload = order_dto(order, _contact_index())
    events = [event for event in order_service.list_order_history(order_number=order.order_number, limit=50) if event.order_id == order_id or (event.order_id is None and event.order_number == order.order_number)]
    payload["activity"] = [_order_event_dto(event, {order_id}) for event in events[:25]]
    return payload


def order_metrics() -> dict[str, Any]:
    orders = order_repository.fetch_orders(200)
    open_orders = [order for order in orders if order.status not in {"Shipped", "Cancelled"}]
    unpaid = [order for order in open_orders if not order.is_paid]
    ready = [order for order in open_orders if order.status == "Ready to Ship"]
    attention = [order for order in open_orders if _attention_reasons(order)]
    return {
        "open_orders": len(open_orders),
        "awaiting_payment": _money(sum(order.display_total for order in unpaid)),
        "awaiting_payment_count": len(unpaid),
        "ready_to_ship": len(ready),
        "needs_attention": len(attention),
    }


def _order_number(reserve: bool = False) -> str:
    settings = settings_repository.get_app_settings()
    sequence = max(1, settings.order_number_next)
    try:
        number = settings.order_number_format.format(seq=sequence).strip()
    except (KeyError, ValueError, IndexError):
        number = f"ORD-{sequence:04d}"
    if not number:
        number = f"ORD-{sequence:04d}"
    if reserve:
        settings_repository.set_setting("order_number_next", str(sequence + 1))
    return number


def order_options() -> dict[str, Any]:
    settings = settings_repository.get_app_settings()
    return {
        "statuses": list(ORDER_STATUSES),
        "carriers": ["USPS", "UPS", "FedEx", "Local pickup", "Delivered"],
        "tax_rate_percent": _money(settings.tax_rate_percent),
        "tax_add_to_total": settings.tax_add_to_total,
        "next_order_number": _order_number(),
    }


def _parse_date(value: Any, field: str, fields: dict[str, str], *, required: bool) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        if required:
            fields[field] = "required"
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        fields[field] = "invalid_date"
        return None


def _parse_price(value: Any, field: str, fields: dict[str, str]) -> float:
    try:
        parsed = Decimal(str(value))
    except Exception:
        fields[field] = "invalid_number"
        return 0.0
    if parsed < 0:
        fields[field] = "must_be_positive"
        return 0.0
    return float(parsed.quantize(Decimal("0.01")))


def _build_order_from_draft(draft: dict[str, Any], existing: Optional[Order] = None) -> Order:
    fields: dict[str, str] = {}
    customer = draft.get("customer") if isinstance(draft.get("customer"), dict) else {}
    customer_name = str(customer.get("name", "")).strip()
    customer_address = str(customer.get("address", "")).strip()
    if not customer_name:
        fields["customer.name"] = "required"
    if not customer_address:
        fields["customer.address"] = "required"

    order_date = _parse_date(
        draft.get("order_date") or (existing.order_date.isoformat() if existing else date.today().isoformat()),
        "order_date",
        fields,
        required=True,
    )
    target_date = _parse_date(
        draft.get("target_completion_date"),
        "target_completion_date",
        fields,
        required=False,
    )
    if order_date and target_date and target_date < order_date:
        fields["target_completion_date"] = "before_order_date"

    raw_items = draft.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        fields["items"] = "required"
        raw_items = []

    items: list[OrderItem] = []
    for index, raw_item in enumerate(raw_items):
        prefix = f"items.{index}"
        if not isinstance(raw_item, dict):
            fields[prefix] = "invalid"
            continue
        try:
            product_id = int(raw_item.get("product_id"))
        except (TypeError, ValueError):
            fields[f"{prefix}.product_id"] = "required"
            continue
        product = product_repository.get_product_by_id(product_id)
        if product is None:
            fields[f"{prefix}.product_id"] = "not_found"
            continue
        try:
            quantity = int(raw_item.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        if quantity <= 0:
            fields[f"{prefix}.quantity"] = "must_be_positive"
        unit_price = _parse_price(raw_item.get("unit_price", product.default_unit_price), f"{prefix}.unit_price", fields)
        items.append(
            OrderItem(
                product_id=product.id,
                product_sku=product.sku,
                product_name=product.name,
                product_description=str(raw_item.get("description", product.description)).strip(),
                quantity=max(quantity, 0),
                unit_price=unit_price,
                base_unit_cost=product.base_unit_cost,
                cost_components=list(product.pricing_components),
                is_freebie=bool(raw_item.get("is_freebie", False)),
            )
        )

    status = str(draft.get("status") or (existing.status if existing else "Received")).strip()
    if status not in ORDER_STATUSES:
        fields["status"] = "invalid"
    if fields:
        raise BridgeError(
            "validation_failed",
            "Review the highlighted order fields.",
            HTTPStatus.UNPROCESSABLE_ENTITY,
            fields,
        )

    settings = settings_repository.get_app_settings()
    subtotal = sum(item.line_total for item in items)
    tax_rate = max(0.0, min(100.0, settings.tax_rate_percent)) / 100.0
    tax_amount = round(subtotal * tax_rate, 2)
    ship_date = existing.ship_date if existing else None
    if status == "Shipped" and ship_date is None:
        ship_date = date.today()
    return Order(
        id=existing.id if existing else None,
        order_number=existing.order_number if existing else _order_number(reserve=True),
        customer_name=customer_name,
        customer_address=customer_address,
        order_date=order_date or date.today(),
        target_completion_date=target_date,
        status=status,
        is_paid=str(draft.get("payment_status", "unpaid")) == "paid",
        carrier=str(draft.get("carrier", "")).strip(),
        tracking_number=str(draft.get("tracking_number", "")).strip(),
        notes=str(draft.get("notes", "")).strip(),
        ship_date=ship_date,
        items=items,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        tax_included_in_total=settings.tax_add_to_total,
    )


def _item_quantities(order: Order) -> dict[str, int]:
    quantities: dict[str, int] = {}
    for item in order.items:
        key = item.product_sku.strip().upper()
        quantities[key] = quantities.get(key, 0) + item.quantity
    return quantities


def _sync_customer(draft: dict[str, Any]) -> None:
    raw = draft.get("customer")
    if not isinstance(raw, dict):
        return
    name = str(raw.get("name", "")).strip()
    if not name:
        return
    existing = None
    try:
        contact_id = int(raw.get("id"))
    except (TypeError, ValueError):
        contact_id = 0
    if contact_id:
        existing = crm_repository.get_contact(contact_id)
    if existing is None:
        existing = next(
            (
                contact
                for contact in crm_repository.list_contacts()
                if contact.customer_name.strip().casefold() == name.casefold()
            ),
            None,
        )
    crm_repository.save_contact(
        CRMContact(
            id=existing.id if existing else None,
            customer_name=name,
            company=existing.company if existing else "",
            email=str(raw.get("email", "")).strip(),
            phone=str(raw.get("phone", "")).strip(),
            address=str(raw.get("address", "")).strip(),
            tags=list(existing.tags) if existing else [],
            created_at=existing.created_at if existing else None,
            last_contacted=existing.last_contacted if existing else None,
            next_follow_up=existing.next_follow_up if existing else None,
            preferred_channel=existing.preferred_channel if existing else "",
            notes=existing.notes if existing else "",
        )
    )


def create_order(draft: dict[str, Any]) -> dict[str, Any]:
    with MUTATION_LOCK:
        order = _build_order_from_draft(draft)
        try:
            order_id = order_repository.insert_order(order)
        except Exception as exc:
            LOGGER.exception("Order creation failed")
            raise BridgeError(
                "order_number_conflict",
                "The next order number is already in use. Review numbering settings and try again.",
                HTTPStatus.CONFLICT,
            ) from exc
        for sku, quantity in _item_quantities(order).items():
            product_repository.adjust_inventory(sku, -quantity)
        order_repository.log_order_event(
            order_id,
            order.order_number,
            "Created",
            f"Order created from browser workspace with {len(order.items)} line items.",
            order.display_total,
        )
        _sync_customer(draft)
    return get_order(order_id)


def update_order_from_draft(order_id: int, draft: dict[str, Any]) -> dict[str, Any]:
    with MUTATION_LOCK:
        existing = order_repository.fetch_order(order_id)
        if existing is None:
            raise BridgeError("not_found", "Order not found.", HTTPStatus.NOT_FOUND)
        expected_status = str(draft.get("expected_status", "")).strip()
        if expected_status and expected_status != existing.status:
            raise BridgeError(
                "status_conflict",
                "The order changed in another window. Refresh and try again.",
                HTTPStatus.CONFLICT,
            )
        updated = _build_order_from_draft(draft, existing)
        old_quantities = _item_quantities(existing)
        new_quantities = _item_quantities(updated)
        order_repository.update_order(order_id, updated)
        for sku in sorted(set(old_quantities) | set(new_quantities)):
            difference = new_quantities.get(sku, 0) - old_quantities.get(sku, 0)
            if difference:
                product_repository.adjust_inventory(sku, -difference)
        order_repository.log_order_event(
            order_id,
            updated.order_number,
            "Updated",
            "Order updated from browser workspace.",
            updated.display_total - existing.display_total,
        )
        _sync_customer(draft)
    return get_order(order_id)


def advance_order(order_id: int, expected_status: str) -> dict[str, Any]:
    expected = expected_status.strip()
    if expected not in ORDER_STATUSES:
        raise BridgeError("invalid_status", "The current status is not recognized.", HTTPStatus.BAD_REQUEST)
    current_index = ORDER_STATUSES.index(expected)
    if current_index == len(ORDER_STATUSES) - 1:
        raise BridgeError("already_complete", "The order is already complete.", HTTPStatus.CONFLICT)

    next_status = ORDER_STATUSES[current_index + 1]
    ship_date = date.today().isoformat() if next_status == "Shipped" else None
    with create_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE orders
            SET status = ?,
                is_paid = CASE WHEN ? = 'Paid' THEN 1 ELSE is_paid END,
                ship_date = CASE WHEN ? = 'Shipped' THEN ? ELSE ship_date END
            WHERE id = ?
              AND status = ?
              AND deleted_at IS NULL
            """,
            (next_status, next_status, next_status, ship_date, int(order_id), expected),
        )
        if cursor.rowcount != 1:
            exists = connection.execute(
                "SELECT status FROM orders WHERE id = ? AND deleted_at IS NULL", (int(order_id),)
            ).fetchone()
            if exists is None:
                raise BridgeError("not_found", "Order not found.", HTTPStatus.NOT_FOUND)
            raise BridgeError(
                "status_conflict",
                "The order changed in another window. Refresh and try again.",
                HTTPStatus.CONFLICT,
            )
        row = connection.execute(
            "SELECT order_number FROM orders WHERE id = ?", (int(order_id),)
        ).fetchone()
        connection.execute(
            """
            INSERT INTO order_history (order_id, order_number, event_type, description, amount_delta)
            VALUES (?, ?, 'Status changed', ?, 0)
            """,
            (int(order_id), row["order_number"], f"Status changed from {expected} to {next_status}."),
        )
        connection.commit()
    return get_order(order_id)


def update_order_payment(order_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    expected = str(payload.get("expected_payment_status", "")).strip().casefold()
    requested = str(payload.get("payment_status", "")).strip().casefold()
    if expected not in {"paid", "unpaid"} or requested not in {"paid", "unpaid"}:
        raise BridgeError("validation_failed", "Choose a valid payment status.", HTTPStatus.BAD_REQUEST, {"payment_status": "invalid_choice"})
    with MUTATION_LOCK, create_connection() as connection:
        row = connection.execute(
            "SELECT order_number, is_paid FROM orders WHERE id = ? AND deleted_at IS NULL",
            (int(order_id),),
        ).fetchone()
        if row is None:
            raise BridgeError("not_found", "Order not found.", HTTPStatus.NOT_FOUND)
        actual = "paid" if bool(row["is_paid"]) else "unpaid"
        if actual != expected:
            raise BridgeError("payment_conflict", "The payment status changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
        if requested != actual:
            connection.execute("UPDATE orders SET is_paid = ? WHERE id = ?", (int(requested == "paid"), int(order_id)))
            connection.execute(
                "INSERT INTO order_history (order_id, order_number, event_type, description, amount_delta) VALUES (?, ?, 'Payment changed', ?, 0)",
                (int(order_id), row["order_number"], f"Payment marked {requested} from browser workspace."),
            )
            connection.commit()
    return get_order(order_id)


def cancel_order_from_browser(order_id: int, expected_status: str) -> dict[str, Any]:
    with MUTATION_LOCK:
        order = order_repository.fetch_order(order_id)
        if order is None:
            raise BridgeError("not_found", "Order not found.", HTTPStatus.NOT_FOUND)
        if expected_status.strip() != order.status:
            raise BridgeError("status_conflict", "The order changed in another window. Refresh and try again.", HTTPStatus.CONFLICT)
        if order.status == "Cancelled":
            raise BridgeError("already_cancelled", "The order is already cancelled.", HTTPStatus.CONFLICT)
        order_service.cancel_order(order_id)
    return get_order(order_id)


def invoice_download(order_id: int) -> BinaryDownload:
    order = order_repository.fetch_order(order_id)
    if order is None:
        raise BridgeError("not_found", "Order not found.", HTTPStatus.NOT_FOUND)
    safe_number = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in order.order_number).strip("_") or f"order-{order_id}"
    filename = f"{safe_number}_{'receipt' if order.is_paid else 'invoice'}.pdf"
    with TemporaryDirectory(prefix="hustlenest-invoice-") as directory:
        path = order_service.export_order_invoice(order_id, str(Path(directory) / filename))
        content = path.read_bytes()
    return BinaryDownload(filename=filename, content_type="application/pdf", content=content)


@dataclass
class BridgeApplication:
    def dispatch(self, method: str, target: str, body: Optional[dict[str, Any]] = None) -> tuple[HTTPStatus, Any]:
        parsed = urlparse(target)
        path = parsed.path.rstrip("/") or "/"
        if method == "GET" and path == "/health":
            return HTTPStatus.OK, {"service": "HustleNest Orders bridge", "status": "ready"}
        if method == "GET" and path == "/api/orders":
            raw_limit = parse_qs(parsed.query).get("limit", ["50"])[0]
            try:
                limit = int(raw_limit)
            except ValueError as exc:
                raise BridgeError("invalid_limit", "Limit must be a number.", HTTPStatus.BAD_REQUEST) from exc
            return HTTPStatus.OK, list_orders(limit)
        if method == "GET" and path == "/api/orders/metrics":
            return HTTPStatus.OK, order_metrics()
        if method == "GET" and path == "/api/order-options":
            return HTTPStatus.OK, order_options()
        if method == "GET" and path in {"/api/customers", "/api/products"}:
            query = parse_qs(parsed.query)
            term = query.get("query", [""])[0]
            try:
                limit = int(query.get("limit", ["30"])[0])
            except ValueError as exc:
                raise BridgeError("invalid_limit", "Limit must be a number.", HTTPStatus.BAD_REQUEST) from exc
            if path == "/api/customers":
                return HTTPStatus.OK, search_customers(term, limit)
            return HTTPStatus.OK, search_products(term, limit)
        if method == "POST" and path == "/api/customers/promote":
            return HTTPStatus.CREATED, promote_order_customer(body or {})
        if method == "GET" and path == "/api/materials":
            query = parse_qs(parsed.query)
            term = query.get("query", [""])[0]
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError as exc:
                raise BridgeError("invalid_limit", "Limit must be a number.", HTTPStatus.BAD_REQUEST) from exc
            return HTTPStatus.OK, search_materials(term, limit)
        if method == "GET" and path == "/api/vendors":
            query = parse_qs(parsed.query)
            term = query.get("query", [""])[0]
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError as exc:
                raise BridgeError("invalid_limit", "Limit must be a number.", HTTPStatus.BAD_REQUEST) from exc
            return HTTPStatus.OK, search_vendors(term, limit)
        if method == "GET" and path == "/api/finance":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError as exc:
                raise BridgeError("invalid_limit", "Limit must be a number.", HTTPStatus.BAD_REQUEST) from exc
            return HTTPStatus.OK, finance_workspace(limit)
        if method == "GET" and path == "/api/reports":
            period = parse_qs(parsed.query).get("period", ["this_year"])[0]
            return HTTPStatus.OK, reports_workspace(period)
        if method == "GET" and path == "/api/reports/export":
            return HTTPStatus.OK, report_download(parse_qs(parsed.query))
        if method == "GET" and path == "/api/history":
            query = parse_qs(parsed.query)
            order_query = query.get("query", [""])[0].strip()[:120]
            start_date = _date_field({"start_date": query.get("start_date", [""])[0]}, "start_date", "Start date", required=False)
            end_date = _date_field({"end_date": query.get("end_date", [""])[0]}, "end_date", "End date", required=False)
            if start_date and end_date and end_date < start_date:
                raise BridgeError("validation_failed", "End date cannot be before the start date.", HTTPStatus.BAD_REQUEST, {"end_date": "before_start"})
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError as exc:
                raise BridgeError("invalid_limit", "Limit must be a number.", HTTPStatus.BAD_REQUEST) from exc
            return HTTPStatus.OK, history_workspace(order_query, start_date, end_date, limit)
        if method == "GET" and path == "/api/geography":
            return HTTPStatus.OK, geography_workspace()
        if method == "GET" and path == "/api/trash":
            return HTTPStatus.OK, trash_workspace()
        if method == "DELETE" and path == "/api/trash":
            return HTTPStatus.OK, empty_browser_trash(body or {})
        if method == "GET" and path == "/api/home":
            return HTTPStatus.OK, home_workspace()
        if method == "GET" and path == "/api/about":
            return HTTPStatus.OK, about_workspace()
        if method == "GET" and path == "/api/goals":
            return HTTPStatus.OK, goals_workspace()
        if method == "POST" and path == "/api/goals":
            return HTTPStatus.CREATED, save_goal_from_browser(body or {})
        if method == "GET" and path == "/api/documents":
            return HTTPStatus.OK, documents_workspace()
        if method == "POST" and path == "/api/documents":
            return HTTPStatus.CREATED, create_document_from_browser(body or {})
        if method == "GET" and path == "/api/settings":
            return HTTPStatus.OK, settings_workspace()
        if method == "PUT" and path == "/api/settings":
            return HTTPStatus.OK, update_settings(body or {})
        if method == "GET" and path == "/api/settings/logo":
            return HTTPStatus.OK, download_dashboard_logo()
        if method == "POST" and path == "/api/settings/logo":
            return HTTPStatus.OK, save_dashboard_logo(body or {})
        if method == "DELETE" and path == "/api/settings/logo":
            return HTTPStatus.OK, delete_dashboard_logo(body or {})
        if method == "GET" and path == "/api/settings/profile/avatar":
            return HTTPStatus.OK, download_profile_avatar()
        if method == "POST" and path == "/api/settings/profile/avatar":
            return HTTPStatus.OK, save_profile_avatar(body or {})
        if method == "DELETE" and path == "/api/settings/profile/avatar":
            return HTTPStatus.OK, delete_profile_avatar(body or {})
        if method == "GET" and path == "/api/sync-settings":
            return HTTPStatus.OK, cloud_sync_workspace()
        if method == "PUT" and path == "/api/sync-settings":
            return HTTPStatus.OK, update_cloud_sync_from_browser(body or {})
        if method == "POST" and path == "/api/sync-settings/upload":
            return HTTPStatus.OK, upload_cloud_database(body or {})
        if method == "POST" and path == "/api/sync-settings/pull":
            return HTTPStatus.OK, pull_cloud_database(body or {})
        if method == "POST" and path == "/api/sync-settings/authorize-google":
            return HTTPStatus.OK, authorize_google_cloud(body or {})
        if method == "GET" and path == "/api/backups":
            return HTTPStatus.OK, backup_workspace()
        if method == "PUT" and path == "/api/backups":
            return HTTPStatus.OK, update_backup_settings(body or {})
        if method == "POST" and path == "/api/backups":
            return HTTPStatus.CREATED, create_browser_backup(body or {})
        if method == "POST" and path == "/api/imports/preview":
            return HTTPStatus.OK, preview_browser_import(body or {})
        if method == "POST" and path == "/api/imports/execute":
            return HTTPStatus.OK, execute_browser_import(body or {})
        if method == "POST" and path == "/api/quick-add":
            return HTTPStatus.CREATED, create_quick_entry(body or {})
        if method == "POST" and path == "/api/orders":
            return HTTPStatus.CREATED, create_order(body or {})

        adjustment_segments = [segment for segment in path.split("/") if segment]
        if method == "POST" and len(adjustment_segments) == 4 and adjustment_segments[:2] == ["api", "materials"] and adjustment_segments[3] == "adjust":
            try:
                material_id = int(adjustment_segments[2])
            except ValueError as exc:
                raise BridgeError("invalid_material_id", "Material id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            return HTTPStatus.OK, adjust_material_inventory(material_id, body or {})

        record_segments = [segment for segment in path.split("/") if segment]
        if len(record_segments) == 4 and record_segments[:2] == ["api", "records"]:
            try:
                record_id = int(record_segments[3])
            except ValueError as exc:
                raise BridgeError("invalid_record_id", "Record id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            if method == "PUT":
                values = (body or {}).get("values")
                if not isinstance(values, dict):
                    raise BridgeError("validation_failed", "Entry values are required.", HTTPStatus.BAD_REQUEST, {"values": "required"})
                return HTTPStatus.OK, update_operational_entry(record_segments[2], record_id, values, str((body or {}).get("expected_revision", "")).strip())
            if method == "DELETE":
                return HTTPStatus.OK, delete_operational_entry(record_segments[2], record_id, body or {})

        trash_segments = [segment for segment in path.split("/") if segment]
        if len(trash_segments) >= 4 and trash_segments[:2] == ["api", "trash"]:
            item_type = trash_segments[2]
            try:
                item_id = int(trash_segments[3])
            except ValueError as exc:
                raise BridgeError("invalid_trash_item_id", "Trash item id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            if method == "POST" and len(trash_segments) == 5 and trash_segments[4] == "restore":
                return HTTPStatus.OK, mutate_trash_item(item_type, item_id, "restore", body or {})
            if method == "DELETE" and len(trash_segments) == 4:
                return HTTPStatus.OK, mutate_trash_item(item_type, item_id, "delete", body or {})

        product_segments = [segment for segment in path.split("/") if segment]
        if len(product_segments) == 4 and product_segments[:2] == ["api", "products"] and product_segments[3] == "photo":
            try:
                product_id = int(product_segments[2])
            except ValueError as exc:
                raise BridgeError("invalid_product_id", "Product id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            if method == "POST":
                return HTTPStatus.OK, save_product_photo(product_id, body or {})
            if method == "GET":
                return HTTPStatus.OK, download_product_photo(product_id)
            if method == "DELETE":
                return HTTPStatus.OK, delete_product_photo(product_id, body or {})

        backup_segments = [segment for segment in path.split("/") if segment]
        if len(backup_segments) >= 3 and backup_segments[:2] == ["api", "backups"]:
            backup_id = backup_segments[2]
            if method == "GET" and len(backup_segments) == 4 and backup_segments[3] == "download":
                return HTTPStatus.OK, download_backup(backup_id)
            if method == "POST" and len(backup_segments) == 4 and backup_segments[3] == "restore":
                return HTTPStatus.OK, restore_browser_backup(backup_id, body or {})

        material_segments = [segment for segment in path.split("/") if segment]
        if method == "GET" and len(material_segments) == 3 and material_segments[:2] == ["api", "materials"]:
            try:
                material_id = int(material_segments[2])
            except ValueError as exc:
                raise BridgeError("invalid_material_id", "Material id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            return HTTPStatus.OK, get_material_detail(material_id)

        vendor_segments = [segment for segment in path.split("/") if segment]
        if method == "GET" and len(vendor_segments) == 3 and vendor_segments[:2] == ["api", "vendors"]:
            try:
                vendor_id = int(vendor_segments[2])
            except ValueError as exc:
                raise BridgeError("invalid_vendor_id", "Vendor id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            return HTTPStatus.OK, get_vendor_detail(vendor_id)

        customer_segments = [segment for segment in path.split("/") if segment]
        if len(customer_segments) >= 3 and customer_segments[:2] == ["api", "customers"]:
            try:
                contact_id = int(customer_segments[2])
            except ValueError as exc:
                raise BridgeError("invalid_customer_id", "Customer id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            if method == "GET" and len(customer_segments) == 3:
                return HTTPStatus.OK, get_customer_detail(contact_id)
            if method == "POST" and len(customer_segments) == 4 and customer_segments[3] == "interactions":
                return HTTPStatus.CREATED, log_customer_interaction(contact_id, body or {})
            if method == "DELETE" and len(customer_segments) == 5 and customer_segments[3] == "interactions":
                try:
                    interaction_id = int(customer_segments[4])
                except ValueError as exc:
                    raise BridgeError("invalid_interaction_id", "Interaction id must be a number.", HTTPStatus.BAD_REQUEST) from exc
                return HTTPStatus.OK, delete_customer_interaction(contact_id, interaction_id, body or {})

        goal_segments = [segment for segment in path.split("/") if segment]
        if len(goal_segments) >= 3 and goal_segments[:2] == ["api", "goals"]:
            try:
                goal_id = int(goal_segments[2])
            except ValueError as exc:
                raise BridgeError("invalid_goal_id", "Goal id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            if method == "PUT" and len(goal_segments) == 3:
                return HTTPStatus.OK, save_goal_from_browser(body or {}, goal_id)
            if method == "DELETE" and len(goal_segments) == 3:
                return HTTPStatus.OK, delete_goal_from_browser(goal_id, body or {})
            if method == "POST" and len(goal_segments) == 4 and goal_segments[3] == "checkpoints":
                return HTTPStatus.CREATED, add_goal_checkpoint(goal_id, body or {})

        document_segments = [segment for segment in path.split("/") if segment]
        if len(document_segments) >= 3 and document_segments[:2] == ["api", "documents"]:
            try:
                document_id = int(document_segments[2])
            except ValueError as exc:
                raise BridgeError("invalid_document_id", "Document id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            if method == "PUT" and len(document_segments) == 3:
                return HTTPStatus.OK, update_document_from_browser(document_id, body or {})
            if method == "DELETE" and len(document_segments) == 3:
                return HTTPStatus.OK, delete_document_from_browser(document_id, body or {})
            if method == "GET" and len(document_segments) == 4 and document_segments[3] == "download":
                return HTTPStatus.OK, download_document(document_id)

        segments = [segment for segment in path.split("/") if segment]
        if len(segments) >= 3 and segments[:2] == ["api", "orders"]:
            try:
                order_id = int(segments[2])
            except ValueError as exc:
                raise BridgeError("invalid_order_id", "Order id must be a number.", HTTPStatus.BAD_REQUEST) from exc
            if method == "GET" and len(segments) == 3:
                return HTTPStatus.OK, get_order(order_id)
            if method == "POST" and len(segments) == 4 and segments[3] == "advance":
                return HTTPStatus.OK, advance_order(order_id, str((body or {}).get("expected_status", "")))
            if method == "POST" and len(segments) == 4 and segments[3] == "payment":
                return HTTPStatus.OK, update_order_payment(order_id, body or {})
            if method == "POST" and len(segments) == 4 and segments[3] == "cancel":
                return HTTPStatus.OK, cancel_order_from_browser(order_id, str((body or {}).get("expected_status", "")))
            if method == "GET" and len(segments) == 4 and segments[3] == "invoice":
                return HTTPStatus.OK, invoice_download(order_id)
            if method == "PUT" and len(segments) == 3:
                return HTTPStatus.OK, update_order_from_draft(order_id, body or {})
            if method == "DELETE" and len(segments) == 3:
                return HTTPStatus.OK, move_record_to_trash("order", order_id, body or {})

        raise BridgeError("not_found", "Endpoint not found.", HTTPStatus.NOT_FOUND)


class BridgeRequestHandler(BaseHTTPRequestHandler):
    server_version = "HustleNestBridge/0.3"
    application = BridgeApplication()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._handle("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle("DELETE")

    def _handle(self, method: str) -> None:
        try:
            body = self._read_json() if method in {"POST", "PUT", "DELETE"} else None
            status, data = self.application.dispatch(method, self.path, body)
            if isinstance(data, BinaryDownload):
                self._write_download(status, data)
            else:
                self._write_json(status, {"ok": True, "data": data})
        except BridgeError as exc:
            self._write_json(
                exc.status,
                {"ok": False, "error": {"code": exc.code, "message": exc.message, "fields": exc.fields}},
            )
        except Exception:
            LOGGER.exception("Unexpected bridge request failure")
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": {"code": "internal_error", "message": "The request could not be completed.", "fields": {}}},
            )

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise BridgeError("invalid_body", "Invalid request body.", HTTPStatus.BAD_REQUEST) from exc
        if length <= 0:
            return {}
        if length > MAX_JSON_BODY_BYTES:
            raise BridgeError("request_too_large", "Request body is too large.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BridgeError("invalid_json", "Request body must be valid JSON.", HTTPStatus.BAD_REQUEST) from exc
        if not isinstance(value, dict):
            raise BridgeError("invalid_body", "Request body must be an object.", HTTPStatus.BAD_REQUEST)
        return value

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _write_download(self, status: HTTPStatus, download: BinaryDownload) -> None:
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", download.content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{download.filename}"')
        self.send_header("Content-Length", str(len(download.content)))
        self.end_headers()
        self.wfile.write(download.content)

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin in {"http://localhost:3000", "http://127.0.0.1:3000"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

    def log_message(self, message: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), message % args)


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, browser_url: Optional[str] = None) -> None:
    initialize()
    order_service.ensure_invoice_runtime()
    server = ThreadingHTTPServer((host, port), BridgeRequestHandler)
    backup_stop = threading.Event()
    backup_thread = threading.Thread(target=_browser_backup_worker, args=(backup_stop,), name="HustleNestBackup", daemon=True)
    backup_thread.start()
    LOGGER.info("Orders bridge listening on http://%s:%s", host, port)
    if browser_url:
        launch_timer = threading.Timer(0.6, launch_configured_browser, args=(browser_url,))
        launch_timer.daemon = True
        launch_timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        backup_stop.set()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local HustleNest Orders bridge.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    parser.add_argument("--launch-browser", action="store_true", help="Open the configured browser after startup.")
    parser.add_argument("--browser-url", default="http://localhost:3000", help="Browser workspace URL to open.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(args.host, args.port, args.browser_url if args.launch_browser else None)


if __name__ == "__main__":
    main()
