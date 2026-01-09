from __future__ import annotations

import json
import re
import sqlite3
import math
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional

from ..models.order_models import (
    CompletedOrder,
    CostComponent,
    CustomerSalesSummary,
    DashboardSnapshot,
    Order,
    OrderHistoryEvent,
    OrderItem,
    OrderReportRow,
    OutstandingOrder,
    ProductForecast,
    ProductSalesSummary,
)
from .database import create_connection


_DATE_FORMAT = "%Y-%m-%d"


def insert_order(order: Order) -> int:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO orders (
                    order_number,
                    customer_name,
                    customer_address,
                    order_date,
                    ship_date,
                    status,
                    is_paid,
                    carrier,
                    tracking_number,
                    notes,
                    total_amount,
                    tax_rate,
                    tax_amount,
                    tax_included_in_total,
                    target_completion_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.order_number.strip(),
                    order.customer_name.strip(),
                    order.customer_address.strip(),
                    order.order_date.strftime(_DATE_FORMAT),
                    order.ship_date.strftime(_DATE_FORMAT) if order.ship_date else None,
                    order.status.strip(),
                    int(bool(order.is_paid)),
                    order.carrier.strip(),
                    order.tracking_number.strip(),
                    order.notes.strip(),
                    order.total_amount,
                    float(order.tax_rate),
                    float(order.tax_amount),
                    int(bool(order.tax_included_in_total)),
                    order.target_completion_date.strftime(_DATE_FORMAT)
                    if order.target_completion_date
                    else None,
                ),
            )
            order_id = cursor.lastrowid

            cursor.executemany(
                """
                INSERT INTO order_items (
                    order_id,
                    product_id,
                    product_sku,
                    product_name,
                    product_description,
                    quantity,
                    unit_price,
                    base_unit_cost,
                    cost_components,
                    is_freebie,
                    applied_discount,
                    applied_tax,
                    price_adjustment_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        order_id,
                        item.product_id,
                        item.product_sku.strip().upper(),
                        item.product_name.strip(),
                        item.product_description.strip(),
                        item.quantity,
                        item.unit_price,
                        float(item.base_unit_cost),
                        _serialize_components(item.cost_components),
                        int(bool(getattr(item, "is_freebie", False))),
                        float(getattr(item, "applied_discount", 0.0) or 0.0),
                        float(getattr(item, "applied_tax", 0.0) or 0.0),
                        str(getattr(item, "price_adjustment_note", "") or ""),
                    )
                    for item in order.items
                ],
            )

            connection.commit()
            return int(order_id)
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise exc
        finally:
            cursor.close()


def update_order(order_id: int, order: Order) -> None:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE orders
                SET
                    order_number = ?,
                    customer_name = ?,
                    customer_address = ?,
                    order_date = ?,
                    ship_date = ?,
                    status = ?,
                    is_paid = ?,
                    carrier = ?,
                    tracking_number = ?,
                    notes = ?,
                    total_amount = ?,
                    tax_rate = ?,
                    tax_amount = ?,
                    tax_included_in_total = ?,
                    target_completion_date = ?
                WHERE id = ?
                """,
                (
                    order.order_number.strip(),
                    order.customer_name.strip(),
                    order.customer_address.strip(),
                    order.order_date.strftime(_DATE_FORMAT),
                    order.ship_date.strftime(_DATE_FORMAT) if order.ship_date else None,
                    order.status.strip(),
                    int(bool(order.is_paid)),
                    order.carrier.strip(),
                    order.tracking_number.strip(),
                    order.notes.strip(),
                    order.total_amount,
                    float(order.tax_rate),
                    float(order.tax_amount),
                    int(bool(order.tax_included_in_total)),
                    order.target_completion_date.strftime(_DATE_FORMAT)
                    if order.target_completion_date
                    else None,
                    int(order_id),
                ),
            )

            cursor.execute("DELETE FROM order_items WHERE order_id = ?", (int(order_id),))

            cursor.executemany(
                """
                INSERT INTO order_items (
                    order_id,
                    product_id,
                    product_sku,
                    product_name,
                    product_description,
                    quantity,
                    unit_price,
                    base_unit_cost,
                    cost_components,
                    is_freebie,
                    applied_discount,
                    applied_tax,
                    price_adjustment_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        int(order_id),
                        item.product_id,
                        item.product_sku.strip().upper(),
                        item.product_name.strip(),
                        item.product_description.strip(),
                        int(item.quantity),
                        float(item.unit_price),
                        float(item.base_unit_cost),
                        _serialize_components(item.cost_components),
                        int(bool(getattr(item, "is_freebie", False))),
                        float(getattr(item, "applied_discount", 0.0) or 0.0),
                        float(getattr(item, "applied_tax", 0.0) or 0.0),
                        str(getattr(item, "price_adjustment_note", "") or ""),
                    )
                    for item in order.items
                ],
            )

            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise exc
        finally:
            cursor.close()


def generate_order_number_for_sku(sku: str, *, padding: int = 4) -> str:
    prefix = _extract_alpha_prefix(sku)
    return generate_order_number_from_prefix(prefix, padding=padding)


def generate_order_number_from_prefix(prefix: str, *, padding: int = 4) -> str:
    normalized_prefix = _extract_alpha_prefix(prefix)
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT order_number
            FROM orders
            WHERE order_number LIKE ? || '%'
              AND SUBSTR(order_number, 1, LENGTH(?)) = ?
            ORDER BY LENGTH(order_number) DESC, order_number DESC
            LIMIT 1
            """,
            (normalized_prefix, normalized_prefix, normalized_prefix),
        ).fetchone()

    last_number = 0
    if row is not None:
        last_number = _parse_sequence(row["order_number"], normalized_prefix)

    next_number = last_number + 1
    return f"{normalized_prefix}{next_number:0{padding}d}"


