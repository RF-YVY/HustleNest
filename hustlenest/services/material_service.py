from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..data import material_repository
from ..models.order_models import Material, MaterialTransaction


def list_materials(*, include_archived: bool = False) -> List[Material]:
    return material_repository.list_materials(include_archived=include_archived)


def get_material(material_id: int) -> Optional[Material]:
    return material_repository.get_material(material_id)


def save_material(material: Material) -> int:
    return material_repository.save_material(material)


def archive_material(material_id: int, archived: bool) -> None:
    material_repository.set_material_archived(material_id, archived)


def delete_material(material_id: int) -> None:
    material_repository.delete_material(material_id)


def record_adjustment(
    material_id: int,
    quantity_delta: float,
    *,
    unit_cost: float = 0.0,
    reason: str = "Manual adjustment",
    reference_type: str = "manual",
    reference_id: Optional[int] = None,
    created_by: str = "",
    notes: str = "",
) -> None:
    material_repository.apply_material_delta(
        material_id,
        quantity_delta,
        unit_cost=unit_cost,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by=created_by,
        notes=notes,
    )


def list_transactions(material_id: int, *, limit: int = 100) -> List[MaterialTransaction]:
    return material_repository.fetch_transactions(material_id, limit=limit)


def log_transaction(transaction: MaterialTransaction) -> int:
    record = transaction
    if record.transaction_date is None:
        record = MaterialTransaction(
            id=transaction.id,
            material_id=transaction.material_id,
            transaction_date=datetime.utcnow(),
            quantity_delta=transaction.quantity_delta,
            unit_cost=transaction.unit_cost,
            reason=transaction.reason,
            reference_type=transaction.reference_type,
            reference_id=transaction.reference_id,
            created_by=transaction.created_by,
            notes=transaction.notes,
        )
    return material_repository.record_transaction(record)


def list_categories() -> List[str]:
    return material_repository.list_categories()
