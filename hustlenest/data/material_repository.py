from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, List, Optional

from ..models.order_models import Material, MaterialTransaction
from .database import create_connection

_DATE_FORMAT = "%Y-%m-%d"


def _row_to_material(row) -> Material:
    last_restocked_value = row["last_restocked"] if row["last_restocked"] else None
    last_restocked = (
        datetime.strptime(last_restocked_value, _DATE_FORMAT).date()
        if last_restocked_value
        else None
    )
    return Material(
        id=int(row["id"]),
        sku=row["sku"],
        name=row["name"],
        category=row["category"] or "",
        description=row["description"] or "",
        unit_of_measure=row["unit_of_measure"] or "",
        quantity_on_hand=float(row["quantity_on_hand"] or 0.0),
        reorder_point=float(row["reorder_point"] or 0.0),
        cost_per_unit=float(row["cost_per_unit"] or 0.0),
        vendor_id=row["vendor_id"],
        last_restocked=last_restocked,
        notes=row["notes"] or "",
        lead_time_days=int(row["lead_time_days"] or 0),
        archived=bool(row["archived"]),
    )


def list_materials(*, include_archived: bool = False) -> List[Material]:
    where_clause = "" if include_archived else "WHERE archived = 0"
    query = f"""
        SELECT
            id,
            sku,
            name,
            category,
            description,
            unit_of_measure,
            quantity_on_hand,
            reorder_point,
            cost_per_unit,
            vendor_id,
            last_restocked,
            notes,
            lead_time_days,
            archived
        FROM materials
        {where_clause}
        ORDER BY archived, UPPER(name)
    """
    with create_connection() as connection:
        rows = connection.execute(query).fetchall()

    return [_row_to_material(row) for row in rows]


def get_material(material_id: int) -> Optional[Material]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                sku,
                name,
                category,
                description,
                unit_of_measure,
                quantity_on_hand,
                reorder_point,
                cost_per_unit,
                vendor_id,
                last_restocked,
                notes,
                lead_time_days,
                archived
            FROM materials
            WHERE id = ?
            LIMIT 1
            """,
            (int(material_id),),
        ).fetchone()

    if row is None:
        return None
    return _row_to_material(row)


def save_material(material: Material) -> int:
    last_restocked = material.last_restocked.isoformat() if material.last_restocked else None
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if material.id:
                cursor.execute(
                    """
                    UPDATE materials
                    SET
                        sku = ?,
                        name = ?,
                        category = ?,
                        description = ?,
                        unit_of_measure = ?,
                        quantity_on_hand = ?,
                        reorder_point = ?,
                        cost_per_unit = ?,
                        vendor_id = ?,
                        last_restocked = ?,
                        notes = ?,
                        lead_time_days = ?,
                        archived = ?
                    WHERE id = ?
                    """,
                    (
                        material.sku.strip(),
                        material.name.strip(),
                        material.category.strip(),
                        material.description.strip(),
                        material.unit_of_measure.strip(),
                        float(material.quantity_on_hand),
                        float(material.reorder_point),
                        float(material.cost_per_unit),
                        material.vendor_id,
                        last_restocked,
                        material.notes.strip(),
                        int(material.lead_time_days or 0),
                        int(bool(material.archived)),
                        int(material.id),
                    ),
                )
                material_id = int(material.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO materials (
                        sku,
                        name,
                        category,
                        description,
                        unit_of_measure,
                        quantity_on_hand,
                        reorder_point,
                        cost_per_unit,
                        vendor_id,
                        last_restocked,
                        notes,
                        lead_time_days,
                        archived
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        material.sku.strip(),
                        material.name.strip(),
                        material.category.strip(),
                        material.description.strip(),
                        material.unit_of_measure.strip(),
                        float(material.quantity_on_hand),
                        float(material.reorder_point),
                        float(material.cost_per_unit),
                        material.vendor_id,
                        last_restocked,
                        material.notes.strip(),
                        int(material.lead_time_days or 0),
                        int(bool(material.archived)),
                    ),
                )
                material_id = int(cursor.lastrowid)
            connection.commit()
            return material_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def set_material_archived(material_id: int, archived: bool) -> None:
    with create_connection() as connection:
        connection.execute(
            "UPDATE materials SET archived = ? WHERE id = ?",
            (int(bool(archived)), int(material_id)),
        )
        connection.commit()


def delete_material(material_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM materials WHERE id = ?", (int(material_id),))
        connection.commit()


def list_categories() -> List[str]:
    with create_connection() as connection:
        rows = connection.execute(
            "SELECT DISTINCT category FROM materials WHERE category <> '' ORDER BY UPPER(category)"
        ).fetchall()
    return [row["category"] for row in rows if row["category"]]


def _row_to_transaction(row) -> MaterialTransaction:
    timestamp_value = row["transaction_date"]
    timestamp = datetime.fromisoformat(timestamp_value) if timestamp_value else datetime.utcnow()
    return MaterialTransaction(
        id=int(row["id"]),
        material_id=int(row["material_id"]),
        transaction_date=timestamp,
        quantity_delta=float(row["quantity_delta"] or 0.0),
        unit_cost=float(row["unit_cost"] or 0.0),
        reason=row["reason"] or "",
        reference_type=row["reference_type"] or "",
        reference_id=row["reference_id"],
        created_by=row["created_by"] or "",
        notes=row["notes"] or "",
    )


def fetch_transactions(material_id: int, *, limit: int = 100) -> List[MaterialTransaction]:
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                material_id,
                transaction_date,
                quantity_delta,
                unit_cost,
                reason,
                reference_type,
                reference_id,
                created_by,
                notes
            FROM material_transactions
            WHERE material_id = ?
            ORDER BY transaction_date DESC, id DESC
            LIMIT ?
            """,
            (int(material_id), int(limit)),
        ).fetchall()

    return [_row_to_transaction(row) for row in rows]


def record_transaction(transaction: MaterialTransaction) -> int:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO material_transactions (
                    material_id,
                    transaction_date,
                    quantity_delta,
                    unit_cost,
                    reason,
                    reference_type,
                    reference_id,
                    created_by,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(transaction.material_id),
                    transaction.transaction_date.isoformat(timespec="seconds"),
                    float(transaction.quantity_delta),
                    float(transaction.unit_cost),
                    transaction.reason.strip(),
                    transaction.reference_type.strip(),
                    transaction.reference_id,
                    transaction.created_by.strip(),
                    transaction.notes.strip(),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def apply_material_delta(
    material_id: int,
    quantity_delta: float,
    *,
    unit_cost: float = 0.0,
    reason: str = "",
    reference_type: str = "",
    reference_id: Optional[int] = None,
    created_by: str = "",
    notes: str = "",
) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "UPDATE materials SET quantity_on_hand = quantity_on_hand + ? WHERE id = ?",
                (float(quantity_delta), int(material_id)),
            )
            if quantity_delta > 0:
                cursor.execute(
                    "UPDATE materials SET last_restocked = ? WHERE id = ?",
                    (date.today().isoformat(), int(material_id)),
                )
            cursor.execute(
                """
                INSERT INTO material_transactions (
                    material_id,
                    transaction_date,
                    quantity_delta,
                    unit_cost,
                    reason,
                    reference_type,
                    reference_id,
                    created_by,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(material_id),
                    timestamp,
                    float(quantity_delta),
                    float(unit_cost),
                    reason.strip(),
                    reference_type.strip(),
                    reference_id,
                    created_by.strip(),
                    notes.strip(),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