def fetch_orders(limit: int = 50) -> List[Order]:
    with create_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                o.id,
                o.order_number,
                o.customer_name,
                o.customer_address,
                o.order_date,
                o.ship_date,
                o.status,
                o.is_paid,
                o.carrier,
                o.tracking_number,
                o.notes,
                o.total_amount,
                o.tax_rate,
                o.tax_amount,
                o.tax_included_in_total,
                o.target_completion_date
            FROM orders AS o
            WHERE UPPER(o.status) <> 'CANCELLED'
            ORDER BY o.order_date DESC
            LIMIT ?
            """,
            (limit,),
        )
        order_rows = cursor.fetchall()

        order_ids = [row["id"] for row in order_rows]
        items_by_order: dict[int, List[OrderItem]] = {order_id: [] for order_id in order_ids}

        if order_ids:
            placeholder = ",".join("?" for _ in order_ids)
            item_cursor = connection.cursor()
            item_cursor.execute(
                f"""
                SELECT
                    order_id,
                    product_id,
                    product_sku,
                    product_name,
                    product_description,
                    quantity,
                    unit_price,
                    base_unit_cost,
                    cost_components,
                    is_freebie,
                    applied_discount,
                    applied_tax,
                    price_adjustment_note
                FROM order_items
                WHERE order_id IN ({placeholder})
                ORDER BY id
                """,
                order_ids,
            )
            for row in item_cursor.fetchall():
                items_by_order[row["order_id"]].append(
                    OrderItem(
                        product_name=row["product_name"],
                        product_description=row["product_description"],
                        quantity=int(row["quantity"]),
                        unit_price=float(row["unit_price"]),
                        product_sku=(row["product_sku"] or ""),
                        product_id=row["product_id"],
                        base_unit_cost=float(row["base_unit_cost"] or 0.0),
                        cost_components=_deserialize_components(row["cost_components"]),
                        is_freebie=bool(row["is_freebie"]),
                        applied_discount=float(row["applied_discount"] or 0.0),
                        applied_tax=float(row["applied_tax"] or 0.0),
                        price_adjustment_note=row["price_adjustment_note"] or "",
                    )
                )
            item_cursor.close()

        orders: List[Order] = []
        for row in order_rows:
            orders.append(
                Order(
                    id=int(row["id"]),
                    order_number=row["order_number"],
                    customer_name=row["customer_name"],
                    customer_address=row["customer_address"],
                    order_date=_parse_date(row["order_date"]),
                    ship_date=_parse_date(row["ship_date"]) if row["ship_date"] else None,
                    status=row["status"],
                    is_paid=bool(row["is_paid"]),
                    carrier=row["carrier"] or "",
                    tracking_number=row["tracking_number"] or "",
                    notes=row["notes"] or "",
                    tax_rate=float(row["tax_rate"] or 0.0),
                    tax_amount=float(row["tax_amount"] or 0.0),
                    tax_included_in_total=bool(row["tax_included_in_total"]),
                    target_completion_date=_parse_date(row["target_completion_date"])
                    if row["target_completion_date"]
                    else None,
                    items=items_by_order.get(int(row["id"]), []),
                )
            )
        cursor.close()
        return orders


def fetch_order_destinations() -> List[tuple[str, str, str]]:
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                order_number,
                customer_name,
                customer_address
            FROM orders
            WHERE TRIM(IFNULL(customer_address, '')) <> ''
            """
        ).fetchall()

    results: List[tuple[str, str, str]] = []
    for row in rows:
        results.append(
            (
                row["order_number"],
                row["customer_name"],
                row["customer_address"],
            )
        )
    return results


