from __future__ import annotations

import base64
import csv
import html
import json
import mimetypes
import shutil
import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from ..data import order_repository, product_repository, settings_repository
from ..data.database import get_storage_root
from ..models.order_models import (
    AppSettings,
    CostComponent,
    DashboardSnapshot,
    NotificationMessage,
    Order,
    OrderHistoryEvent,
    OrderItem,
    OrderReportRow,
    OutstandingOrder,
    OrderDestination,
    Product,
    ProductForecast,
    ProductSalesSummary,
)

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QFont, QPageSize, QPdfWriter, QTextDocument


_ORDER_STATUSES: List[str] = [
    "Received",
    "Paid",
    "Processing",
    "Ready to Ship",
    "Shipped",
    "Cancelled",
]

_PRODUCT_STATUSES: List[str] = [
    "Ordered",
    "Available",
    "Out of Stock",
    "Discontinued",
]

_DEFAULT_ORDER_NUMBER_FORMAT = "ORD-{seq:04d}"
_SEQUENCE_PATTERN = re.compile(r"(\d+)(?!.*\d)")
_CITY_STATE_PATTERN = re.compile(
    r"(?P<city>.+?),\s*(?P<state>[A-Za-z]{2})(?:\s+\d{5}(?:-\d{4})?)?$"
)
_SKU_ALIASES: Dict[str, str] = {
    "BC-0001": "BMETAL-CARD",
}
_VALID_LOGO_POSITIONS = {
    "top-left",
    "top-center",
    "top-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
}

_STORAGE_ROOT = get_storage_root()
_PRODUCT_MEDIA_ROOT = _STORAGE_ROOT / "media" / "products"


def _ensure_product_media_root() -> Path:
    _PRODUCT_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    return _PRODUCT_MEDIA_ROOT


def _product_media_relative(path: Path) -> str:
    try:
        return str(path.relative_to(_STORAGE_ROOT))
    except ValueError:
        return str(path)


def _is_managed_product_photo(path: Path) -> bool:
    try:
        path.relative_to(_PRODUCT_MEDIA_ROOT)
        return True
    except ValueError:
        return False


def _resolve_product_photo_path(value: str) -> Optional[Path]:
    if not value:
        return None
    raw = Path(value).expanduser()
    if raw.is_absolute() and raw.exists():
        return raw
    if not raw.is_absolute():
        candidate = (_STORAGE_ROOT / value).expanduser()
        if candidate.exists():
            return candidate
    if raw.exists():
        return raw
    return None


def _absolute_product_photo_path(value: str) -> Optional[Path]:
    if not value:
        return None
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw
    return (_STORAGE_ROOT / value).expanduser()


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _persist_product_photo(new_photo: str, sku: str, existing_photo: str) -> str:
    new_clean = new_photo.strip()
    existing_clean = existing_photo.strip()
    if not new_clean:
        existing_path = _absolute_product_photo_path(existing_clean)
        if existing_path and existing_path.exists() and _is_managed_product_photo(existing_path):
            _safe_unlink(existing_path)
        return ""

    if new_clean == existing_clean:
        resolved = _absolute_product_photo_path(existing_clean)
        if resolved and _is_managed_product_photo(resolved):
            return _product_media_relative(resolved)
        return existing_clean

    existing_path = _absolute_product_photo_path(existing_clean) if existing_clean else None
    resolved_new = _absolute_product_photo_path(new_clean)
    if resolved_new and resolved_new.exists():
        if existing_path and resolved_new == existing_path:
            return _product_media_relative(resolved_new) if _is_managed_product_photo(resolved_new) else str(resolved_new)
        if _is_managed_product_photo(resolved_new):
            if existing_path and existing_path.exists() and existing_path != resolved_new and _is_managed_product_photo(existing_path):
                _safe_unlink(existing_path)
            return _product_media_relative(resolved_new)

    source_candidate = Path(new_clean).expanduser()
    if not source_candidate.is_file():
        # Fall back to using the cleaned value directly if file is missing.
        return new_clean

    destination_root = _ensure_product_media_root()
    extension = source_candidate.suffix.lower()
    if not extension:
        mime_type, _ = mimetypes.guess_type(str(source_candidate))
        if mime_type:
            guessed = mimetypes.guess_extension(mime_type)
            if guessed:
                extension = guessed
    destination_name = f"{sku.lower()}_{uuid4().hex}{extension}"
    destination_path = destination_root / destination_name
    try:
        shutil.copy2(source_candidate, destination_path)
    except OSError:
        return new_clean

    if existing_path and existing_path.exists() and existing_path != destination_path and _is_managed_product_photo(existing_path):
        _safe_unlink(existing_path)

    return _product_media_relative(destination_path)


def resolve_product_photo(photo_path: str) -> Optional[Path]:
    resolved = _resolve_product_photo_path(photo_path.strip()) if photo_path else None
    return resolved if resolved and resolved.exists() else None


@dataclass
class _ProductSummaryAccumulator:
    sku: str = ""
    name: str = ""
    fallback: str = ""
    quantity: int = 0
    sales: float = 0.0
    cost: float = 0.0
    profit: float = 0.0


def _display_total(order: Order, *, include_tax: Optional[bool] = None) -> float:
    include = include_tax
    if include is None:
        include = bool(getattr(order, "tax_included_in_total", False))
    return order.total_amount + (order.tax_amount if include else 0.0)


def save_order(order: Order) -> int:
    order_id = order_repository.insert_order(order)
    for item in order.items:
        product_repository.adjust_inventory(item.product_sku, -item.quantity)
    saved_order = replace(order, id=order_id)
    _log_order_event(
        saved_order,
        "Created",
        f"Order created with {len(saved_order.items)} items.",
        _display_total(saved_order),
    )
    return order_id


def update_order(order_id: int, updated: Order) -> Order:
    existing = order_repository.fetch_order(order_id)
    if existing is None:
        raise ValueError("Order not found")

    normalized = replace(updated, id=order_id)

    previous_quantities = _summarize_item_quantities(existing.items)
    new_quantities = _summarize_item_quantities(normalized.items)

    for sku in sorted(set(previous_quantities) | set(new_quantities)):
        diff = new_quantities.get(sku, 0) - previous_quantities.get(sku, 0)
        if diff != 0:
            product_repository.adjust_inventory(sku, -diff)

    order_repository.update_order(order_id, normalized)

    amount_delta = _display_total(normalized) - _display_total(existing)
    if normalized.status != existing.status:
        description = (
            f"Order updated. Status changed from {existing.status} to {normalized.status}."
        )
    else:
        description = "Order updated."
    _log_order_event(normalized, "Updated", description, amount_delta)
    return normalized


