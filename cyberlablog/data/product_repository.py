from __future__ import annotations

import sqlite3
import json
from typing import Iterable, List, Optional

from ..models.order_models import CostComponent, Product
from .database import create_connection


def list_products() -> List[Product]:
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                sku,
                name,
                description,
                photo_path,
                inventory_count,
                is_complete,
                status,
                base_unit_cost,
                default_unit_price,
                pricing_components
            FROM products
            ORDER BY sku ASC
            """
        ).fetchall()

    return [
        Product(
            id=int(row["id"]),
            sku=row["sku"],
            name=row["name"],
            description=row["description"],
            photo_path=row["photo_path"],
            inventory_count=int(row["inventory_count"]),
            is_complete=bool(row["is_complete"]),
            status=row["status"] or "Ordered",
            base_unit_cost=float(row["base_unit_cost"] or 0.0),
            default_unit_price=float(row["default_unit_price"] or 0.0),
            pricing_components=_deserialize_components(row["pricing_components"]),
        )
        for row in rows
    ]


def get_product_by_sku(sku: str) -> Optional[Product]:
    sku = sku.strip().upper()
    if not sku:
        return None

    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                sku,
                name,
                description,
                photo_path,
                inventory_count,
                is_complete,
                status,
                base_unit_cost,
                default_unit_price,
                pricing_components
            FROM products
            WHERE sku = ?
            """,
            (sku,),
        ).fetchone()

    if row is None:
        return None

    return Product(
        id=int(row["id"]),
        sku=row["sku"],
        name=row["name"],
        description=row["description"],
        photo_path=row["photo_path"],
        inventory_count=int(row["inventory_count"]),
        is_complete=bool(row["is_complete"]),
        status=row["status"] or "Ordered",
        base_unit_cost=float(row["base_unit_cost"] or 0.0),
        default_unit_price=float(row["default_unit_price"] or 0.0),
        pricing_components=_deserialize_components(row["pricing_components"]),
    )


def create_product(sku: str, name: str, *, mark_complete: bool = False) -> Product:
    sku = sku.strip().upper()
    if not sku:
        raise ValueError("SKU is required")

    with create_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO products (
                sku,
                name,
                is_complete,
                status,
                base_unit_cost,
                default_unit_price,
                pricing_components
            ) VALUES (?, ?, ?, ?, 0, 0, '[]')
            ON CONFLICT(sku) DO UPDATE SET
                name = excluded.name
            """,
            (sku, name.strip() or sku, int(mark_complete), "Ordered"),
        )
        product_id = cursor.lastrowid or cursor.execute(
            "SELECT id FROM products WHERE sku = ?", (sku,)
        ).fetchone()[0]
        connection.commit()
        cursor.close()

    return get_product_by_id(product_id)


def update_product(product: Product) -> Product:
    if product.id is None:
        raise ValueError("Product ID is required for update")

    sku = product.sku.strip().upper()
    if not sku:
        raise ValueError("SKU is required")

    try:
        description = (product.description or "").strip()
        photo_path = (product.photo_path or "").strip()
        status = (product.status or "Ordered").strip() or "Ordered"
        with create_connection() as connection:
            connection.execute(
                """
                UPDATE products
                SET sku = ?,
                    name = ?,
                    description = ?,
                    photo_path = ?,
                    inventory_count = ?,
                    is_complete = ?,
                    status = ?,
                    base_unit_cost = ?,
                    default_unit_price = ?,
                    pricing_components = ?
                WHERE id = ?
                """,
                (
                    sku,
                    product.name.strip() or sku,
                    description,
                    photo_path,
                    max(0, int(product.inventory_count)),
                    int(product.is_complete),
                    status,
                    float(product.base_unit_cost),
                    float(product.default_unit_price),
                    _serialize_components(product.pricing_components),
                    int(product.id),
                ),
            )
            connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"SKU '{sku}' already exists.") from exc

    return get_product_by_id(product.id)


def get_product_by_id(product_id: int) -> Optional[Product]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                sku,
                name,
                description,
                photo_path,
                inventory_count,
                is_complete,
                status,
                base_unit_cost,
                default_unit_price,
                pricing_components
            FROM products
            WHERE id = ?
            """,
            (int(product_id),),
        ).fetchone()

    if row is None:
        return None

    return Product(
        id=int(row["id"]),
        sku=row["sku"],
        name=row["name"],
        description=row["description"],
        photo_path=row["photo_path"],
        inventory_count=int(row["inventory_count"]),
        is_complete=bool(row["is_complete"]),
        status=row["status"] or "Ordered",
        base_unit_cost=float(row["base_unit_cost"] or 0.0),
        default_unit_price=float(row["default_unit_price"] or 0.0),
        pricing_components=_deserialize_components(row["pricing_components"]),
    )


def ensure_product(sku: str, name: str) -> Product:
    existing = get_product_by_sku(sku)
    if existing:
        return existing
    return create_product(sku, name, mark_complete=False)


def adjust_inventory(sku: str, delta: int) -> None:
    sku = sku.strip().upper()
    if not sku or delta == 0:
        return

    with create_connection() as connection:
        connection.execute(
            """
            UPDATE products
            SET inventory_count = MAX(0, inventory_count + ?)
            WHERE sku = ?
            """,
            (int(delta), sku),
        )
        connection.commit()


def upsert_inventory_info(sku: str, name: str, *, inventory: Optional[int] = None) -> Product:
    product = ensure_product(sku, name)
    if inventory is not None:
        with create_connection() as connection:
            connection.execute(
                "UPDATE products SET inventory_count = ? WHERE sku = ?",
                (max(0, int(inventory)), product.sku),
            )
            connection.commit()
        product = get_product_by_sku(product.sku) or product
    return product


def delete_product(product_id: int) -> None:
    if not product_id:
        return

    with create_connection() as connection:
        connection.execute("DELETE FROM products WHERE id = ?", (int(product_id),))
        connection.commit()


def _deserialize_components(raw: object) -> List[CostComponent]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    components: List[CostComponent] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label", "")).strip()
        amount = entry.get("amount", 0)
        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            amount_value = 0.0
        if not label and amount_value == 0.0:
            continue
        components.append(CostComponent(label=label, amount=amount_value))
    return components


def _serialize_components(components: Iterable[CostComponent]) -> str:
    payload = [
        {
            "label": component.label,
            "amount": float(component.amount),
        }
        for component in components
    ]
    return json.dumps(payload)