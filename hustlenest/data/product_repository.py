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
            WHERE deleted_at IS NULL
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
            WHERE sku = ? AND deleted_at IS NULL
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


def create_product_with_materials(product: Product, links: list[tuple[int, float, bool]]) -> Product:
    sku = product.sku.strip().upper()
    if not sku:
        raise ValueError("SKU is required")
    try:
        with create_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO products (
                    sku, name, description, photo_path, inventory_count, is_complete,
                    status, base_unit_cost, default_unit_price, pricing_components
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _product_values(product),
            )
            product_id = int(cursor.lastrowid)
            _replace_product_materials(connection, product_id, links)
            connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"SKU '{sku}' already exists.") from exc
    saved = get_product_by_id(product_id)
    assert saved is not None
    return saved


def update_product_with_materials(product: Product, links: list[tuple[int, float, bool]]) -> Product:
    if product.id is None:
        raise ValueError("Product ID is required for update")
    sku = product.sku.strip().upper()
    if not sku:
        raise ValueError("SKU is required")
    try:
        with create_connection() as connection:
            connection.execute(
                """
                UPDATE products
                SET sku = ?, name = ?, description = ?, photo_path = ?, inventory_count = ?,
                    is_complete = ?, status = ?, base_unit_cost = ?, default_unit_price = ?,
                    pricing_components = ?
                WHERE id = ?
                """,
                (*_product_values(product), int(product.id)),
            )
            _replace_product_materials(connection, int(product.id), links)
            connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"SKU '{sku}' already exists.") from exc
    saved = get_product_by_id(product.id)
    assert saved is not None
    return saved


def list_product_materials(product_id: int) -> list[dict[str, object]]:
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                m.id AS material_id,
                m.sku,
                m.name,
                m.unit_of_measure,
                m.cost_per_unit,
                pm.quantity_required,
                pm.include_in_unit_cost
            FROM product_materials AS pm
            JOIN materials AS m ON m.id = pm.material_id
            WHERE pm.product_id = ? AND m.archived = 0
            ORDER BY UPPER(m.name)
            """,
            (int(product_id),),
        ).fetchall()
    return [
        {
            "material_id": int(row["material_id"]),
            "sku": row["sku"],
            "name": row["name"],
            "unit_of_measure": row["unit_of_measure"] or "",
            "cost_per_unit": float(row["cost_per_unit"] or 0),
            "quantity_required": float(row["quantity_required"] or 0),
            "include_in_unit_cost": bool(row["include_in_unit_cost"]),
        }
        for row in rows
    ]


def list_material_products(material_id: int) -> list[dict[str, object]]:
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT p.id AS product_id, p.sku, p.name, pm.quantity_required, pm.include_in_unit_cost
            FROM product_materials AS pm
            JOIN products AS p ON p.id = pm.product_id
            WHERE pm.material_id = ? AND p.deleted_at IS NULL
            ORDER BY UPPER(p.name)
            """,
            (int(material_id),),
        ).fetchall()
    return [
        {
            "product_id": int(row["product_id"]),
            "sku": row["sku"],
            "name": row["name"],
            "quantity_required": float(row["quantity_required"] or 0),
            "include_in_unit_cost": bool(row["include_in_unit_cost"]),
        }
        for row in rows
    ]


def replace_product_materials(product_id: int, links: list[tuple[int, float, bool]]) -> None:
    with create_connection() as connection:
        _replace_product_materials(connection, product_id, links)
        connection.commit()


def product_material_cost(product_id: int) -> float:
    return sum(
        float(item["cost_per_unit"]) * float(item["quantity_required"])
        for item in list_product_materials(product_id)
        if bool(item["include_in_unit_cost"])
    )


def product_material_cost_components(product_id: int) -> List[CostComponent]:
    return [
        CostComponent(
            label=f"Material: {item['name']}",
            amount=float(item["cost_per_unit"]) * float(item["quantity_required"]),
        )
        for item in list_product_materials(product_id)
        if bool(item["include_in_unit_cost"])
    ]


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


def _product_values(product: Product) -> tuple[object, ...]:
    sku = product.sku.strip().upper()
    return (
        sku,
        product.name.strip() or sku,
        (product.description or "").strip(),
        (product.photo_path or "").strip(),
        max(0, int(product.inventory_count)),
        int(product.is_complete),
        (product.status or "Ordered").strip() or "Ordered",
        float(product.base_unit_cost),
        float(product.default_unit_price),
        _serialize_components(product.pricing_components),
    )


def _replace_product_materials(connection: sqlite3.Connection, product_id: int, links: list[tuple[int, float, bool]]) -> None:
    connection.execute("DELETE FROM product_materials WHERE product_id = ?", (int(product_id),))
    connection.executemany(
        "INSERT INTO product_materials (product_id, material_id, quantity_required, include_in_unit_cost) VALUES (?, ?, ?, ?)",
        [(int(product_id), int(material_id), float(quantity), int(include_in_unit_cost)) for material_id, quantity, include_in_unit_cost in links],
    )
