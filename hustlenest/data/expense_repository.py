from __future__ import annotations

import json
from datetime import date, datetime
from typing import Iterable, List, Optional

from ..models.order_models import Expense, RecurringExpense
from .database import create_connection

_DATE_FORMAT = "%Y-%m-%d"


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.strptime(value, _DATE_FORMAT).date()


def _row_to_expense(row) -> Expense:
    tags_value = row["tags"] or "[]"
    try:
        tags = json.loads(tags_value)
    except json.JSONDecodeError:
        tags = []
    return Expense(
        id=int(row["id"]),
        category=row["category"],
        amount=float(row["amount"] or 0.0),
        expense_date=datetime.strptime(row["expense_date"], _DATE_FORMAT).date(),
        description=row["description"] or "",
        payment_method=row["payment_method"] or "",
        vendor_id=row["vendor_id"],
        material_id=row["material_id"],
        is_recurring=bool(row["is_recurring"]),
        recurring_id=row["recurring_id"],
        document_id=row["document_id"],
        tags=tags,
        notes=row["notes"] or "",
    )


def _row_to_recurring(row) -> RecurringExpense:
    return RecurringExpense(
        id=int(row["id"]),
        category=row["category"] or "",
        amount=float(row["amount"] or 0.0),
        frequency=row["frequency"],
        start_date=_parse_date(row["start_date"]),
        end_date=_parse_date(row["end_date"]),
        day_of_month=row["day_of_month"],
        next_occurrence=_parse_date(row["next_occurrence"]),
        auto_record=bool(row["auto_record"]),
        notes=row["notes"] or "",
        vendor_id=row["vendor_id"],
    )


def list_expenses(
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[Iterable[str]] = None,
    vendor_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[Expense]:
    conditions = []
    params: List[object] = []

    if start_date:
        conditions.append("expense_date >= ?")
        params.append(start_date.isoformat())
    if end_date:
        conditions.append("expense_date <= ?")
        params.append(end_date.isoformat())
    if categories:
        placeholders = ",".join("?" for _ in categories)
        conditions.append(f"category IN ({placeholders})")
        params.extend(list(categories))
    if vendor_id:
        conditions.append("vendor_id = ?")
        params.append(int(vendor_id))

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    limit_clause = ""
    if limit:
        limit_clause = f"LIMIT {int(limit)}"

    query = f"""
        SELECT
            id,
            category,
            amount,
            expense_date,
            description,
            payment_method,
            vendor_id,
            material_id,
            is_recurring,
            recurring_id,
            document_id,
            tags,
            notes
        FROM expenses
        {where_clause}
        ORDER BY expense_date DESC, id DESC
        {limit_clause}
    """

    with create_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    return [_row_to_expense(row) for row in rows]


def get_expense(expense_id: int) -> Optional[Expense]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                category,
                amount,
                expense_date,
                description,
                payment_method,
                vendor_id,
                material_id,
                is_recurring,
                recurring_id,
                document_id,
                tags,
                notes
            FROM expenses
            WHERE id = ?
            LIMIT 1
            """,
            (int(expense_id),),
        ).fetchone()

    if row is None:
        return None
    return _row_to_expense(row)


def save_expense(expense: Expense) -> int:
    tags_json = json.dumps(expense.tags or [])
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if expense.id:
                cursor.execute(
                    """
                    UPDATE expenses
                    SET
                        category = ?,
                        amount = ?,
                        expense_date = ?,
                        description = ?,
                        payment_method = ?,
                        vendor_id = ?,
                        material_id = ?,
                        is_recurring = ?,
                        recurring_id = ?,
                        document_id = ?,
                        tags = ?,
                        notes = ?
                    WHERE id = ?
                    """,
                    (
                        expense.category.strip(),
                        float(expense.amount),
                        expense.expense_date.isoformat(),
                        expense.description.strip(),
                        expense.payment_method.strip(),
                        expense.vendor_id,
                        expense.material_id,
                        int(bool(expense.is_recurring)),
                        expense.recurring_id,
                        expense.document_id,
                        tags_json,
                        expense.notes.strip(),
                        int(expense.id),
                    ),
                )
                expense_id = int(expense.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO expenses (
                        category,
                        amount,
                        expense_date,
                        description,
                        payment_method,
                        vendor_id,
                        material_id,
                        is_recurring,
                        recurring_id,
                        document_id,
                        tags,
                        notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        expense.category.strip(),
                        float(expense.amount),
                        expense.expense_date.isoformat(),
                        expense.description.strip(),
                        expense.payment_method.strip(),
                        expense.vendor_id,
                        expense.material_id,
                        int(bool(expense.is_recurring)),
                        expense.recurring_id,
                        expense.document_id,
                        tags_json,
                        expense.notes.strip(),
                    ),
                )
                expense_id = int(cursor.lastrowid)
            connection.commit()
            return expense_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_expense(expense_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))
        connection.commit()


def list_categories(*, include_recurring: bool = True) -> List[str]:
    categories: set[str] = set()
    with create_connection() as connection:
        expense_rows = connection.execute(
            "SELECT DISTINCT category FROM expenses WHERE category <> ''"
        ).fetchall()
        categories.update(row["category"] for row in expense_rows if row["category"])
        if include_recurring:
            recurring_rows = connection.execute(
                "SELECT DISTINCT category FROM recurring_expenses WHERE category <> ''"
            ).fetchall()
            categories.update(row["category"] for row in recurring_rows if row["category"])
    return sorted(categories, key=lambda value: value.casefold())


def list_recurring_expenses() -> List[RecurringExpense]:
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                category,
                amount,
                frequency,
                start_date,
                end_date,
                day_of_month,
                next_occurrence,
                auto_record,
                notes,
                vendor_id
            FROM recurring_expenses
            ORDER BY start_date DESC, id DESC
            """
        ).fetchall()

    return [_row_to_recurring(row) for row in rows]