def list_recent_orders(limit: int = 50) -> List[Order]:
    return order_repository.fetch_orders(limit)


def fetch_order(order_id: int) -> Optional[Order]:
    return order_repository.fetch_order(order_id)


def get_dashboard_snapshot() -> DashboardSnapshot:
    snapshot = order_repository.build_dashboard_snapshot()
    normalized_breakdown = _normalize_product_breakdown(snapshot.product_breakdown)
    return replace(snapshot, product_breakdown=normalized_breakdown)


def list_order_statuses() -> List[str]:
    return list(_ORDER_STATUSES)


def list_outstanding_orders() -> List[OutstandingOrder]:
    return order_repository.fetch_outstanding_orders()


def list_order_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[OrderReportRow]:
    return order_repository.fetch_order_report(start_date, end_date)


def list_order_destinations() -> List[OrderDestination]:
    rows = order_repository.fetch_order_destinations()
    aggregates: Dict[Tuple[str, str], OrderDestination] = {}

    for order_number, _customer_name, address in rows:
        if not address:
            continue
        parsed = _extract_city_state(address)
        if parsed is None:
            continue
        city, state = parsed
        key = (city, state)
        destination = aggregates.get(key)
        if destination is None:
            destination = OrderDestination(city=city, state=state, count=0)
            aggregates[key] = destination
        destination.count += 1
        destination.order_numbers.append(order_number)

    sorted_destinations = sorted(aggregates.values(), key=lambda item: item.count, reverse=True)
    return sorted_destinations


def build_order(
    order_number: str,
    customer_name: str,
    customer_address: str,
    status: str,
    carrier: str,
    tracking_number: str,
    order_date: date,
    ship_date: Optional[date],
    target_completion_date: Optional[date],
    items: List[OrderItem],
    *,
    is_paid: bool = False,
    notes: str = "",
) -> Order:
    if not items:
        raise ValueError("At least one line item is required")

    normalized_items: List[OrderItem] = []
    for item in items:
        cleaned = _normalize_item(item)
        product = product_repository.ensure_product(cleaned.product_sku, cleaned.product_name)
        cleaned = replace(
            cleaned,
            product_id=product.id,
            product_name=product.name,
            product_sku=product.sku,
        )
        if cleaned.base_unit_cost == 0 and product.base_unit_cost:
            cleaned = replace(cleaned, base_unit_cost=product.base_unit_cost)
        if not cleaned.cost_components and product.pricing_components:
            cleaned = replace(cleaned, cost_components=list(product.pricing_components))
        if (
            cleaned.unit_price == 0
            and product.default_unit_price
            and not getattr(cleaned, "is_freebie", False)
        ):
            cleaned = replace(cleaned, unit_price=product.default_unit_price)
        cleaned = _apply_pricing_metadata(cleaned, product)
        normalized_items.append(cleaned)

    app_settings = settings_repository.get_app_settings()
    tax_rate_percent = max(0.0, min(100.0, app_settings.tax_rate_percent))
    tax_rate = tax_rate_percent / 100.0
    subtotal = sum(item.line_total for item in normalized_items)
    tax_amount = round(subtotal * tax_rate, 2) if tax_rate > 0 else 0.0

    order_number_clean = order_number.strip()
    if not order_number_clean:
        order_number_clean = reserve_next_order_number()
    else:
        ensure_next_order_number_progress(order_number_clean)

    normalized_status = _normalize_status(status)
    normalized_ship_date = ship_date
    if normalized_status == "Shipped" and normalized_ship_date is None:
        normalized_ship_date = date.today()

    normalized_carrier = carrier.strip()
    normalized_tracking = tracking_number.strip()
    normalized_notes = notes.strip()
    normalized_target = target_completion_date
    if normalized_target is not None and normalized_target < order_date:
        raise ValueError("Target completion date cannot be before the order date")

    return Order(
        order_number=order_number_clean,
        customer_name=customer_name.strip(),
        customer_address=customer_address.strip(),
        status=normalized_status,
        is_paid=bool(is_paid),
        carrier=normalized_carrier,
        tracking_number=normalized_tracking,
        notes=normalized_notes,
        order_date=order_date,
        ship_date=normalized_ship_date,
        target_completion_date=normalized_target,
        items=normalized_items,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        tax_included_in_total=bool(app_settings.tax_add_to_total),
    )


def list_products() -> List[Product]:
    return product_repository.list_products()

def list_product_statuses() -> List[str]:
    return list(_PRODUCT_STATUSES)


def ensure_product_exists(sku: str, name: str) -> Product:
    product = product_repository.ensure_product(sku, name)
    if not product.status:
        product = product_repository.update_product(
            Product(
                id=product.id,
                sku=product.sku,
                name=product.name,
                description=product.description,
                photo_path=product.photo_path,
                inventory_count=product.inventory_count,
                is_complete=product.is_complete,
                status=_PRODUCT_STATUSES[0],
            )
        )
    return product


def update_product(product: Product) -> Product:
    normalized_status = _normalize_product_status(product.status)
    normalized_sku = product.sku.strip().upper()
    if not normalized_sku:
        raise ValueError("SKU cannot be empty.")

    normalized_name = product.name.strip() or normalized_sku
    normalized_description = product.description.strip()
    normalized_photo = product.photo_path.strip()
    normalized_inventory = max(0, int(product.inventory_count))
    existing_product = product_repository.get_product_by_id(product.id) if product.id else None
    existing_photo = existing_product.photo_path if existing_product else ""
    persisted_photo = _persist_product_photo(normalized_photo, normalized_sku, existing_photo)
    completion_state = bool(normalized_description) and bool(persisted_photo)

    normalized = replace(
        product,
        sku=normalized_sku,
        name=normalized_name,
        description=normalized_description,
        photo_path=persisted_photo,
        inventory_count=normalized_inventory,
        is_complete=completion_state,
        status=normalized_status,
        base_unit_cost=max(0.0, float(product.base_unit_cost)),
        default_unit_price=max(0.0, float(product.default_unit_price)),
        pricing_components=_normalize_cost_components(product.pricing_components),
    )
    return product_repository.update_product(normalized)


