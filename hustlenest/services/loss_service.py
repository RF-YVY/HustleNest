from __future__ import annotations

from typing import List, Optional

from ..data import loss_repository, material_repository, product_repository
from ..models.order_models import LossRecord


def list_losses(*, limit: Optional[int] = None) -> List[LossRecord]:
    return loss_repository.fetch_losses(limit=limit)


def get_loss(loss_id: int) -> Optional[LossRecord]:
    return loss_repository.get_loss(loss_id)


def save_loss(record: LossRecord) -> int:
    if record.id:
        existing = loss_repository.get_loss(record.id)
        if existing:
            _reverse_inventory_effect(existing)
        loss_repository.update_loss(record.id, record)
        updated = loss_repository.get_loss(record.id)
        if updated:
            _apply_inventory_effect(updated)
        return int(record.id)
    loss_id = loss_repository.create_loss(record)
    created = loss_repository.get_loss(loss_id)
    if created:
        _apply_inventory_effect(created)
    return loss_id


def delete_loss(loss_id: int) -> None:
    existing = loss_repository.get_loss(loss_id)
    if existing:
        _reverse_inventory_effect(existing)
    loss_repository.delete_loss(loss_id)


def list_categories() -> List[str]:
    return loss_repository.list_categories()


def _apply_inventory_effect(record: LossRecord) -> None:
    quantity = float(record.quantity or 0.0)
    if quantity <= 0:
        return
    if record.is_product_loss and record.product_id:
        _adjust_product_inventory(record.product_id, -quantity)
    if record.material_id:
        material_repository.apply_material_delta(
            int(record.material_id),
            -quantity,
            reason=f"Loss: {record.category}",
            reference_type="loss",
            reference_id=record.id,
            created_by=record.recorded_by,
            notes=record.description,
        )


def _reverse_inventory_effect(record: LossRecord) -> None:
    quantity = float(record.quantity or 0.0)
    if quantity <= 0:
        return
    if record.is_product_loss and record.product_id:
        _adjust_product_inventory(record.product_id, quantity)
    if record.material_id:
        material_repository.apply_material_delta(
            int(record.material_id),
            quantity,
            reason=f"Loss reversal: {record.category}",
            reference_type="loss",
            reference_id=record.id,
            created_by=record.recorded_by,
            notes=record.details,
        )


def _adjust_product_inventory(product_id: int, quantity_delta: float) -> None:
    product = product_repository.get_product_by_id(product_id)
    if product is None:
        return
    delta = int(round(quantity_delta))
    if delta == 0:
        return
    product_repository.adjust_inventory(product.sku, delta)