def fetch_order(order_id: int) -> Optional[Order]:
    with create_connection() as connection:
        order_row = connection.execute(
            """
            SELECT
                id,
                order_number,
                customer_name,
                customer_address,
                order_date,
                ship_date,
                status,
                is_paid,
                carrier,
                tracking_number,
                notes,
                total_amount,
                tax_rate,
                tax_amount,
                tax_included_in_total,
                target_completion_date
            FROM orders
            WHERE id = ?
            LIMIT 1
            """,
            (int(order_id),),
        ).fetchone()

        if order_row is None:
            return None

        item_rows = connection.execute(
            """
            SELECT
                product_id,
                product_sku,
                product_name,
                product_description,
                quantity,
                unit_price,
                base_unit_cost,
                cost_components,
                is_freebie,
                applied_discount,
                applied_tax,
                price_adjustment_note
            FROM order_items
            WHERE order_id = ?
            ORDER BY id
            """,
            (int(order_id),),
        ).fetchall()

    items = [
        OrderItem(
            product_name=row["product_name"],
            product_description=row["product_description"],
            quantity=int(row["quantity"]),
            unit_price=float(row["unit_price"]),
            product_sku=row["product_sku"] or "",
            product_id=row["product_id"],
            base_unit_cost=float(row["base_unit_cost"] or 0.0),
            cost_components=_deserialize_components(row["cost_components"]),
            is_freebie=bool(row["is_freebie"]),
            applied_discount=float(row["applied_discount"] or 0.0),
            applied_tax=float(row["applied_tax"] or 0.0),
            price_adjustment_note=row["price_adjustment_note"] or "",
        )
        for row in item_rows
    ]

    return Order(
        id=int(order_row["id"]),
        order_number=order_row["order_number"],
        customer_name=order_row["customer_name"],
        customer_address=order_row["customer_address"],
        order_date=_parse_date(order_row["order_date"]),
        ship_date=_parse_date(order_row["ship_date"]) if order_row["ship_date"] else None,
        status=order_row["status"],
        is_paid=bool(order_row["is_paid"]),
        carrier=order_row["carrier"] or "",
        tracking_number=order_row["tracking_number"] or "",
        notes=order_row["notes"] or "",
        target_completion_date=_parse_date(order_row["target_completion_date"])
        if order_row["target_completion_date"]
        else None,
        tax_rate=float(order_row["tax_rate"] or 0.0),
        tax_amount=float(order_row["tax_amount"] or 0.0),
        tax_included_in_total=bool(order_row["tax_included_in_total"]),
        items=items,
    )


def update_order_status(order_id: int, status: str, *, ship_date: Optional[date] = None) -> None:
    with create_connection() as connection:
        connection.execute(
            """
            UPDATE orders
            SET status = ?,
                ship_date = ?
            WHERE id = ?
            """,
            (status.strip(), _format_date(ship_date), int(order_id)),
        )
        connection.commit()


