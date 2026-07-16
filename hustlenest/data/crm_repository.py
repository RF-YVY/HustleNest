from __future__ import annotations

import json
from datetime import date, datetime
from typing import Iterable, List, Optional

from ..models.order_models import CRMContact, CRMInteraction
from .database import create_connection

_DATE_FORMAT = "%Y-%m-%d"
_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, _DATE_FORMAT).date()
    except ValueError:
        return datetime.fromisoformat(value).date()


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _row_to_contact(row) -> CRMContact:
    tags_value = row["tags"] or "[]"
    try:
        tags = json.loads(tags_value)
    except json.JSONDecodeError:
        tags = []
    return CRMContact(
        id=int(row["id"]),
        customer_name=row["customer_name"],
        company=row["company"] or "",
        email=row["email"] or "",
        phone=row["phone"] or "",
        address=row["address"] or "",
        tags=tags,
        created_at=_parse_datetime(row["created_at"]) if "created_at" in row.keys() else None,
        last_contacted=_parse_date(row["last_contacted"]),
        next_follow_up=_parse_date(row["next_follow_up"]),
        preferred_channel=row["preferred_channel"] or "",
        notes=row["notes"] or "",
    )


def _row_to_interaction(row) -> CRMInteraction:
    return CRMInteraction(
        id=int(row["id"]),
        contact_id=int(row["contact_id"]),
        interaction_date=_parse_datetime(row["interaction_date"]),
        channel=row["channel"] or "",
        summary=row["summary"] or "",
        follow_up_date=_parse_date(row["follow_up_date"]),
        follow_up_action=row["follow_up_action"] or "",
        order_id=row["order_id"],
    )


def list_contacts(*, tags: Optional[Iterable[str]] = None) -> List[CRMContact]:
    params: List[object] = []
    where_clause = ""
    if tags:
        placeholders = " OR ".join("tags LIKE ?" for _ in tags)
        params.extend([f"%{tag}%" for tag in tags])
        where_clause = f"WHERE {placeholders}"

    query = f"""
        SELECT
            id,
            customer_name,
            company,
            email,
            phone,
            address,
            tags,
            created_at,
            last_contacted,
            next_follow_up,
            preferred_channel,
            notes
        FROM crm_contacts
        {where_clause}
        ORDER BY COALESCE(next_follow_up, last_contacted) DESC, UPPER(customer_name)
    """

    with create_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    return [_row_to_contact(row) for row in rows]


def get_contact(contact_id: int) -> Optional[CRMContact]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                customer_name,
                company,
                email,
                phone,
                address,
                tags,
                created_at,
                last_contacted,
                next_follow_up,
                preferred_channel,
                notes
            FROM crm_contacts
            WHERE id = ?
            LIMIT 1
            """,
            (int(contact_id),),
        ).fetchone()

    if row is None:
        return None
    return _row_to_contact(row)


def save_contact(contact: CRMContact) -> int:
    tags_json = json.dumps(contact.tags or [])
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if contact.id:
                cursor.execute(
                    """
                    UPDATE crm_contacts
                    SET
                        customer_name = ?,
                        company = ?,
                        email = ?,
                        phone = ?,
                        address = ?,
                        tags = ?,
                        last_contacted = ?,
                        next_follow_up = ?,
                        preferred_channel = ?,
                        notes = ?
                    WHERE id = ?
                    """,
                    (
                        contact.customer_name.strip(),
                        contact.company.strip(),
                        contact.email.strip(),
                        contact.phone.strip(),
                        contact.address.strip(),
                        tags_json,
                        contact.last_contacted.isoformat() if contact.last_contacted else None,
                        contact.next_follow_up.isoformat() if contact.next_follow_up else None,
                        contact.preferred_channel.strip(),
                        contact.notes.strip(),
                        int(contact.id),
                    ),
                )
                contact_id = int(contact.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO crm_contacts (
                        customer_name,
                        company,
                        email,
                        phone,
                        address,
                        tags,
                        last_contacted,
                        next_follow_up,
                        preferred_channel,
                        notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        contact.customer_name.strip(),
                        contact.company.strip(),
                        contact.email.strip(),
                        contact.phone.strip(),
                        contact.address.strip(),
                        tags_json,
                        contact.last_contacted.isoformat() if contact.last_contacted else None,
                        contact.next_follow_up.isoformat() if contact.next_follow_up else None,
                        contact.preferred_channel.strip(),
                        contact.notes.strip(),
                    ),
                )
                contact_id = int(cursor.lastrowid)
            connection.commit()
            return contact_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_contact(contact_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM crm_contacts WHERE id = ?", (int(contact_id),))
        connection.commit()


def list_interactions(contact_id: int, *, limit: Optional[int] = None) -> List[CRMInteraction]:
    limit_clause = ""
    if limit:
        limit_clause = f"LIMIT {int(limit)}"

    query = f"""
        SELECT
            id,
            contact_id,
            interaction_date,
            channel,
            summary,
            follow_up_date,
            follow_up_action,
            order_id
        FROM crm_interactions
        WHERE contact_id = ?
        ORDER BY interaction_date DESC, id DESC
        {limit_clause}
    """

    with create_connection() as connection:
        rows = connection.execute(query, (int(contact_id),)).fetchall()

    return [_row_to_interaction(row) for row in rows]


def save_interaction(interaction: CRMInteraction) -> int:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if interaction.id:
                cursor.execute(
                    """
                    UPDATE crm_interactions
                    SET
                        contact_id = ?,
                        interaction_date = ?,
                        channel = ?,
                        summary = ?,
                        follow_up_date = ?,
                        follow_up_action = ?,
                        order_id = ?
                    WHERE id = ?
                    """,
                    (
                        int(interaction.contact_id),
                        interaction.interaction_date.isoformat(timespec="seconds"),
                        interaction.channel.strip(),
                        interaction.summary.strip(),
                        interaction.follow_up_date.isoformat() if interaction.follow_up_date else None,
                        interaction.follow_up_action.strip(),
                        interaction.order_id,
                        int(interaction.id),
                    ),
                )
                interaction_id = int(interaction.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO crm_interactions (
                        contact_id,
                        interaction_date,
                        channel,
                        summary,
                        follow_up_date,
                        follow_up_action,
                        order_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(interaction.contact_id),
                        interaction.interaction_date.isoformat(timespec="seconds"),
                        interaction.channel.strip(),
                        interaction.summary.strip(),
                        interaction.follow_up_date.isoformat() if interaction.follow_up_date else None,
                        interaction.follow_up_action.strip(),
                        interaction.order_id,
                    ),
                )
                interaction_id = int(cursor.lastrowid)
            connection.commit()
            return interaction_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_interaction(interaction_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM crm_interactions WHERE id = ?", (int(interaction_id),))
        connection.commit()
