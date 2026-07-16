from __future__ import annotations

from typing import Iterable, List, Optional

from ..data import document_repository
from ..models.order_models import DocumentRecord


def list_documents(
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    categories: Optional[Iterable[str]] = None,
) -> List[DocumentRecord]:
    return document_repository.list_documents(
        entity_type=entity_type,
        entity_id=entity_id,
        categories=categories,
    )


def get_document(document_id: int) -> Optional[DocumentRecord]:
    return document_repository.get_document(document_id)


def save_document(document: DocumentRecord) -> int:
    return document_repository.save_document(document)


def delete_document(document_id: int) -> None:
    document_repository.delete_document(document_id)
