from __future__ import annotations

import csv
import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ..data import order_repository, product_repository, settings_repository
from ..models.order_models import (
    AppSettings,
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


@dataclass
class _ProductSummaryAccumulator:
    sku: str = ""
    name: str = ""
    fallback: str = ""
    quantity: int = 0
    sales: float = 0.0


def save_order(order: Order) -> int:
    order_id = order_repository.insert_order(order)
    for item in order.items:
        product_repository.adjust_inventory(item.product_sku, -item.quantity)
    saved_order = replace(order, id=order_id)
    _log_order_event(
        saved_order,
        "Created",
        f"Order created with {len(saved_order.items)} items.",
        saved_order.total_amount,
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

    amount_delta = normalized.total_amount - existing.total_amount
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
        normalized_items.append(cleaned)

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
    normalized_target = target_completion_date
    if normalized_target is not None and normalized_target < order_date:
        raise ValueError("Target completion date cannot be before the order date")

    return Order(
        order_number=order_number_clean,
        customer_name=customer_name.strip(),
        customer_address=customer_address.strip(),
        status=normalized_status,
        carrier=normalized_carrier,
        tracking_number=normalized_tracking,
        order_date=order_date,
        ship_date=normalized_ship_date,
        target_completion_date=normalized_target,
        items=normalized_items,
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

    normalized = replace(
        product,
        sku=normalized_sku,
        name=normalized_name,
        description=normalized_description,
        photo_path=normalized_photo,
        inventory_count=normalized_inventory,
        status=normalized_status,
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
        -cancelled_order.total_amount,
    )


def delete_order(order_id: int) -> None:
    order = order_repository.fetch_order(order_id)
    if order is None:
        raise ValueError("Order not found")

    cancelled_name = _normalize_status("Cancelled")
    was_cancelled = order.status.strip().lower() == cancelled_name.lower()
    if not was_cancelled:
        _restock_order_items(order)

    amount_delta = 0.0 if was_cancelled else -order.total_amount
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
        if entry is None:
            entry = _ProductSummaryAccumulator(
                sku=normalized_sku,
                name=name_candidate,
                fallback=raw_label,
                quantity=int(row.total_quantity),
                sales=float(row.total_sales),
            )
            aggregates[key] = entry
        else:
            entry.quantity += int(row.total_quantity)
            entry.sales += float(row.total_sales)
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
        "Products",
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
                    row.products,
                ]
            )

    return path


def _normalize_item(item: OrderItem) -> OrderItem:
    sku = item.product_sku.strip().upper()
    return replace(
        item,
        product_name=item.product_name.strip(),
        product_description=item.product_description.strip(),
        product_sku=sku,
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