def delete_product(product_id: int) -> None:
    product_repository.delete_product(product_id)


def cancel_order(order_id: int) -> None:
    order = order_repository.fetch_order(order_id)
    if order is None:
        raise ValueError("Order not found")

    cancelled_name = _normalize_status("Cancelled")
    if order.status.strip().lower() == cancelled_name.lower():
        return

    _restock_order_items(order)
    order_repository.update_order_status(order_id, cancelled_name, ship_date=None)
    cancelled_order = replace(order, status=cancelled_name)
    _log_order_event(
        cancelled_order,
        "Cancelled",
        "Order cancelled and inventory restored.",
        -_display_total(cancelled_order),
    )


def delete_order(order_id: int) -> None:
    order = order_repository.fetch_order(order_id)
    if order is None:
        raise ValueError("Order not found")

    cancelled_name = _normalize_status("Cancelled")
    was_cancelled = order.status.strip().lower() == cancelled_name.lower()
    if not was_cancelled:
        _restock_order_items(order)

    amount_delta = 0.0 if was_cancelled else -_display_total(order)
    description = "Order deleted from system." + (" (Previously cancelled.)" if was_cancelled else "")

    _log_order_event(
        order,
        "Deleted",
        description,
        amount_delta,
    )
    order_repository.delete_order(order_id)


def get_app_settings() -> AppSettings:
    return settings_repository.get_app_settings()


def update_app_settings(settings: AppSettings) -> AppSettings:
    settings_repository.set_setting("business_name", settings.business_name.strip())
    settings_repository.set_setting("low_inventory_threshold", str(max(0, settings.low_inventory_threshold)))
    format_value = settings.order_number_format.strip() or _DEFAULT_ORDER_NUMBER_FORMAT
    settings_repository.set_setting("order_number_format", format_value)
    next_value = max(1, int(settings.order_number_next))
    settings_repository.set_setting("order_number_next", str(next_value))
    settings_repository.set_setting(
        "dashboard_show_business_name",
        "1" if settings.dashboard_show_business_name else "0",
    )
    settings_repository.set_setting("dashboard_logo_path", settings.dashboard_logo_path.strip())
    alignment = settings.dashboard_logo_alignment.strip().lower()
    if alignment not in _VALID_LOGO_POSITIONS:
        alignment = "top-left"
    settings_repository.set_setting("dashboard_logo_alignment", alignment)
    logo_size = max(24, min(1024, int(settings.dashboard_logo_size)))
    settings_repository.set_setting("dashboard_logo_size", str(logo_size))
    settings_repository.set_setting("dashboard_home_city", settings.dashboard_home_city.strip())
    settings_repository.set_setting("dashboard_home_state", settings.dashboard_home_state.strip().upper()[:2])
    settings_repository.set_setting("invoice_slogan", settings.invoice_slogan.strip())
    settings_repository.set_setting("invoice_street", settings.invoice_street.strip())
    settings_repository.set_setting("invoice_city", settings.invoice_city.strip())
    settings_repository.set_setting("invoice_state", settings.invoice_state.strip().upper()[:2])
    settings_repository.set_setting("invoice_zip", settings.invoice_zip.strip())
    settings_repository.set_setting("invoice_phone", settings.invoice_phone.strip())
    settings_repository.set_setting("invoice_fax", settings.invoice_fax.strip())
    settings_repository.set_setting("invoice_terms", settings.invoice_terms.strip() or "Due on receipt")
    settings_repository.set_setting("invoice_comments", settings.invoice_comments.strip())
    settings_repository.set_setting("invoice_contact_name", settings.invoice_contact_name.strip())
    settings_repository.set_setting("invoice_contact_phone", settings.invoice_contact_phone.strip())
    settings_repository.set_setting("invoice_contact_email", settings.invoice_contact_email.strip())

    payment_payload = []
    for option in settings.payment_options:
        label = option.label.strip()
        value = option.value.strip()
        if label and value:
            payment_payload.append({"label": label, "value": value})
    settings_repository.set_setting("payment_options", json.dumps(payment_payload, ensure_ascii=False))

    for legacy_key in ("payment_paypal", "payment_venmo", "payment_cash_app"):
        settings_repository.set_setting(legacy_key, "")

    settings_repository.set_setting("payment_other", settings.payment_other.strip())
    clamped_tax_rate = max(0.0, min(100.0, float(settings.tax_rate_percent)))
    settings_repository.set_setting("tax_rate_percent", f"{clamped_tax_rate:.4f}")
    settings_repository.set_setting(
        "tax_show_on_invoice",
        "1" if settings.tax_show_on_invoice else "0",
    )
    settings_repository.set_setting(
        "tax_add_to_total",
        "1" if settings.tax_add_to_total else "0",
    )
    return settings_repository.get_app_settings()


def get_low_inventory_threshold() -> int:
    return settings_repository.get_app_settings().low_inventory_threshold


def list_order_history(
    *,
    order_number: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 200,
) -> List[OrderHistoryEvent]:
    return order_repository.fetch_order_history(order_number, start_date, end_date, limit)


def list_inventory_forecast(window_days: int = 30, limit: int = 25) -> List[ProductForecast]:
    raw = order_repository.fetch_product_forecast(window_days, limit)
    threshold = get_low_inventory_threshold()
    results: List[ProductForecast] = []
    for row in raw:
        needs_reorder = row.inventory_count <= threshold
        if row.days_until_stockout is not None:
            needs_reorder = needs_reorder or row.days_until_stockout <= 21
        results.append(replace(row, needs_reorder=needs_reorder))
    return results