def delete_order(order_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM orders WHERE id = ?", (int(order_id),))
        connection.commit()


def log_order_event(
    order_id: Optional[int],
    order_number: str,
    event_type: str,
    description: str,
    amount_delta: float,
) -> None:
    with create_connection() as connection:
        connection.execute(
            """
            INSERT INTO order_history (
                order_id,
                order_number,
                event_type,
                description,
                amount_delta
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(order_id) if order_id is not None else None,
                order_number.strip(),
                event_type.strip(),
                description.strip(),
                float(amount_delta),
            ),
        )
        connection.commit()


def fetch_order_history(
    order_number: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 200,
) -> List[OrderHistoryEvent]:
    sql = [
        """
        SELECT
            id,
            order_id,
            order_number,
            event_type,
            description,
            amount_delta,
            created_at
        FROM order_history
        WHERE 1 = 1
        """
    ]
    params: List[object] = []

    if order_number:
        sql.append("AND UPPER(order_number) LIKE UPPER(?)")
        params.append(f"%{order_number.strip()}%")

    if start_date:
        sql.append("AND DATE(created_at) >= ?")
        params.append(_format_date(start_date))

    if end_date:
        sql.append("AND DATE(created_at) <= ?")
        params.append(_format_date(end_date))

    sql.append("ORDER BY datetime(created_at) DESC")
    sql.append("LIMIT ?")
    params.append(int(limit))

    query = "\n".join(sql)

    with create_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    events: List[OrderHistoryEvent] = []
    for row in rows:
        raw_created = row["created_at"]
        created_at = _parse_timestamp(raw_created)
        events.append(
            OrderHistoryEvent(
                id=int(row["id"]),
                order_id=(int(row["order_id"]) if row["order_id"] is not None else None),
                order_number=row["order_number"],
                event_type=row["event_type"],
                description=row["description"],
                amount_delta=float(row["amount_delta"] or 0.0),
                created_at=created_at,
            )
        )
    return events


def fetch_total_sales() -> float:
    total_sales, _, _ = fetch_financial_totals()
    return total_sales


def fetch_financial_totals() -> tuple[float, float, float]:
    with create_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                oi.quantity,
                oi.unit_price,
                oi.base_unit_cost,
                oi.cost_components,
                oi.is_freebie
            FROM order_items AS oi
            JOIN orders AS o ON o.id = oi.order_id
            WHERE UPPER(o.status) <> 'CANCELLED'
            """
        )
        total_sales = 0.0
        total_cost = 0.0
        freebie_cost = 0.0
        for row in cursor.fetchall():
            quantity = int(row["quantity"] or 0)
            unit_price = float(row["unit_price"] or 0.0)
            base_cost = float(row["base_unit_cost"] or 0.0)
            extras = sum(component.amount for component in _deserialize_components(row["cost_components"]))
            line_cost = quantity * (base_cost + extras)
            total_sales += quantity * unit_price
            total_cost += line_cost
            if bool(row["is_freebie"]):
                freebie_cost += line_cost
        cursor.close()
    return total_sales, total_cost, freebie_cost


def fetch_tax_total(start_date: Optional[date] = None, end_date: Optional[date] = None) -> float:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(tax_amount), 0) AS total_tax
            FROM orders
            WHERE UPPER(status) <> 'CANCELLED'
              AND (? IS NULL OR order_date >= ?)
              AND (? IS NULL OR order_date <= ?)
            """,
            (
                _format_date(start_date),
                _format_date(start_date),
                _format_date(end_date),
                _format_date(end_date),
            ),
        ).fetchone()
    return float(row["total_tax"] or 0.0)


def fetch_product_sales_summary() -> List[ProductSalesSummary]:
    with create_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                oi.product_sku,
                oi.product_name,
                oi.product_description,
                oi.quantity,
                oi.unit_price,
                oi.base_unit_cost,
                oi.cost_components,
                p.name AS product_record_name
            FROM order_items AS oi
            JOIN orders AS o ON o.id = oi.order_id
            LEFT JOIN products AS p ON p.sku = oi.product_sku
            WHERE UPPER(o.status) <> 'CANCELLED'
            """
        )
        rows = cursor.fetchall()
        cursor.close()

    aggregates: Dict[str, Dict[str, float | str]] = {}

    for row in rows:
        sku = (row["product_sku"] or "").strip()
        order_name = (row["product_name"] or "").strip()
        product_name = (row["product_record_name"] or "").strip() or order_name

        if not sku:
            label = order_name or product_name
        elif product_name:
            label = f"{sku} - {product_name}"
        else:
            label = sku

        entry = aggregates.get(label)
        if entry is None:
            entry = {
                "quantity": 0,
                "sales": 0.0,
                "cost": 0.0,
            }
            aggregates[label] = entry

        quantity = int(row["quantity"] or 0)
        unit_price = float(row["unit_price"] or 0.0)
        base_cost = float(row["base_unit_cost"] or 0.0)
        extras = sum(component.amount for component in _deserialize_components(row["cost_components"]))

        entry["quantity"] += quantity
        entry["sales"] += quantity * unit_price
        entry["cost"] += quantity * (base_cost + extras)

    summaries: List[ProductSalesSummary] = []
    for label, data in aggregates.items():
        total_sales = float(data["sales"])
        total_cost = float(data["cost"])
        profit = total_sales - total_cost
        margin = profit / total_sales if total_sales else 0.0
        summaries.append(
            ProductSalesSummary(
                product_name=label,
                total_quantity=int(data["quantity"]),
                total_sales=total_sales,
                total_cost=total_cost,
                total_profit=profit,
                margin=margin,
            )
        )

    summaries.sort(key=lambda item: (-item.total_sales, item.product_name))
    return summaries


