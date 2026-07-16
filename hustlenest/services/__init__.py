"""Service layer package for HustleNest.

Submodules are exposed as attributes so that
``from ..services import cloud_sync_service`` style imports work
both during normal execution and within a PyInstaller bundle.
"""

# Import submodules as attributes of the package.
# This allows `from ..services import xyz` to resolve xyz as a module.
from . import (
    cloud_sync_service,
    crm_service,
    document_service,
    expense_service,
    finance_service,
    goal_service,
    inventory_service,
    loss_service,
    material_service,
    order_service,
    vendor_service,
)

__all__ = [
    "cloud_sync_service",
    "crm_service",
    "document_service",
    "expense_service",
    "finance_service",
    "goal_service",
    "inventory_service",
    "loss_service",
    "material_service",
    "order_service",
    "vendor_service",
]
