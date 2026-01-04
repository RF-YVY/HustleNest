from __future__ import annotations

import re
import sqlite3
import math
from datetime import date, datetime, timedelta
from typing import List, Optional

from ..models.order_models import (
    CompletedOrder,
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
                    carrier,
                    tracking_number,
                    total_amount,
                    target_completion_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.order_number.strip(),
                    order.customer_name.strip(),
                    order.customer_address.strip(),
                    order.order_date.strftime(_DATE_FORMAT),
                    order.ship_date.strftime(_DATE_FORMAT) if order.ship_date else None,
                    order.status.strip(),
                    order.carrier.strip(),
                    order.tracking_number.strip(),
                    order.total_amount,
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
                    unit_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
                    carrier = ?,
                    tracking_number = ?,
                    total_amount = ?,
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
                    order.carrier.strip(),
                    order.tracking_number.strip(),
                    order.total_amount,
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
                    unit_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
                o.carrier,
                o.tracking_number,
                o.total_amount,
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
                    unit_price
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
                    carrier=row["carrier"] or "",
                    tracking_number=row["tracking_number"] or "",
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
                carrier,
                tracking_number,
                total_amount,
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
                unit_price
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
        carrier=order_row["carrier"] or "",
        tracking_number=order_row["tracking_number"] or "",
        target_completion_date=_parse_date(order_row["target_completion_date"])
        if order_row["target_completion_date"]
        else None,
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
    with create_connection() as connection:
        cursor = connection.execute(
            "SELECT IFNULL(SUM(total_amount), 0) AS total FROM orders WHERE UPPER(status) <> 'CANCELLED';"
        )
        value = cursor.fetchone()["total"]
        cursor.close()
        return float(value)


def fetch_product_sales_summary() -> List[ProductSalesSummary]:
    with create_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                CASE
                    WHEN TRIM(oi.product_sku) = '' THEN oi.product_name
                    WHEN p.name IS NULL OR TRIM(p.name) = '' THEN oi.product_sku
                    ELSE oi.product_sku || ' - ' || p.name
                END AS product_label,
                SUM(oi.quantity) AS total_quantity,
                SUM(oi.quantity * oi.unit_price) AS total_sales
            FROM order_items AS oi
            JOIN orders AS o ON o.id = oi.order_id
            LEFT JOIN products AS p ON p.sku = oi.product_sku
            WHERE UPPER(o.status) <> 'CANCELLED'
            GROUP BY product_label
            ORDER BY total_sales DESC, product_label ASC;
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            ProductSalesSummary(
                product_name=row["product_label"],
                total_quantity=int(row["total_quantity"] or 0),
                total_sales=float(row["total_sales"] or 0.0),
            )
            for row in rows
        ]


def fetch_top_customers(limit: int = 10) -> List[CustomerSalesSummary]:
    with create_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                TRIM(o.customer_name) AS customer_name,
                COUNT(*) AS order_count,
                SUM(o.total_amount) AS total_sales,
                CASE
                    WHEN COUNT(*) = 0 THEN 0
                    ELSE SUM(o.total_amount) / COUNT(*)
                END AS average_order
            FROM orders AS o
            WHERE TRIM(o.customer_name) <> ''
              AND UPPER(o.status) <> 'CANCELLED'
            GROUP BY TRIM(o.customer_name)
            ORDER BY total_sales DESC, customer_name ASC
            LIMIT ?;
            """,
            (int(limit),),
        )
        rows = cursor.fetchall()
        cursor.close()

    return [
        CustomerSalesSummary(
            customer_name=row["customer_name"],
            order_count=int(row["order_count"] or 0),
            total_sales=float(row["total_sales"] or 0.0),
            average_order=float(row["average_order"] or 0.0),
        )
        for row in rows
    ]


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
                status,
                carrier,
                tracking_number,
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
                status=row["status"],
                carrier=row["carrier"] or "",
                tracking_number=row["tracking_number"] or "",
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
                status,
                carrier,
                tracking_number,
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
                status=row["status"],
                carrier=row["carrier"] or "",
                tracking_number=row["tracking_number"] or "",
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
                o.id AS order_id,
                o.order_number,
                o.customer_name,
                o.order_date,
                o.ship_date,
                o.status,
                o.carrier,
                o.tracking_number,
                o.total_amount,
                o.target_completion_date,
                IFNULL(SUM(oi.quantity), 0) AS total_items,
                IFNULL(
                    GROUP_CONCAT(
                        (CASE
                            WHEN TRIM(oi.product_sku) = '' THEN oi.product_name
                            ELSE oi.product_sku || ' - ' || oi.product_name
                         END) ||
                        CASE WHEN TRIM(oi.product_description) = '' THEN ''
                             ELSE ' (' || oi.product_description || ')'
                        END || ' x' || oi.quantity,
                        ', '
                    ),
                    ''
                ) AS products
            FROM orders AS o
            LEFT JOIN order_items AS oi ON oi.order_id = o.id
            WHERE (? IS NULL OR o.order_date >= ?)
              AND (? IS NULL OR o.order_date <= ?)
                            AND UPPER(o.status) <> 'CANCELLED'
            GROUP BY o.id
            ORDER BY o.order_date DESC;
            """,
            (
                _format_date(start_date),
                _format_date(start_date),
                _format_date(end_date),
                _format_date(end_date),
            ),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            OrderReportRow(
                order_id=int(row["order_id"]),
                order_number=row["order_number"],
                customer_name=row["customer_name"],
                order_date=_parse_date(row["order_date"]),
                ship_date=_parse_date(row["ship_date"]) if row["ship_date"] else None,
                status=row["status"],
                carrier=row["carrier"] or "",
                tracking_number=row["tracking_number"] or "",
                total_amount=float(row["total_amount"]),
                products=row["products"],
                item_count=int(row["total_items"] or 0),
                target_completion_date=_parse_date(row["target_completion_date"])
                if row["target_completion_date"]
                else None,
            )
            for row in rows
        ]


def build_dashboard_snapshot() -> DashboardSnapshot:
    total_sales = fetch_total_sales()
    product_breakdown = fetch_product_sales_summary()
    outstanding_details = fetch_outstanding_orders()
    completed_details = fetch_completed_orders()
    top_customers = fetch_top_customers()
    inventory_forecast = fetch_product_forecast()
    outstanding_count = len(outstanding_details)
    completed_count = len(completed_details)
    return DashboardSnapshot(
        total_sales=total_sales,
        outstanding_orders=outstanding_count,
        product_breakdown=product_breakdown,
        outstanding_details=outstanding_details,
        completed_orders=completed_count,
        completed_details=completed_details,
        top_customers=top_customers,
        inventory_forecast=inventory_forecast,
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
