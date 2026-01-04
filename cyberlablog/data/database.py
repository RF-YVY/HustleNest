from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterator


_DB_FILE = "hustlenest.db"


def _get_storage_directory() -> Path:
    base = Path(os.getenv("LOCALAPPDATA", Path.home()))
    target = base / "HustleNest"
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_database_path() -> Path:
    return _get_storage_directory() / _DB_FILE


def create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    _apply_pragmas(connection)
    return connection


def _apply_pragmas(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.close()


def initialize() -> None:
    with create_connection() as connection:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                photo_path TEXT NOT NULL DEFAULT '',
                inventory_count INTEGER NOT NULL DEFAULT 0,
                is_complete INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Ordered'
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                customer_address TEXT NOT NULL,
                order_date TEXT NOT NULL,
                ship_date TEXT,
                status TEXT NOT NULL,
                carrier TEXT NOT NULL DEFAULT '',
                tracking_number TEXT NOT NULL DEFAULT '',
                total_amount REAL NOT NULL DEFAULT 0,
                target_completion_date TEXT
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER,
                product_sku TEXT NOT NULL DEFAULT '',
                product_name TEXT NOT NULL,
                product_description TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_order_items_order_id
            ON order_items(order_id);

            CREATE TABLE IF NOT EXISTS order_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                order_number TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                amount_delta REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_order_history_order_number
            ON order_history(order_number);

            CREATE INDEX IF NOT EXISTS idx_order_history_created_at
            ON order_history(created_at);
            """
        )

        _ensure_column(connection, "order_items", "product_sku", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "order_items", "product_id", "INTEGER")
        _ensure_column(connection, "orders", "carrier", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "orders", "tracking_number", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "products", "status", "TEXT NOT NULL DEFAULT 'Ordered'")
        _ensure_column(connection, "orders", "target_completion_date", "TEXT")

        cursor.close()
        connection.commit()


def iter_rows(sql: str, *params: object) -> Iterator[sqlite3.Row]:
    with create_connection() as connection:
        cursor = connection.execute(sql, params)
        try:
            for row in cursor:
                yield row
        finally:
            cursor.close()


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    info = connection.execute(f"PRAGMA table_info({table});").fetchall()
    if not any(row[1] == column for row in info):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")
