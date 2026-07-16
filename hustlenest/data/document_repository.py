from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable, List, Optional

from ..models.order_models import DocumentRecord
from .database import create_connection


def _row_to_document(row) -> DocumentRecord:
    tags_value = row["tags"] or "[]"
    try:
        tags = json.loads(tags_value)
    except json.JSONDecodeError:
        tags = []
    created_at_value = row["created_at"] if "created_at" in row.keys() else None
    created_at = datetime.fromisoformat(created_at_value) if created_at_value else None
    return DocumentRecord(
        id=int(row["id"]),
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        file_path=row["file_path"],
        category=row["category"] or "",
        description=row["description"] or "",
        tags=tags,
        stored_at=row["stored_at"] or "",
        checksum=row["checksum"] or "",
        created_at=created_at,
    )


def list_documents(
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    categories: Optional[Iterable[str]] = None,
) -> List[DocumentRecord]:
    conditions = []
    params: List[object] = []

    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type.strip())
    if entity_id is not None:
        conditions.append("entity_id = ?")
        params.append(int(entity_id))
    if categories:
        placeholders = ",".join("?" for _ in categories)
        conditions.append(f"category IN ({placeholders})")
        params.extend(list(categories))

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            id,
            entity_type,
            entity_id,
            file_path,
            category,
            description,
            tags,
            stored_at,
            checksum,
            created_at
        FROM documents
        {where_clause}
        ORDER BY created_at DESC, id DESC
    """

    with create_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    return [_row_to_document(row) for row in rows]


def get_document(document_id: int) -> Optional[DocumentRecord]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                entity_type,
                entity_id,
                file_path,
                category,
                description,
                tags,
                stored_at,
                checksum,
                created_at
            FROM documents
            WHERE id = ?
            LIMIT 1
            """,
            (int(document_id),),
        ).fetchone()

    if row is None:
        return None
    return _row_to_document(row)


def save_document(document: DocumentRecord) -> int:
    tags_json = json.dumps(document.tags or [])
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if document.id:
                cursor.execute(
                    """
                    UPDATE documents
                    SET
                        entity_type = ?,
                        entity_id = ?,
                        file_path = ?,
                        category = ?,
                        description = ?,
                        tags = ?,
                        stored_at = ?,
                        checksum = ?
                    WHERE id = ?
                    """,
                    (
                        document.entity_type.strip(),
                        document.entity_id,
                        document.file_path.strip(),
                        document.category.strip(),
                        document.description.strip(),
                        tags_json,
                        document.stored_at.strip(),
                        document.checksum.strip(),
                        int(document.id),
                    ),
                )
                document_id = int(document.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO documents (
                        entity_type,
                        entity_id,
                        file_path,
                        category,
                        description,
                        tags,
                        stored_at,
                        checksum,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document.entity_type.strip(),
                        document.entity_id,
                        document.file_path.strip(),
                        document.category.strip(),
                        document.description.strip(),
                        tags_json,
                        document.stored_at.strip(),
                        document.checksum.strip(),
                        datetime.utcnow().isoformat(timespec="seconds"),
                    ),
                )
                document_id = int(cursor.lastrowid)
            connection.commit()
            return document_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_document(document_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM documents WHERE id = ?", (int(document_id),))
        connection.commit()
