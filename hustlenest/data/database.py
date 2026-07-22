from __future__ import annotations

import gc
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterator, Optional


_DB_FILE = "hustlenest.db"


def _get_storage_directory() -> Path:
    base = Path(os.getenv("LOCALAPPDATA", Path.home()))
    target = base / "HustleNest"
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_database_path() -> Path:
    return _get_storage_directory() / _DB_FILE


def get_storage_root() -> Path:
    """Return the application data directory used for persistent assets."""
    return _get_storage_directory()


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


def close_database_for_replacement() -> Optional[str]:
    """
    Aggressively close all SQLite connections and release file handles.
    
    This function should be called before attempting to replace the database file.
    Returns an error message if the database could not be fully released, or None on success.
    """
    db_path = get_database_path()
    if not db_path.exists():
        return None
    
    # Force garbage collection to release any unreferenced connections
    gc.collect()
    
    # Try to checkpoint and close WAL mode
    try:
        # Use uri=True with immutable=0 to get a fresh connection
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        cursor = conn.cursor()
        try:
            # Checkpoint WAL to merge it into main database
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            # Switch to DELETE journal mode to remove WAL files
            cursor.execute("PRAGMA journal_mode=DELETE;")
        except sqlite3.Error:
            pass
        finally:
            cursor.close()
            conn.close()
    except sqlite3.Error as e:
        # If we can't connect, the file might already be locked
        pass
    
    # Force another garbage collection
    gc.collect()
    
    # Give Windows time to release handles
    time.sleep(0.1)
    
    # Try to remove WAL and SHM files
    for suffix in ("-wal", "-shm"):
        wal_path = db_path.with_name(db_path.name + suffix)
        if wal_path.exists():
            for _ in range(3):
                try:
                    wal_path.unlink()
                    break
                except OSError:
                    time.sleep(0.1)
    
    # Verify we can get exclusive access by trying to open with exclusive lock
    try:
        # Try opening in exclusive mode to verify no other locks
        test_conn = sqlite3.connect(str(db_path), timeout=1.0, isolation_level="EXCLUSIVE")
        test_conn.execute("BEGIN EXCLUSIVE")
        test_conn.rollback()
        test_conn.close()
    except sqlite3.Error as e:
        return f"Database appears to be locked: {e}"
    
    return None


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
                status TEXT NOT NULL DEFAULT 'Ordered',
                base_unit_cost REAL NOT NULL DEFAULT 0,
                default_unit_price REAL NOT NULL DEFAULT 0,
                pricing_components TEXT NOT NULL DEFAULT '[]'
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
                is_paid INTEGER NOT NULL DEFAULT 0,
                carrier TEXT NOT NULL DEFAULT '',
                tracking_number TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
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
                base_unit_cost REAL NOT NULL DEFAULT 0,
                cost_components TEXT NOT NULL DEFAULT '[]',
                applied_discount REAL NOT NULL DEFAULT 0,
                applied_tax REAL NOT NULL DEFAULT 0,
                price_adjustment_note TEXT NOT NULL DEFAULT '',
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

            CREATE TABLE IF NOT EXISTS order_workflow (
                order_id INTEGER PRIMARY KEY,
                record_type TEXT NOT NULL DEFAULT 'order',
                amount_paid REAL NOT NULL DEFAULT 0,
                deposit_required REAL NOT NULL DEFAULT 0,
                quote_expires TEXT,
                template_name TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                contact_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                website TEXT NOT NULL DEFAULT '',
                account_number TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                preferred_payment_method TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                unit_of_measure TEXT NOT NULL DEFAULT '',
                quantity_on_hand REAL NOT NULL DEFAULT 0,
                reorder_point REAL NOT NULL DEFAULT 0,
                cost_per_unit REAL NOT NULL DEFAULT 0,
                vendor_id INTEGER,
                last_restocked TEXT,
                notes TEXT NOT NULL DEFAULT '',
                lead_time_days INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(vendor_id) REFERENCES vendors(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_materials_vendor_id
            ON materials(vendor_id);

            CREATE TABLE IF NOT EXISTS material_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                transaction_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                quantity_delta REAL NOT NULL,
                unit_cost REAL NOT NULL DEFAULT 0,
                reason TEXT NOT NULL DEFAULT '',
                reference_type TEXT NOT NULL DEFAULT '',
                reference_id INTEGER,
                created_by TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_material_transactions_material_id
            ON material_transactions(material_id);

            CREATE TABLE IF NOT EXISTS product_materials (
                product_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                quantity_required REAL NOT NULL DEFAULT 1,
                include_in_unit_cost INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(product_id, material_id),
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_product_materials_material_id
            ON product_materials(material_id);

            CREATE TABLE IF NOT EXISTS losses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                order_item_id INTEGER,
                product_id INTEGER,
                material_id INTEGER,
                amount REAL NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT '',
                loss_date TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                details TEXT NOT NULL DEFAULT '',
                is_product_loss INTEGER NOT NULL DEFAULT 0,
                recorded_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE SET NULL,
                FOREIGN KEY(order_item_id) REFERENCES order_items(id) ON DELETE SET NULL,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL,
                FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_losses_loss_date
            ON losses(loss_date);

            CREATE INDEX IF NOT EXISTS idx_losses_order_id
            ON losses(order_id);

            CREATE INDEX IF NOT EXISTS idx_losses_category
            ON losses(category);

            CREATE TABLE IF NOT EXISTS recurring_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER,
                category TEXT NOT NULL DEFAULT '',
                amount REAL NOT NULL,
                frequency TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                day_of_month INTEGER,
                next_occurrence TEXT,
                auto_record INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(vendor_id) REFERENCES vendors(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER,
                material_id INTEGER,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                amount REAL NOT NULL,
                expense_date TEXT NOT NULL,
                payment_method TEXT NOT NULL DEFAULT '',
                is_recurring INTEGER NOT NULL DEFAULT 0,
                recurring_id INTEGER,
                document_id INTEGER,
                tags TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(vendor_id) REFERENCES vendors(id) ON DELETE SET NULL,
                FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE SET NULL,
                FOREIGN KEY(recurring_id) REFERENCES recurring_expenses(id) ON DELETE SET NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_expenses_expense_date
            ON expenses(expense_date);

            CREATE INDEX IF NOT EXISTS idx_expenses_vendor_id
            ON expenses(vendor_id);

            CREATE INDEX IF NOT EXISTS idx_expenses_category
            ON expenses(category);

            CREATE TABLE IF NOT EXISTS crm_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_contacted TEXT,
                next_follow_up TEXT,
                preferred_channel TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS crm_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                interaction_date TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                follow_up_date TEXT,
                follow_up_action TEXT NOT NULL DEFAULT '',
                order_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(contact_id) REFERENCES crm_contacts(id) ON DELETE CASCADE,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_crm_interactions_contact_id
            ON crm_interactions(contact_id);

            CREATE INDEX IF NOT EXISTS idx_crm_contacts_next_follow_up
            ON crm_contacts(next_follow_up);

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                file_path TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                stored_at TEXT NOT NULL DEFAULT '',
                checksum TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_documents_entity
            ON documents(entity_type, entity_id);

            CREATE INDEX IF NOT EXISTS idx_documents_category
            ON documents(category);

            CREATE TABLE IF NOT EXISTS business_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                target_value REAL NOT NULL,
                start_date TEXT,
                end_date TEXT,
                current_value REAL NOT NULL DEFAULT 0,
                owner TEXT NOT NULL DEFAULT '',
                progress_notes TEXT NOT NULL DEFAULT '',
                threshold_warning REAL NOT NULL DEFAULT 0,
                threshold_critical REAL NOT NULL DEFAULT 0,
                auto_calculate INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS goal_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                checkpoint_date TEXT NOT NULL,
                actual_value REAL NOT NULL,
                forecast_value REAL NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(goal_id) REFERENCES business_goals(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_goal_checkpoints_goal_id
            ON goal_checkpoints(goal_id);

            CREATE INDEX IF NOT EXISTS idx_business_goals_metric_type
            ON business_goals(metric_type);
            """
        )

        _ensure_column(connection, "order_items", "product_sku", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "order_items", "product_id", "INTEGER")
        _ensure_column(connection, "orders", "carrier", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "orders", "tracking_number", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "orders", "notes", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "products", "status", "TEXT NOT NULL DEFAULT 'Ordered'")
        _ensure_column(connection, "orders", "target_completion_date", "TEXT")
        _ensure_column(connection, "orders", "is_paid", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "orders", "tax_rate", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "orders", "tax_amount", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "orders", "tax_included_in_total", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "products", "base_unit_cost", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "products", "default_unit_price", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "products", "pricing_components", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(connection, "order_items", "base_unit_cost", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "order_items", "cost_components", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(connection, "order_items", "is_freebie", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "order_items", "applied_discount", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "order_items", "applied_tax", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "order_items", "price_adjustment_note", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "materials", "category", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "expenses", "material_id", "INTEGER")
        _ensure_column(connection, "product_materials", "include_in_unit_cost", "INTEGER NOT NULL DEFAULT 1")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_expenses_material_id ON expenses(material_id)")
        
        # Soft delete columns for undo/restore functionality
        _ensure_column(connection, "orders", "deleted_at", "TEXT")
        _ensure_column(connection, "products", "deleted_at", "TEXT")

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