def list_notifications(today: Optional[date] = None) -> List[NotificationMessage]:
    today = today or date.today()
    notifications: List[NotificationMessage] = []

    for forecast in list_inventory_forecast(limit=50):
        if not forecast.needs_reorder:
            continue
        if forecast.days_until_stockout is None:
            detail = "" if forecast.inventory_count > 0 else " (no recent sales data)"
            message = (
                f"Inventory low for {forecast.sku} - {forecast.name}: "
                f"{forecast.inventory_count} on hand{detail}."
            )
        else:
            message = (
                f"Inventory low for {forecast.sku} - {forecast.name}: "
                f"{forecast.inventory_count} on hand, est. {forecast.days_until_stockout} days remaining."
            )
        notifications.append(NotificationMessage("Inventory", message, "warning"))

    for order in list_outstanding_orders():
        target = order.target_completion_date
        if target is None:
            continue
        days_remaining = (target - today).days
        if days_remaining < 0:
            notifications.append(
                NotificationMessage(
                    "Order",
                    f"Order {order.order_number} overdue by {-days_remaining} day(s).",
                    "critical",
                )
            )
        elif days_remaining == 0:
            notifications.append(
                NotificationMessage(
                    "Order",
                    f"Order {order.order_number} target completion is today.",
                    "warning",
                )
            )

    notifications.sort(key=lambda item: (item.severity != "critical", item.category, item.message))
    return notifications


def _normalize_product_breakdown(rows: Iterable[ProductSalesSummary]) -> List[ProductSalesSummary]:
    aggregates: Dict[str, _ProductSummaryAccumulator] = {}

    for row in rows:
        raw_label = row.product_name.strip()
        sku_candidate, name_candidate = _extract_sku_name(raw_label)
        normalized_sku = _replace_alias_sku(sku_candidate) if sku_candidate else ""
        key = normalized_sku.upper() if normalized_sku else raw_label.lower()

        entry = aggregates.get(key)
        cost_value = float(getattr(row, "total_cost", 0.0))
        profit_value = float(getattr(row, "total_profit", float(row.total_sales) - cost_value))
        if entry is None:
            entry = _ProductSummaryAccumulator(
                sku=normalized_sku,
                name=name_candidate,
                fallback=raw_label,
                quantity=int(row.total_quantity),
                sales=float(row.total_sales),
                cost=cost_value,
                profit=profit_value,
            )
            aggregates[key] = entry
        else:
            entry.quantity += int(row.total_quantity)
            entry.sales += float(row.total_sales)
            entry.cost += cost_value
            entry.profit += profit_value
            if not entry.sku and normalized_sku:
                entry.sku = normalized_sku
            if not entry.name and name_candidate:
                entry.name = name_candidate
            if not entry.fallback and raw_label:
                entry.fallback = raw_label

    results: List[ProductSalesSummary] = []
    for entry in aggregates.values():
        sku = entry.sku.strip()
        name = entry.name.strip()
        fallback = entry.fallback.strip()

        if sku and name:
            label = f"{sku} - {name}"
        elif sku:
            label = sku
        else:
            label = fallback or name

        results.append(
            ProductSalesSummary(
                product_name=label,
                total_quantity=entry.quantity,
                total_sales=entry.sales,
                total_cost=entry.cost,
                total_profit=entry.profit,
                margin=(entry.profit / entry.sales) if entry.sales else 0.0,
            )
        )

    results.sort(key=lambda item: (-item.total_sales, item.product_name))
    return results


def _extract_sku_name(label: str) -> Tuple[str, str]:
    if not label:
        return "", ""

    cleaned = label.strip()
    if " - " in cleaned:
        left, right = cleaned.split(" - ", 1)
        left = left.strip()
        right = right.strip()
        if _looks_like_sku(left):
            return left, right

    if _looks_like_sku(cleaned):
        return cleaned, ""

    return "", cleaned


def _replace_alias_sku(sku: str) -> str:
    candidate = sku.strip()
    if not candidate:
        return candidate
    mapped = _SKU_ALIASES.get(candidate.upper())
    if mapped:
        return mapped
    return candidate


def _looks_like_sku(value: str) -> bool:
    if not value:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{2,}", value.strip()))


