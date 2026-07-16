from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, List, Optional

from ..models.order_models import LossRecord
from .database import create_connection

_DATE_FORMAT = "%Y-%m-%d"


def _row_to_loss(row) -> LossRecord:
    loss_date_value = row["loss_date"]
    loss_date = datetime.strptime(loss_date_value, _DATE_FORMAT).date() if loss_date_value else date.today()
    keys = set(row.keys())
    product_name = row["product_name"] if "product_name" in keys and row["product_name"] else ""
    material_name = row["material_name"] if "material_name" in keys and row["material_name"] else ""
    return LossRecord(
        id=int(row["id"]),
        amount=float(row["amount"] or 0.0),
        loss_date=loss_date,
        category=row["category"] or "",
        description=row["description"] or "",
        details=row["details"] or "",
        is_product_loss=bool(row["is_product_loss"]),
        recorded_by=row["recorded_by"] or "",
        quantity=float(row["quantity"] or 0.0),
        unit=row["unit"] or "",
        order_id=row["order_id"],
        order_item_id=row["order_item_id"],
        product_id=row["product_id"],
        material_id=row["material_id"],
        product_name=product_name,
        material_name=material_name,
    )


def fetch_losses(
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
) -> List[LossRecord]:
    conditions = []
    params: List[object] = []

    if start_date:
        conditions.append("loss_date >= ?")
        params.append(start_date.isoformat())
    if end_date:
        conditions.append("loss_date <= ?")
        params.append(end_date.isoformat())
    if categories:
        placeholders = ",".join("?" for _ in categories)
        conditions.append(f"category IN ({placeholders})")
        params.extend(list(categories))

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    limit_clause = ""
    if limit:
        limit_clause = f"LIMIT {int(limit)}"

    query = f"""
        SELECT
            l.id,
            l.amount,
            l.loss_date,
            l.category,
            l.description,
            l.details,
            l.is_product_loss,
            l.recorded_by,
            l.quantity,
            l.unit,
            l.order_id,
            l.order_item_id,
            l.product_id,
            l.material_id,
            p.name AS product_name,
            m.name AS material_name
        FROM losses AS l
        LEFT JOIN products AS p ON p.id = l.product_id
        LEFT JOIN materials AS m ON m.id = l.material_id
        {where_clause}
        ORDER BY l.loss_date DESC, l.id DESC
        {limit_clause}
    """

    with create_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    return [_row_to_loss(row) for row in rows]


def get_loss(loss_id: int) -> Optional[LossRecord]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                l.id,
                l.amount,
                l.loss_date,
                l.category,
                l.description,
                l.details,
                l.is_product_loss,
                l.recorded_by,
                l.quantity,
                l.unit,
                l.order_id,
                l.order_item_id,
                l.product_id,
                l.material_id,
                p.name AS product_name,
                m.name AS material_name
            FROM losses AS l
            LEFT JOIN products AS p ON p.id = l.product_id
            LEFT JOIN materials AS m ON m.id = l.material_id
            WHERE l.id = ?
            LIMIT 1
            """,
            (int(loss_id),),
        ).fetchone()

    if row is None:
        return None
    return _row_to_loss(row)


def create_loss(record: LossRecord) -> int:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO losses (
                    order_id,
                    order_item_id,
                    product_id,
                    material_id,
                    amount,
                    quantity,
                    unit,
                    loss_date,
                    category,
                    description,
                    details,
                    is_product_loss,
                    recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.order_id,
                    record.order_item_id,
                    record.product_id,
                    record.material_id,
                    float(record.amount),
                    float(record.quantity),
                    record.unit.strip(),
                    record.loss_date.isoformat(),
                    record.category.strip(),
                    record.description.strip(),
                    record.details.strip(),
                    int(bool(record.is_product_loss)),
                    record.recorded_by.strip(),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def update_loss(loss_id: int, record: LossRecord) -> None:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE losses
                SET
                    order_id = ?,
                    order_item_id = ?,
                    product_id = ?,
                    material_id = ?,
                    amount = ?,
                    quantity = ?,
                    unit = ?,
                    loss_date = ?,
                    category = ?,
                    description = ?,
                    details = ?,
                    is_product_loss = ?,
                    recorded_by = ?
                WHERE id = ?
                """,
                (
                    record.order_id,
                    record.order_item_id,
                    record.product_id,
                    record.material_id,
                    float(record.amount),
                    float(record.quantity),
                    record.unit.strip(),
                    record.loss_date.isoformat(),
                    record.category.strip(),
                    record.description.strip(),
                    record.details.strip(),
                    int(bool(record.is_product_loss)),
                    record.recorded_by.strip(),
                    int(loss_id),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_loss(loss_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM losses WHERE id = ?", (int(loss_id),))
        connection.commit()


def list_categories() -> List[str]:
    with create_connection() as connection:
        rows = connection.execute(
            "SELECT DISTINCT category FROM losses WHERE category <> '' ORDER BY UPPER(category)"
        ).fetchall()
    return [row["category"] for row in rows if row["category"]]
