from __future__ import annotations

from typing import List, Optional

from ..models.order_models import Vendor
from .database import create_connection


def list_vendors() -> List[Vendor]:
    query = """
        SELECT
            id,
            name,
            contact_name,
            email,
            phone,
            website,
            account_number,
            notes,
            preferred_payment_method
        FROM vendors
        ORDER BY UPPER(name)
    """
    with create_connection() as connection:
        rows = connection.execute(query).fetchall()

    vendors: List[Vendor] = []
    for row in rows:
        vendors.append(
            Vendor(
                id=int(row["id"]),
                name=row["name"],
                contact_name=row["contact_name"] or "",
                email=row["email"] or "",
                phone=row["phone"] or "",
                website=row["website"] or "",
                account_number=row["account_number"] or "",
                notes=row["notes"] or "",
                preferred_payment_method=row["preferred_payment_method"] or "",
            )
        )
    return vendors


def get_vendor(vendor_id: int) -> Optional[Vendor]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                name,
                contact_name,
                email,
                phone,
                website,
                account_number,
                notes,
                preferred_payment_method
            FROM vendors
            WHERE id = ?
            LIMIT 1
            """,
            (int(vendor_id),),
        ).fetchone()

    if row is None:
        return None

    return Vendor(
        id=int(row["id"]),
        name=row["name"],
        contact_name=row["contact_name"] or "",
        email=row["email"] or "",
        phone=row["phone"] or "",
        website=row["website"] or "",
        account_number=row["account_number"] or "",
        notes=row["notes"] or "",
        preferred_payment_method=row["preferred_payment_method"] or "",
    )


def save_vendor(vendor: Vendor) -> int:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if vendor.id:
                cursor.execute(
                    """
                    UPDATE vendors
                    SET
                        name = ?,
                        contact_name = ?,
                        email = ?,
                        phone = ?,
                        website = ?,
                        account_number = ?,
                        notes = ?,
                        preferred_payment_method = ?
                    WHERE id = ?
                    """,
                    (
                        vendor.name.strip(),
                        vendor.contact_name.strip(),
                        vendor.email.strip(),
                        vendor.phone.strip(),
                        vendor.website.strip(),
                        vendor.account_number.strip(),
                        vendor.notes.strip(),
                        vendor.preferred_payment_method.strip(),
                        int(vendor.id),
                    ),
                )
                vendor_id = int(vendor.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO vendors (
                        name,
                        contact_name,
                        email,
                        phone,
                        website,
                        account_number,
                        notes,
                        preferred_payment_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        vendor.name.strip(),
                        vendor.contact_name.strip(),
                        vendor.email.strip(),
                        vendor.phone.strip(),
                        vendor.website.strip(),
                        vendor.account_number.strip(),
                        vendor.notes.strip(),
                        vendor.preferred_payment_method.strip(),
                    ),
                )
                vendor_id = int(cursor.lastrowid)
            connection.commit()
            return vendor_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_vendor(vendor_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM vendors WHERE id = ?", (int(vendor_id),))
        connection.commit()


def search_vendors(term: str, *, limit: int = 20) -> List[Vendor]:
    pattern = f"%{term.strip()}%"
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                name,
                contact_name,
                email,
                phone,
                website,
                account_number,
                notes,
                preferred_payment_method
            FROM vendors
            WHERE name LIKE ? OR contact_name LIKE ?
            ORDER BY UPPER(name)
            LIMIT ?
            """,
            (pattern, pattern, int(limit)),
        ).fetchall()

    results: List[Vendor] = []
    for row in rows:
        results.append(
            Vendor(
                id=int(row["id"]),
                name=row["name"],
                contact_name=row["contact_name"] or "",
                email=row["email"] or "",
                phone=row["phone"] or "",
                website=row["website"] or "",
                account_number=row["account_number"] or "",
                notes=row["notes"] or "",
                preferred_payment_method=row["preferred_payment_method"] or "",
            )
        )
    return results
