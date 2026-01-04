from __future__ import annotations

from typing import List, Optional

from ..models.order_models import Product
from .database import create_connection


def list_products() -> List[Product]:
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, sku, name, description, photo_path, inventory_count, is_complete, status
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
            SELECT id, sku, name, description, photo_path, inventory_count, is_complete, status
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
    )


def create_product(sku: str, name: str, *, mark_complete: bool = False) -> Product:
    sku = sku.strip().upper()
    if not sku:
        raise ValueError("SKU is required")

    with create_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO products (sku, name, is_complete, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET name = excluded.name
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

    with create_connection() as connection:
        connection.execute(
            """
            UPDATE products
            SET name = ?,
                description = ?,
                photo_path = ?,
                inventory_count = ?,
                is_complete = ?,
                status = ?
            WHERE id = ?
            """,
            (
                product.name.strip(),
                product.description.strip(),
                product.photo_path.strip(),
                max(0, int(product.inventory_count)),
                int(product.is_complete),
                product.status.strip() or "Ordered",
                int(product.id),
            ),
        )
        connection.commit()

    return get_product_by_id(product.id)


def get_product_by_id(product_id: int) -> Optional[Product]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT id, sku, name, description, photo_path, inventory_count, is_complete, status
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