def fetch_top_customers(limit: int = 10) -> List[CustomerSalesSummary]:
    with create_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                o.id,
                TRIM(o.customer_name) AS customer_name,
                o.total_amount
            FROM orders AS o
            WHERE TRIM(o.customer_name) <> ''
              AND UPPER(o.status) <> 'CANCELLED'
            """
        )
        order_rows = cursor.fetchall()
        cursor.close()

    if not order_rows:
        return []

    order_ids = [int(row["id"]) for row in order_rows]
    items_by_order: Dict[int, List[OrderItem]] = {order_id: [] for order_id in order_ids}

    with create_connection() as connection:
        placeholder = ",".join("?" for _ in order_ids)
        item_cursor = connection.cursor()
        item_cursor.execute(
            f"""
            SELECT
                order_id,
                product_id,
                product_sku,
                product_name,
                product_description,
                quantity,
                unit_price,
                base_unit_cost,
                cost_components,
                is_freebie,
                applied_discount,
                applied_tax,
                price_adjustment_note
            FROM order_items
            WHERE order_id IN ({placeholder})
            ORDER BY id
            """,
            order_ids,
        )
        for row in item_cursor.fetchall():
            items_by_order[int(row["order_id"])].append(
                OrderItem(
                    product_name=row["product_name"],
                    product_description=row["product_description"],
                    quantity=int(row["quantity"]),
                    unit_price=float(row["unit_price"]),
                    product_sku=row["product_sku"] or "",
                    product_id=row["product_id"],
                    base_unit_cost=float(row["base_unit_cost"] or 0.0),
                    cost_components=_deserialize_components(row["cost_components"]),
                    is_freebie=bool(row["is_freebie"]),
                    applied_discount=float(row["applied_discount"] or 0.0),
                    applied_tax=float(row["applied_tax"] or 0.0),
                    price_adjustment_note=row["price_adjustment_note"] or "",
                )
            )
        item_cursor.close()

    aggregates: Dict[str, Dict[str, float | int]] = {}
    for row in order_rows:
        order_id = int(row["id"])
        customer = row["customer_name"]
        total_amount = float(row["total_amount"] or 0.0)
        items = items_by_order.get(order_id, [])
        total_cost = sum(item.line_cost for item in items)
        profit = total_amount - total_cost

        entry = aggregates.get(customer)
        if entry is None:
            entry = {
                "orders": 0,
                "sales": 0.0,
                "cost": 0.0,
            }
            aggregates[customer] = entry

        entry["orders"] += 1
        entry["sales"] += total_amount
        entry["cost"] += total_cost

    summaries: List[CustomerSalesSummary] = []
    for customer, data in aggregates.items():
        total_sales = float(data["sales"])
        total_cost = float(data["cost"])
        profit = total_sales - total_cost
        margin = profit / total_sales if total_sales else 0.0
        order_count = int(data["orders"])
        average_order = total_sales / order_count if order_count else 0.0
        summaries.append(
            CustomerSalesSummary(
                customer_name=customer,
                order_count=order_count,
                total_sales=total_sales,
                average_order=average_order,
                total_cost=total_cost,
                total_profit=profit,
                margin=margin,
            )
        )

    summaries.sort(key=lambda item: (-item.total_sales, item.customer_name))
    return summaries[: max(0, int(limit))]


def fetch_product_forecast(window_days: int = 30, limit: int = 25) -> List[ProductForecast]:
    window_days = max(1, int(window_days))
    start_date = date.today() - timedelta(days=window_days)

    with create_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                p.id,
                p.sku,
                p.name,
                p.status,
                p.inventory_count,
                IFNULL(s.qty_sold, 0) AS qty_sold
            FROM products AS p
            LEFT JOIN (
                SELECT
                    oi.product_sku AS sku,
                    SUM(oi.quantity) AS qty_sold
                FROM order_items AS oi
                JOIN orders AS o ON o.id = oi.order_id
                WHERE o.order_date >= ?
                  AND UPPER(o.status) <> 'CANCELLED'
                GROUP BY oi.product_sku
            ) AS s ON s.sku = p.sku
            """,
            (_format_date(start_date),),
        )
        rows = cursor.fetchall()
        cursor.close()

    forecasts: List[ProductForecast] = []
    for row in rows:
        inventory = int(row["inventory_count"] or 0)
        qty_sold = float(row["qty_sold"] or 0.0)
        avg_daily = qty_sold / float(window_days)
        avg_weekly = avg_daily * 7.0
        if avg_daily > 0:
            days_until = max(0, int(math.ceil(inventory / avg_daily)))
        else:
            days_until = None

        forecasts.append(
            ProductForecast(
                product_id=int(row["id"]) if row["id"] is not None else None,
                sku=row["sku"],
                name=row["name"],
                status=row["status"] or "",
                inventory_count=inventory,
                average_weekly_sales=avg_weekly,
                days_until_stockout=days_until,
            )
        )

    forecasts.sort(
        key=lambda item: (
            item.days_until_stockout is None,
            item.days_until_stockout if item.days_until_stockout is not None else float("inf"),
            -item.average_weekly_sales,
        )
    )

    return forecasts[: max(0, int(limit))]


