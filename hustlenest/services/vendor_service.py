from __future__ import annotations

from typing import List, Optional

from ..data import vendor_repository
from ..models.order_models import Vendor


def list_vendors() -> List[Vendor]:
    return vendor_repository.list_vendors()


def get_vendor(vendor_id: int) -> Optional[Vendor]:
    return vendor_repository.get_vendor(vendor_id)


def save_vendor(vendor: Vendor) -> int:
    return vendor_repository.save_vendor(vendor)


def delete_vendor(vendor_id: int) -> None:
    vendor_repository.delete_vendor(vendor_id)


def ensure_vendor(name: str) -> Vendor:
    normalized = name.strip()
    if not normalized:
        raise ValueError("Vendor name is required")
    for vendor in list_vendors():
        if vendor.name.lower() == normalized.lower():
            return vendor
    vendor = Vendor(id=None, name=normalized)
    vendor_id = save_vendor(vendor)
    vendor.id = vendor_id
    return vendor
