from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional

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
    Product,
    ProductForecast,
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


def list_recent_orders(limit: int = 50) -> List[Order]:
    return order_repository.fetch_orders(limit)


def get_dashboard_snapshot() -> DashboardSnapshot:
    return order_repository.build_dashboard_snapshot()


def list_order_statuses() -> List[str]:
    return list(_ORDER_STATUSES)


def list_outstanding_orders() -> List[OutstandingOrder]:
    return order_repository.fetch_outstanding_orders()


def list_order_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[OrderReportRow]:
    return order_repository.fetch_order_report(start_date, end_date)


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

    order_number = order_number.strip().upper()
    if not order_number:
        order_number = _generate_order_number_from_items(normalized_items)

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
        order_number=order_number,
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
    normalized = replace(product, status=normalized_status)
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


def _generate_order_number_from_items(items: List[OrderItem]) -> str:
    sku = next((item.product_sku for item in items if item.product_sku), "")
    if sku:
        return order_repository.generate_order_number_for_sku(sku)
    fallback = items[0].product_name if items else "ORD"
    return order_repository.generate_order_number_from_prefix(fallback)


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