def fetch_outstanding_orders() -> List[OutstandingOrder]:
    with create_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                id,
                order_number,
                customer_name,
                order_date,
                total_amount,
                tax_amount,
                tax_included_in_total,
                status,
                carrier,
                tracking_number,
                                notes,
                target_completion_date
            FROM orders
            WHERE UPPER(status) <> 'SHIPPED'
              AND UPPER(status) <> 'CANCELLED'
            ORDER BY order_date ASC;
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            OutstandingOrder(
                id=int(row["id"]),
                order_number=row["order_number"],
                customer_name=row["customer_name"],
                order_date=_parse_date(row["order_date"]),
                total_amount=float(row["total_amount"]),
                tax_amount=float(row["tax_amount"] or 0.0),
                tax_included_in_total=bool(row["tax_included_in_total"]),
                status=row["status"],
                carrier=row["carrier"] or "",
                tracking_number=row["tracking_number"] or "",
                notes=row["notes"] or "",
                target_completion_date=_parse_date(row["target_completion_date"])
                if row["target_completion_date"]
                else None,
            )
            for row in rows
        ]


def fetch_completed_orders(limit: int = 25) -> List[CompletedOrder]:
    with create_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                id,
                order_number,
                customer_name,
                order_date,
                ship_date,
                total_amount,
                tax_amount,
                tax_included_in_total,
                status,
                carrier,
                tracking_number,
                notes,
                target_completion_date
            FROM orders
            WHERE UPPER(status) = 'SHIPPED'
            ORDER BY COALESCE(ship_date, order_date) DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            CompletedOrder(
                id=int(row["id"]),
                order_number=row["order_number"],
                customer_name=row["customer_name"],
                order_date=_parse_date(row["order_date"]),
                ship_date=_parse_date(row["ship_date"]) if row["ship_date"] else None,
                total_amount=float(row["total_amount"]),
                tax_amount=float(row["tax_amount"] or 0.0),
                tax_included_in_total=bool(row["tax_included_in_total"]),
                status=row["status"],
                carrier=row["carrier"] or "",
                tracking_number=row["tracking_number"] or "",
                notes=row["notes"] or "",
                target_completion_date=_parse_date(row["target_completion_date"])
                if row["target_completion_date"]
                else None,
            )
            for row in rows
        ]