def export_order_report(rows: Iterable[OrderReportRow], destination: str) -> Path:
    path = Path(destination).expanduser()
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    app_settings = settings_repository.get_app_settings()
    include_tax = bool(app_settings.tax_add_to_total)

    headers = [
        "Order Number",
        "Customer",
        "Order Date",
        "Ship Date",
        "Target Date",
        "Status",
        "Carrier",
        "Tracking Number",
        "Item Count",
        "Total Amount",
        "Freebie Cost",
        "Net Revenue",
        "Tax Amount",
        "Displayed Total",
        "Total Cost",
        "Profit",
        "Margin",
        "Products",
        "Adjustments",
        "Notes",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            order_date = row.order_date.strftime("%Y-%m-%d") if row.order_date else ""
            ship_date = row.ship_date.strftime("%Y-%m-%d") if row.ship_date else ""
            target_date = (
                row.target_completion_date.strftime("%Y-%m-%d")
                if row.target_completion_date
                else ""
            )
            tax_amount = getattr(row, "tax_amount", 0.0)
            display_total = row.total_amount + (tax_amount if include_tax else 0.0)
            writer.writerow(
                [
                    row.order_number,
                    row.customer_name,
                    order_date,
                    ship_date,
                    target_date,
                    row.status,
                    row.carrier,
                    row.tracking_number,
                    row.item_count,
                    f"{row.total_amount:.2f}",
                    f"{getattr(row, 'freebie_cost', 0.0):.2f}",
                    f"{getattr(row, 'net_revenue', row.total_amount - getattr(row, 'freebie_cost', 0.0)):.2f}",
                    f"{tax_amount:.2f}",
                    f"{display_total:.2f}",
                    f"{getattr(row, 'total_cost', 0.0):.2f}",
                    f"{getattr(row, 'profit', 0.0):.2f}",
                    f"{getattr(row, 'margin', 0.0) * 100:.1f}%",
                    row.products,
                    row.adjustment_summary,
                    row.notes,
                ]
            )

    return path


def export_order_invoice(order_id: int, destination: str) -> Path:
    order = order_repository.fetch_order(int(order_id))
    if order is None:
        raise ValueError("Order not found.")

    settings = settings_repository.get_app_settings()
    path = Path(destination).expanduser()
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    html_content = _render_invoice_html(order, settings)
    _write_pdf_from_html(html_content, path)
    return path


def _render_invoice_html(order: Order, settings: AppSettings) -> str:
    business_name = (settings.business_name or "").strip() or "Company Name"
    slogan = (settings.invoice_slogan or "Your Company Slogan").strip() or "Your Company Slogan"
    street = (settings.invoice_street or "Street Address").strip() or "Street Address"
    city = (settings.invoice_city or "").strip()
    state = (settings.invoice_state or "").strip()
    zip_code = (settings.invoice_zip or "").strip()
    phone = (settings.invoice_phone or "").strip()
    fax = (settings.invoice_fax or "").strip()

    city_state = ""
    if city and state:
        city_state = f"{city}, {state}"
    elif city:
        city_state = city
    elif state:
        city_state = state
    if zip_code:
        city_state = f"{city_state} {zip_code}".strip()
    if not city_state:
        city_state = "City, ST ZIP Code"

    contact_line = ""
    phone_parts: List[str] = []
    if phone:
        phone_parts.append(f"Phone: {phone}")
    if fax:
        phone_parts.append(f"Fax: {fax}")
    if phone_parts:
        contact_line = " ".join(phone_parts)

    company_lines: List[str] = []
    if slogan:
        company_lines.append(slogan)
    if street:
        company_lines.append(street)
    company_lines.append(city_state)
    if contact_line:
        company_lines.append(contact_line)
    safe_company = html.escape(business_name)

    def _format_address_block(name: str, address: str) -> str:
        lines: List[str] = []
        if name and name.strip():
            lines.append(html.escape(name.strip()))
        for raw in (address or "").splitlines():
            stripped = raw.strip()
            if stripped:
                lines.append(html.escape(stripped))
        if not lines:
            lines.append("Recipient Name")
            lines.append("Company Name")
            lines.append("Street Address")
            lines.append("City, ST ZIP Code")
            lines.append("Phone: Phone")
        return "<br>".join(lines)

    customer_block = _format_address_block(order.customer_name, order.customer_address)
    ship_block = customer_block

    invoice_date = order.order_date.strftime("%B %d, %Y") if order.order_date else "DATE"
    document_title = "Receipt" if order.is_paid else "Invoice"

    terms_value = (settings.invoice_terms or "Due on receipt").strip() or "Due on receipt"

    comments_text = (settings.invoice_comments or "").strip()
    comments_html = html.escape(comments_text).replace("\n", "<br>") if comments_text else ""

    invoice_logo_size = min(80, max(48, int(settings.dashboard_logo_size or 0) or 72))
    logo_markup = ""
    logo_payload = _load_logo_data(settings.dashboard_logo_path)
    if logo_payload is not None:
        mime_type, encoded = logo_payload
        logo_markup = (
            f"<div class=\"logo-wrap\"><img src=\"data:{mime_type};base64,{encoded}\" "
            f"alt=\"{html.escape(business_name)} logo\" class=\"logo\" width=\"{invoice_logo_size}\" height=\"{invoice_logo_size}\"/></div>"
        )

    line_rows: List[str] = []
    for item in order.items:
        name = (item.product_name or "").strip()
        sku = (item.product_sku or "").strip()
        if name and sku:
            base_label = f"{name} ({sku})"
        else:
            base_label = name or sku or "Item"
        description_parts = [base_label]
        if item.product_description and item.product_description.strip():
            description_parts.append(item.product_description.strip())
        description = " – ".join(description_parts)
        adjustments: List[str] = []
        if float(getattr(item, "applied_discount", 0.0) or 0.0) > 0.005:
            adjustments.append(
                f"Discount: -{html.escape(_format_currency(float(item.applied_discount)))}"
            )
        if float(getattr(item, "applied_tax", 0.0) or 0.0) > 0.005:
            adjustments.append(
                f"Tax/Surcharge: +{html.escape(_format_currency(float(item.applied_tax)))}"
            )
        note_text = (item.price_adjustment_note or "").strip()
        if note_text:
            adjustments.append(html.escape(note_text))
        adjustment_html = ""
        if adjustments:
            adjustment_html = (
                """
            <tr class="item-adjustment">
                <td></td>
                <td colspan="3" class="adjustment-details">{details}</td>
            </tr>
            """.format(details="; ".join(adjustments))
            )
        line_rows.append(
            """
            <tr>
                <td class="qty">{quantity}</td>
                <td>{description}</td>
                <td class="currency">{unit_price}</td>
                <td class="currency">{line_total}</td>
            </tr>
            {adjustments}
            """.format(
                quantity=int(item.quantity),
                description=html.escape(description),
                unit_price=_format_currency(item.unit_price),
                line_total=_format_currency(item.line_total),
                adjustments=adjustment_html,
            )
        )

    if not line_rows:
        line_rows.append(
            """
            <tr>
                <td class="qty">--</td>
                <td class="empty" colspan="3">No items available.</td>
            </tr>
            """
        )

    subtotal = order.total_amount
    stored_tax_amount = float(getattr(order, "tax_amount", 0.0) or 0.0)
    stored_tax_rate = float(getattr(order, "tax_rate", 0.0) or 0.0)
    fallback_rate = max(0.0, float(settings.tax_rate_percent or 0.0)) / 100.0
    tax_rate_fraction = stored_tax_rate if stored_tax_rate > 0 else fallback_rate
    tax_amount = stored_tax_amount
    if tax_amount <= 0 and tax_rate_fraction > 0:
        tax_amount = round(subtotal * tax_rate_fraction, 2)
    include_tax_in_total = bool(settings.tax_add_to_total)
    show_tax_line = bool(settings.tax_show_on_invoice and tax_amount > 0)
    shipping_amount = 0.0
    total_due = subtotal + (tax_amount if include_tax_in_total else 0.0) + shipping_amount

    totals_rows = [
        """
        <tr class=\"totals-row\">
            <td colspan=\"3\" class=\"totals-label\">Subtotal</td>
            <td class=\"currency\">{subtotal}</td>
        </tr>
        """.format(subtotal=_format_currency(subtotal))
    ]

    if show_tax_line:
        if tax_rate_fraction > 0:
            tax_label = f"Sales Tax ({tax_rate_fraction * 100:.2f}%)"
        else:
            tax_label = "Sales Tax"
        totals_rows.append(
            """
            <tr class=\"totals-row\">
                <td colspan=\"3\" class=\"totals-label\">{label}</td>
                <td class=\"currency\">{amount}</td>
            </tr>
            """.format(label=tax_label, amount=_format_currency(tax_amount))
        )

    totals_rows.append(
        """
        <tr class=\"totals-row\">
            <td colspan=\"3\" class=\"totals-label\">Shipping &amp; Handling</td>
            <td class=\"currency\">{shipping}</td>
        </tr>
        """.format(shipping=_format_currency(shipping_amount))
    )

    total_label = "Total Due"
    if show_tax_line and not include_tax_in_total:
        total_label = "Total Due (excludes tax)"
    elif include_tax_in_total and tax_amount > 0 and not show_tax_line:
        total_label = "Total Due (includes tax)"

    totals_rows.append(
        """
        <tr class=\"totals-row total-due\">
            <td colspan=\"3\" class=\"totals-label\">{label}</td>
            <td class=\"currency\">{total}</td>
        </tr>
        """.format(label=total_label, total=_format_currency(total_due))
    )

    totals_html = "".join(totals_rows)

    terms_display = html.escape(terms_value)

    def _format_payment_value(value: str) -> str:
        trimmed = (value or "").strip()
        if not trimmed:
            return ""
        if re.match(r"^https?://", trimmed, re.IGNORECASE):
            safe_value = html.escape(trimmed)
            return f"<a href=\"{safe_value}\">{safe_value}</a>"
        return html.escape(trimmed)

    payment_items: List[str] = []
    for option in settings.payment_options:
        label_text = (option.label or "").strip()
        if not label_text:
            continue
        formatted_value = _format_payment_value(option.value)
        if formatted_value:
            payment_items.append(
                f"<li><span class=\"payment-label\">{html.escape(label_text)}</span> {formatted_value}</li>"
            )

    payment_options_html = ""
    if payment_items:
        payment_options_html = (
            "<div class=\"payment-options\">"
            "<h4>Payment Options</h4>"
            "<ul class=\"payment-list\">"
            + "".join(payment_items)
            + "</ul>"
            "</div>"
        )

    other_note = (settings.payment_other or "").strip()
    payment_notes_html = ""
    if other_note:
        payment_notes_html = (
            "<p class=\"payment-note\">"
            + html.escape(other_note).replace("\n", "<br>")
            + "</p>"
        )

    if payment_options_html or payment_notes_html:
        payment_instructions_html = payment_options_html + payment_notes_html
    else:
        payment_instructions_html = f"<p>Make all checks payable to {safe_company}.</p>"

    contact_name = (settings.invoice_contact_name or business_name).strip() or business_name
    contact_phone = (settings.invoice_contact_phone or "").strip()
    contact_email = (settings.invoice_contact_email or "").strip()

    contact_segments: List[str] = []
    if contact_name:
        contact_segments.append(html.escape(contact_name))
    if contact_phone:
        contact_segments.append(html.escape(contact_phone))
    if contact_email:
        if "@" in contact_email and not re.match(r"^[a-z]+://", contact_email, re.IGNORECASE):
            safe_email = html.escape(contact_email)
            contact_segments.append(f"<a href=\"mailto:{safe_email}\">{safe_email}</a>")
        else:
            contact_segments.append(html.escape(contact_email))
    if not contact_segments:
        contact_segments.append(f"{safe_company}, Phone, Email")

    contact_message = ", ".join(contact_segments)
    payment_instructions_html += (
        f"<p class=\"payment-contact\">If you have any questions concerning this invoice, contact {contact_message}.</p>"
    )
    payment_instructions_html += f"<p class=\"terms-note\">Payment Terms: {terms_display}</p>"

    company_paragraphs = "".join(f"<p>{html.escape(line)}</p>" for line in company_lines)

    styles = f"""
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 36px; background-color: #ffffff; color: #1f2933; font-size: 11pt; line-height: 1.1; }}
        p {{ margin: 0; }}
        .invoice {{ max-width: 820px; margin: 0 auto; background: #ffffff; padding: 30px 32px; border-radius: 12px; box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08); border: 1px solid #e5e9f0; }}
        .invoice-header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; margin-bottom: 18px; }}
        .company-block {{ display: flex; gap: 12px; align-items: flex-start; }}
        .company-info h1 {{ margin: 0 0 6px 0; font-size: 21pt; letter-spacing: 0.03em; color: #111827; }}
        .company-info p {{ margin: 0; color: #4b5563; font-size: 10pt; }}
        .logo-wrap {{ flex-shrink: 0; border-radius: 10px; border: 1px solid #dfe4ea; padding: 6px; background: #ffffff; }}
        .logo {{ width: {invoice_logo_size}px; height: {invoice_logo_size}px; object-fit: contain; display: block; }}
        .invoice-title {{ font-size: 30pt; font-weight: 700; color: #0f172a; letter-spacing: 0.12em; text-align: right; margin: 0 0 6px 0; }}
        .invoice-meta {{ text-align: right; font-size: 10.5pt; color: #334155; background: #ffffff; border: 1px solid #e5e9f0; border-radius: 10px; padding: 10px 14px; display: inline-block; }}
        .invoice-meta table {{ margin-left: auto; border-collapse: collapse; }}
        .invoice-meta th {{ text-align: left; padding: 2px 10px 2px 0; font-weight: 600; color: #0f172a; }}
        .invoice-meta td {{ padding: 2px 0; }}
        .address-section {{ display: flex; gap: 24px; margin-bottom: 18px; }}
        .address-card {{ flex: 1; background-color: #ffffff; padding: 14px 16px; border-radius: 12px; border: 1px solid #e5e9f0; box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05); }}
        .address-card h3 {{ margin: 0 0 6px 0; text-transform: uppercase; letter-spacing: 0.12em; font-size: 9pt; color: #6b7280; }}
        .address-card p {{ margin: 0; color: #111827; font-size: 10.5pt; line-height: 1.1; }}
        .comments {{ margin-bottom: 18px; background: #ffffff; border: 1px solid #f0f2f6; border-radius: 12px; padding: 14px 16px; box-shadow: 0 6px 16px rgba(15, 23, 42, 0.04); }}
        .comments h3 {{ margin: 0 0 6px 0; font-size: 10pt; letter-spacing: 0.12em; text-transform: uppercase; color: #6b7280; }}
        .comments p {{ margin: 0; background: #ffffff; padding: 0; color: #1f2933; font-size: 10.5pt; border-radius: 6px; line-height: 1.1; }}
        table.items-table {{ width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 10.5pt; border: 1px solid #e5e9f0; border-radius: 12px; overflow: hidden; }}
        table.items-table thead th {{ text-align: left; font-weight: 600; font-size: 10pt; text-transform: uppercase; letter-spacing: 0.12em; padding: 8px 8px; background-color: #f8fafc; border-bottom: 1px solid #e5e9f0; color: #0f172a; }}
        table.items-table tbody td {{ padding: 6px 8px; border-bottom: 1px solid #e5e9f0; vertical-align: top; background: #ffffff; }}
        table.items-table tbody tr:last-child td {{ border-bottom: none; }}
        .qty {{ text-align: center; width: 70px; }}
        .currency {{ text-align: right; width: 120px; }}
        .empty {{ text-align: center; color: #94a3b8; padding: 14px 8px; font-style: italic; background: #ffffff; }}
        .item-adjustment td {{ background: #f8fafc; border-bottom: 1px solid #e5e9f0; font-size: 9.5pt; color: #475569; }}
        .adjustment-details {{ padding: 2px 8px 8px 8px; font-style: italic; }}
        .summary-row {{ display: flex; justify-content: flex-start; align-items: flex-start; gap: 20px; margin-top: 12px; }}
        .payment-instructions {{ margin-top: 0; font-size: 10.5pt; color: #111827; max-width: 340px; background: #ffffff; border: 1px solid #e5e9f0; border-radius: 12px; padding: 12px; box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05); }}
        .payment-instructions p {{ margin: 0; line-height: 1.1; }}
        .payment-options {{ margin-bottom: 6px; }}
        .payment-options h4 {{ margin: 0 0 4px 0; font-size: 10pt; letter-spacing: 0.12em; text-transform: uppercase; color: #6b7280; }}
        .payment-list {{ margin: 0 0 6px 16px; padding: 0; line-height: 1.1; }}
        .payment-list li {{ margin: 2px 0; list-style: disc; color: #111827; }}
        .payment-label {{ font-weight: 600; color: #0f172a; margin-right: 6px; }}
        .payment-note {{ margin: 4px 0 0 0; color: #111827; line-height: 1.1; }}
        .payment-contact {{ margin: 6px 0 0 0; color: #111827; line-height: 1.1; }}
        .terms-note {{ margin: 4px 0 0 0; color: #1f2933; font-style: italic; line-height: 1.1; }}
        table.items-table tfoot td {{ padding: 6px 8px; border-top: 1px solid #e5e9f0; background: #f8fafc; color: #0f172a; }}
        table.items-table tfoot .totals-label {{ text-align: right; font-weight: 600; }}
        table.items-table tfoot tr.total-due td {{ background: #0f172a; color: #ffffff; font-size: 11.5pt; font-weight: 700; border-top: none; }}
        table.items-table tfoot tr.total-due .totals-label {{ color: #ffffff; }}
        .footer {{ margin-top: 18px; font-size: 10pt; text-align: center; color: #6b7280; letter-spacing: 0.04em; text-transform: uppercase; }}
    """

    invoice_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8" />
            <title>{document_title} - {order_number}</title>
            <style>{styles}</style>
        </head>
        <body>
            <div class="invoice">
                <div class="invoice-header">
                    <div class="company-block">
                        {logo}
                        <div class="company-info">
                            <h1>{company}</h1>
                            {company_details}
                        </div>
                    </div>
                    <div class="invoice-meta">
                        <div class="invoice-title">{document_title}</div>
                        <table>
                            <tr><th>{document_title} #</th><td>{invoice_number}</td></tr>
                            <tr><th>Date</th><td>{invoice_date}</td></tr>
                        </table>
                    </div>
                </div>
                <div class="address-section">
                    <div class="address-card">
                        <h3>To</h3>
                        <p>{customer_block}</p>
                    </div>
                    <div class="address-card">
                        <h3>Ship To</h3>
                        <p>{ship_block}</p>
                    </div>
                </div>
                <div class="comments">
                    <h3>Comments or Special Instructions</h3>
                    <p>{comments}</p>
                </div>
                <table class="items-table">
                    <thead>
                        <tr>
                            <th class="qty">Quantity</th>
                            <th>Description</th>
                            <th class="currency">Unit Price</th>
                            <th class="currency">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                    <tfoot>
                        {totals}
                    </tfoot>
                </table>
                <div class="summary-row">
                    <div class="payment-instructions">
                        {payment_instructions}
                    </div>
                </div>
                <p class="footer">Thank you for your business!</p>
            </div>
        </body>
        </html>
    """.format(
        order_number=html.escape(order.order_number),
        styles=styles,
        logo=logo_markup,
        company=safe_company,
        document_title=document_title,
        company_details=company_paragraphs,
        invoice_number=html.escape(order.order_number),
        invoice_date=html.escape(invoice_date),
        customer_block=customer_block,
        ship_block=ship_block,
        comments=comments_html,
        rows="".join(line_rows),
        totals=totals_html,
        payment_instructions=payment_instructions_html,
    )

    return invoice_html


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _write_pdf_from_html(html_content: str, path: Path) -> None:
    pdf_writer = QPdfWriter(str(path))
    pdf_writer.setPageSize(QPageSize(QPageSize.Letter))  # type: ignore[attr-defined]
    pdf_writer.setResolution(144)

    document = QTextDocument()
    document.setDocumentMargin(36)
    document.setDefaultFont(QFont("Segoe UI", 11))
    document.setHtml(html_content)

    page_width = pdf_writer.width()
    page_height = pdf_writer.height()
    document.setPageSize(QSizeF(page_width, page_height))

    document.print_(pdf_writer)


def _load_logo_data(path_str: str) -> Optional[Tuple[str, str]]:
    candidate = (path_str or "").strip()
    if not candidate:
        return None

    path = Path(candidate).expanduser()
    if not path.is_file():
        return None

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        mime_type = "image/png"

    try:
        data = path.read_bytes()
    except OSError:
        return None

    encoded = base64.b64encode(data).decode("ascii")
    return mime_type, encoded


def _normalize_item(item: OrderItem) -> OrderItem:
    sku = item.product_sku.strip().upper()
    return replace(
        item,
        product_name=item.product_name.strip(),
        product_description=item.product_description.strip(),
        product_sku=sku,
        base_unit_cost=max(0.0, float(item.base_unit_cost)),
        cost_components=_normalize_cost_components(item.cost_components),
        unit_price=max(0.0, float(item.unit_price)),
        is_freebie=bool(getattr(item, "is_freebie", False)),
        applied_discount=max(0.0, float(getattr(item, "applied_discount", 0.0) or 0.0)),
        applied_tax=max(0.0, float(getattr(item, "applied_tax", 0.0) or 0.0)),
        price_adjustment_note=str(getattr(item, "price_adjustment_note", "") or "").strip(),
    )


def _apply_pricing_metadata(item: OrderItem, product: Product) -> OrderItem:
    quantity = max(0, int(getattr(item, "quantity", 0)))
    if quantity <= 0:
        return replace(item, applied_discount=0.0, applied_tax=0.0)

    default_price = float(getattr(product, "default_unit_price", 0.0) or 0.0)
    actual_price = float(getattr(item, "unit_price", 0.0) or 0.0)
    line_default = default_price * quantity
    line_actual = actual_price * quantity

    discount = 0.0
    tax = 0.0
    note_parts: List[str] = []

    if bool(getattr(item, "is_freebie", False)):
        if line_default > 0:
            discount = line_default
            note_parts.append("Freebie – default price waived")
        else:
            note_parts.append("Freebie item")
    else:
        if line_default > 0:
            delta = line_actual - line_default
            if delta < -0.005:
                discount = abs(delta)
                note_parts.append("Discount applied to default price")
            elif delta > 0.005:
                tax = delta
                note_parts.append("Includes surcharge above default price")
        else:
            if line_actual > 0:
                note_parts.append("Custom unit price (no default price)")
            else:
                note_parts.append("Price overridden to zero")

    existing_note = (item.price_adjustment_note or "").strip()
    if existing_note:
        note_parts.append(existing_note)

    unique_notes: List[str] = []
    for part in note_parts:
        trimmed = part.strip()
        if not trimmed:
            continue
        if trimmed not in unique_notes:
            unique_notes.append(trimmed)

    return replace(
        item,
        applied_discount=round(max(0.0, discount), 2),
        applied_tax=round(max(0.0, tax), 2),
        price_adjustment_note="; ".join(unique_notes),
    )


def _normalize_status(status: str) -> str:
    candidate = status.strip()
    if not candidate:
        return _ORDER_STATUSES[0]

    candidate_lower = candidate.lower()
    for option in _ORDER_STATUSES:
        if candidate_lower == option.lower():
            return option

    return candidate.title()


def _normalize_product_status(status: str) -> str:
    candidate = status.strip()
    if not candidate:
        return _PRODUCT_STATUSES[0]

    candidate_lower = candidate.lower()
    for option in _PRODUCT_STATUSES:
        if candidate_lower == option.lower():
            return option

    return candidate.title()


def preview_next_order_number() -> str:
    fmt, next_value = _get_order_number_configuration()
    return _format_order_number(fmt, next_value)


def reserve_next_order_number() -> str:
    fmt, next_value = _get_order_number_configuration()
    order_number = _format_order_number(fmt, next_value)
    _set_next_order_number(next_value + 1)
    return order_number


def ensure_next_order_number_progress(order_number: str) -> None:
    if not order_number:
        return
    sequence_value = _extract_sequence_value(order_number)
    if sequence_value is None:
        return
    _, current_next = _get_order_number_configuration()
    if sequence_value >= current_next:
        _set_next_order_number(sequence_value + 1)


def _get_order_number_configuration() -> Tuple[str, int]:
    fmt = settings_repository.get_setting("order_number_format") or _DEFAULT_ORDER_NUMBER_FORMAT
    fmt = fmt.strip() or _DEFAULT_ORDER_NUMBER_FORMAT
    try:
        next_value = int(settings_repository.get_setting("order_number_next") or "1")
    except ValueError:
        next_value = 1
    return fmt, max(1, next_value)


def _set_next_order_number(value: int) -> None:
    settings_repository.set_setting("order_number_next", str(max(1, value)))


def _normalize_cost_components(components: Iterable[CostComponent] | None) -> List[CostComponent]:
    normalized: List[CostComponent] = []
    if not components:
        return normalized

    for component in components:
        if isinstance(component, CostComponent):
            label = component.label
            amount = component.amount
        elif isinstance(component, dict):
            label = str(component.get("label", ""))
            amount = component.get("amount", 0)
        else:
            label = str(getattr(component, "label", ""))
            amount = getattr(component, "amount", 0)

        label = label.strip()
        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            amount_value = 0.0

        if not label and amount_value == 0.0:
            continue

        normalized.append(CostComponent(label=label, amount=max(0.0, amount_value)))

    return normalized


def _format_order_number(fmt: str, sequence: int) -> str:
    try:
        formatted = fmt.format(seq=sequence)
    except Exception:
        formatted = f"{sequence:06d}"
    formatted = formatted.strip()
    return formatted or f"{sequence:06d}"


def _extract_sequence_value(order_number: str) -> Optional[int]:
    match = _SEQUENCE_PATTERN.search(order_number)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _restock_order_items(order: Order) -> None:
    for item in order.items:
        sku = item.product_sku.strip()
        if not sku:
            continue
        product_repository.adjust_inventory(sku, item.quantity)


def _log_order_event(order: Order, event_type: str, description: str, amount_delta: float) -> None:
    order_repository.log_order_event(
        order.id,
        order.order_number,
        event_type,
        description,
        amount_delta,
    )


def _summarize_item_quantities(items: Iterable[OrderItem]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for item in items:
        sku = item.product_sku.strip().upper()
        if not sku:
            continue
        totals[sku] = totals.get(sku, 0) + int(item.quantity)
    return totals


def _extract_city_state(address: str) -> Optional[Tuple[str, str]]:
    normalized = address.replace("\r", "\n")
    segments = [segment.strip() for segment in normalized.split("\n") if segment.strip()]
    for segment in reversed(segments):
        match = _CITY_STATE_PATTERN.search(segment)
        if match:
            city = match.group("city").strip()
            state = match.group("state").strip().upper()
            if city and state:
                return city, state

    condensed = " ".join(segments)
    match = _CITY_STATE_PATTERN.search(condensed)
    if match:
        city = match.group("city").strip()
        state = match.group("state").strip().upper()
        if city and state:
            return city, state

    return None
