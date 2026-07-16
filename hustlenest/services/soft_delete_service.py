"""Soft delete service for orders and products with restore functionality."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional, Tuple

from ..data.database import create_connection


@dataclass
class DeletedItem:
    """Represents a soft-deleted item."""
    id: int
    item_type: Literal["order", "product"]
    name: str
    deleted_at: datetime
    details: str = ""


def soft_delete_order(order_id: int) -> bool:
    """
    Mark an order as deleted (soft delete).
    Returns True if successful.
    """
    now = datetime.now().isoformat()
    with create_connection() as conn:
        cursor = conn.execute(
            "UPDATE orders SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, order_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def soft_delete_product(product_id: int) -> bool:
    """
    Mark a product as deleted (soft delete).
    Returns True if successful.
    """
    now = datetime.now().isoformat()
    with create_connection() as conn:
        cursor = conn.execute(
            "UPDATE products SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, product_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def restore_order(order_id: int) -> bool:
    """
    Restore a soft-deleted order.
    Returns True if successful.
    """
    with create_connection() as conn:
        cursor = conn.execute(
            "UPDATE orders SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
            (order_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def restore_product(product_id: int) -> bool:
    """
    Restore a soft-deleted product.
    Returns True if successful.
    """
    with create_connection() as conn:
        cursor = conn.execute(
            "UPDATE products SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
            (product_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def permanent_delete_order(order_id: int) -> bool:
    """
    Permanently delete a soft-deleted order.
    Only works on already soft-deleted items.
    Returns True if successful.
    """
    with create_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM orders WHERE id = ? AND deleted_at IS NOT NULL",
            (order_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def permanent_delete_product(product_id: int) -> bool:
    """
    Permanently delete a soft-deleted product.
    Only works on already soft-deleted items.
    Returns True if successful.
    """
    with create_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM products WHERE id = ? AND deleted_at IS NOT NULL",
            (product_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def list_deleted_orders() -> List[DeletedItem]:
    """
    List all soft-deleted orders.
    """
    items: List[DeletedItem] = []
    with create_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, order_number, customer_name, order_date, deleted_at
            FROM orders
            WHERE deleted_at IS NOT NULL
            ORDER BY deleted_at DESC
            """
        ).fetchall()
        
        for row in rows:
            deleted_at = datetime.fromisoformat(row["deleted_at"])
            items.append(DeletedItem(
                id=row["id"],
                item_type="order",
                name=row["order_number"],
                deleted_at=deleted_at,
                details=f"Customer: {row['customer_name']}, Date: {row['order_date']}",
            ))
    
    return items


def list_deleted_products() -> List[DeletedItem]:
    """
    List all soft-deleted products.
    """
    items: List[DeletedItem] = []
    with create_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, sku, name, deleted_at
            FROM products
            WHERE deleted_at IS NOT NULL
            ORDER BY deleted_at DESC
            """
        ).fetchall()
        
        for row in rows:
            deleted_at = datetime.fromisoformat(row["deleted_at"])
            items.append(DeletedItem(
                id=row["id"],
                item_type="product",
                name=row["sku"],
                deleted_at=deleted_at,
                details=row["name"],
            ))
    
    return items


def list_all_deleted_items() -> List[DeletedItem]:
    """
    List all soft-deleted items (orders and products).
    """
    items = list_deleted_orders() + list_deleted_products()
    items.sort(key=lambda x: x.deleted_at, reverse=True)
    return items


def empty_trash() -> Tuple[int, int]:
    """
    Permanently delete all soft-deleted items.
    Returns (orders_deleted, products_deleted).
    """
    with create_connection() as conn:
        orders_cursor = conn.execute("DELETE FROM orders WHERE deleted_at IS NOT NULL")
        orders_count = orders_cursor.rowcount
        
        products_cursor = conn.execute("DELETE FROM products WHERE deleted_at IS NOT NULL")
        products_count = products_cursor.rowcount
        
        conn.commit()
    
    return orders_count, products_count


def get_deleted_count() -> int:
    """
    Get total count of soft-deleted items.
    """
    with create_connection() as conn:
        row = conn.execute(
            """
            SELECT 
                (SELECT COUNT(*) FROM orders WHERE deleted_at IS NOT NULL) +
                (SELECT COUNT(*) FROM products WHERE deleted_at IS NOT NULL) AS total
            """
        ).fetchone()
        return row["total"] if row else 0