def get_recurring_expense(recurring_id: int) -> Optional[RecurringExpense]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                category,
                amount,
                frequency,
                start_date,
                end_date,
                day_of_month,
                next_occurrence,
                auto_record,
                notes,
                vendor_id
            FROM recurring_expenses
            WHERE id = ?
            LIMIT 1
            """,
            (int(recurring_id),),
        ).fetchone()

    if row is None:
        return None
    return _row_to_recurring(row)


def save_recurring_expense(recurring: RecurringExpense) -> int:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if recurring.id:
                cursor.execute(
                    """
                    UPDATE recurring_expenses
                    SET
                        category = ?,
                        amount = ?,
                        frequency = ?,
                        start_date = ?,
                        end_date = ?,
                        day_of_month = ?,
                        next_occurrence = ?,
                        auto_record = ?,
                        notes = ?,
                        vendor_id = ?
                    WHERE id = ?
                    """,
                    (
                        recurring.category.strip(),
                        float(recurring.amount),
                        recurring.frequency.strip(),
                        recurring.start_date.isoformat() if recurring.start_date else None,
                        recurring.end_date.isoformat() if recurring.end_date else None,
                        recurring.day_of_month,
                        recurring.next_occurrence.isoformat() if recurring.next_occurrence else None,
                        int(bool(recurring.auto_record)),
                        recurring.notes.strip(),
                        recurring.vendor_id,
                        int(recurring.id),
                    ),
                )
                recurring_id = int(recurring.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO recurring_expenses (
                        category,
                        amount,
                        frequency,
                        start_date,
                        end_date,
                        day_of_month,
                        next_occurrence,
                        auto_record,
                        notes,
                        vendor_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recurring.category.strip(),
                        float(recurring.amount),
                        recurring.frequency.strip(),
                        recurring.start_date.isoformat() if recurring.start_date else None,
                        recurring.end_date.isoformat() if recurring.end_date else None,
                        recurring.day_of_month,
                        recurring.next_occurrence.isoformat() if recurring.next_occurrence else None,
                        int(bool(recurring.auto_record)),
                        recurring.notes.strip(),
                        recurring.vendor_id,
                    ),
                )
                recurring_id = int(cursor.lastrowid)
            connection.commit()
            return recurring_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_recurring_expense(recurring_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM recurring_expenses WHERE id = ?", (int(recurring_id),))
        connection.commit()