def fetch_order_report(start_date: Optional[date], end_date: Optional[date]) -> List[OrderReportRow]:
    with create_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                o.id,
                o.order_number,
                o.customer_name,
                o.order_date,
                o.ship_date,
                o.status,
                o.carrier,
                o.tracking_number,
                o.notes,
                o.total_amount,
                o.tax_rate,
                o.tax_amount,
                o.tax_included_in_total,
                o.target_completion_date
            FROM orders AS o
            WHERE (? IS NULL OR o.order_date >= ?)
              AND (? IS NULL OR o.order_date <= ?)
              AND UPPER(o.status) <> 'CANCELLED'
            ORDER BY o.order_date DESC;
            """,
            (
                _format_date(start_date),
                _format_date(start_date),
                _format_date(end_date),
                _format_date(end_date),
            ),
        )
        order_rows = cursor.fetchall()
        cursor.close()

    if not order_rows:
        return []

    order_ids = [int(row["id"]) for row in order_rows]
    items_by_order: dict[int, List[OrderItem]] = {order_id: [] for order_id in order_ids}

    with create_connection() as connection:
        placeholder = ",".join("?" for _ in order_ids)
        item_cursor = connection.cursor()
        item_cursor.execute(
            f"""
            SELECT
                order_id,
                product_id,
                product_sku,
                product_name,
                product_description,
                quantity,
                unit_price,
                base_unit_cost,
                cost_components,
                is_freebie,
                applied_discount,
                applied_tax,
                price_adjustment_note
            FROM order_items
            WHERE order_id IN ({placeholder})
            ORDER BY id
            """,
            order_ids,
        )
        for row in item_cursor.fetchall():
            items_by_order[int(row["order_id"])].append(
                OrderItem(
                    product_name=row["product_name"],
                    product_description=row["product_description"],
                    quantity=int(row["quantity"]),
                    unit_price=float(row["unit_price"]),
                    product_sku=row["product_sku"] or "",
                    product_id=row["product_id"],
                    base_unit_cost=float(row["base_unit_cost"] or 0.0),
                    cost_components=_deserialize_components(row["cost_components"]),
                    is_freebie=bool(row["is_freebie"]),
                    applied_discount=float(row["applied_discount"] or 0.0),
                    applied_tax=float(row["applied_tax"] or 0.0),
                    price_adjustment_note=row["price_adjustment_note"] or "",
                )
            )
        item_cursor.close()

    report_rows: List[OrderReportRow] = []
    for row in order_rows:
        order_id = int(row["id"])
        items = items_by_order.get(order_id, [])
        total_amount = float(row["total_amount"])
        total_cost = sum(item.line_cost for item in items)
        freebie_cost = sum(
            item.line_cost for item in items if getattr(item, "is_freebie", False)
        )
        profit = total_amount - total_cost
        margin = profit / total_amount if total_amount else 0.0
        report_rows.append(
            OrderReportRow(
                order_id=order_id,
                order_number=row["order_number"],
                customer_name=row["customer_name"],
                order_date=_parse_date(row["order_date"]),
                ship_date=_parse_date(row["ship_date"]) if row["ship_date"] else None,
                status=row["status"],
                carrier=row["carrier"] or "",
                tracking_number=row["tracking_number"] or "",
                notes=row["notes"] or "",
                total_amount=total_amount,
                tax_rate=float(row["tax_rate"] or 0.0),
                tax_amount=float(row["tax_amount"] or 0.0),
                tax_included_in_total=bool(row["tax_included_in_total"]),
                products=_format_report_products(items),
                item_count=sum(item.quantity for item in items),
                target_completion_date=_parse_date(row["target_completion_date"])
                if row["target_completion_date"]
                else None,
                total_cost=total_cost,
                profit=profit,
                margin=margin,
                freebie_cost=freebie_cost,
                adjustment_summary=_summarize_adjustments(items),
            )
        )

    return report_rows


def build_dashboard_snapshot() -> DashboardSnapshot:
    total_sales, total_cost, freebie_cost = fetch_financial_totals()
    tax_total = fetch_tax_total()
    total_profit = total_sales - total_cost
    net_sales = total_sales - freebie_cost
    if net_sales > 0:
        margin = total_profit / net_sales
    elif total_sales > 0:
        margin = total_profit / total_sales
    else:
        margin = 0.0
    product_breakdown = fetch_product_sales_summary()
    outstanding_details = fetch_outstanding_orders()
    completed_details = fetch_completed_orders()
    top_customers = fetch_top_customers()
    inventory_forecast = fetch_product_forecast()
    outstanding_count = len(outstanding_details)
    completed_count = len(completed_details)
    return DashboardSnapshot(
        total_sales=total_sales,
        total_cost=total_cost,
        total_profit=total_profit,
        profit_margin=margin,
        outstanding_orders=outstanding_count,
        product_breakdown=product_breakdown,
        outstanding_details=outstanding_details,
        completed_orders=completed_count,
        completed_details=completed_details,
        top_customers=top_customers,
        inventory_forecast=inventory_forecast,
        freebie_cost=freebie_cost,
        net_sales=net_sales,
        tax_total=tax_total,
    )


def _extract_alpha_prefix(value: str) -> str:
    if not value:
        return "ORD"
    match = re.search(r"[A-Za-z]+", value.upper())
    if match:
        return match.group(0)
    return "ORD"


def _parse_sequence(order_number: str, prefix: str) -> int:
    suffix = order_number[len(prefix) :]
    match = re.search(r"(\d+)$", suffix)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return 0
    return 0


def _format_date(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime(_DATE_FORMAT)


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw, _DATE_FORMAT).date()


def _parse_timestamp(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.utcnow()


def _format_report_products(items: Iterable[OrderItem]) -> str:
    parts: List[str] = []
    for item in items:
        prefix = item.product_sku.strip()
        if prefix:
            label = f"{prefix} - {item.product_name}"
        else:
            label = item.product_name
        description = item.product_description.strip()
        if description:
            label = f"{label} ({description})"
        summary = item.adjustment_summary.strip()
        if summary:
            label = f"{label} [{summary}]"
        parts.append(f"{label} x{item.quantity}")
    return ", ".join(parts)


def _summarize_adjustments(items: Iterable[OrderItem]) -> str:
    details: List[str] = []
    for item in items:
        summary = item.adjustment_summary.strip()
        if not summary:
            continue
        label = item.product_name.strip() or item.product_sku.strip() or "Item"
        details.append(f"{label}: {summary}")
    return "; ".join(details)


def _deserialize_components(raw: object) -> List[CostComponent]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    components: List[CostComponent] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label", "")).strip()
        amount = entry.get("amount", 0)
        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            amount_value = 0.0
        if not label and amount_value == 0.0:
            continue
        components.append(CostComponent(label=label, amount=amount_value))
    return components


def _serialize_components(components: Iterable[CostComponent]) -> str:
    payload = [
        {
            "label": component.label,
            "amount": float(component.amount),
        }
        for component in components
    ]
    return json.dumps(payload)
