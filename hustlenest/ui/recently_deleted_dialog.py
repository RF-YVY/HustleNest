"""Recently Deleted dialog for viewing and restoring soft-deleted items."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import soft_delete_service


class RecentlyDeletedDialog(QDialog):
    """Dialog for managing soft-deleted items (trash)."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recently Deleted")
        self.resize(700, 450)
        self._setup_ui()
        self._refresh_list()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Info label
        info_label = QLabel(
            "Items you delete are moved here temporarily. "
            "You can restore them or permanently delete them."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Type", "Name", "Details", "Deleted At"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)
        
        # Action buttons
        btn_row = QHBoxLayout()
        
        restore_btn = QPushButton("Restore Selected")
        restore_btn.clicked.connect(self._restore_selected)
        btn_row.addWidget(restore_btn)
        
        delete_btn = QPushButton("Delete Permanently")
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)
        
        btn_row.addStretch(1)
        
        empty_btn = QPushButton("Empty Trash")
        empty_btn.clicked.connect(self._empty_trash)
        btn_row.addWidget(empty_btn)
        
        layout.addLayout(btn_row)
        
        # Status label
        self._status_label = QLabel()
        layout.addWidget(self._status_label)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)
    
    def _refresh_list(self) -> None:
        """Refresh the list of deleted items."""
        items = soft_delete_service.list_all_deleted_items()
        
        self._table.setRowCount(len(items))
        for row, item in enumerate(items):
            type_text = "Order" if item.item_type == "order" else "Product"
            self._table.setItem(row, 0, QTableWidgetItem(type_text))
            self._table.setItem(row, 1, QTableWidgetItem(item.name))
            self._table.setItem(row, 2, QTableWidgetItem(item.details))
            self._table.setItem(row, 3, QTableWidgetItem(
                item.deleted_at.strftime("%Y-%m-%d %H:%M")
            ))
            
            # Store item data for later use
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item)
        
        count = len(items)
        self._status_label.setText(f"{count} item{'s' if count != 1 else ''} in trash")
    
    def _get_selected_items(self) -> list:
        """Get list of selected DeletedItem objects."""
        items = []
        for row in set(idx.row() for idx in self._table.selectedIndexes()):
            item = self._table.item(row, 0)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data:
                    items.append(data)
        return items
    
    def _restore_selected(self) -> None:
        """Restore selected items."""
        items = self._get_selected_items()
        if not items:
            QMessageBox.warning(self, "No Selection", "Please select items to restore.")
            return
        
        restored = 0
        for item in items:
            if item.item_type == "order":
                if soft_delete_service.restore_order(item.id):
                    restored += 1
            else:
                if soft_delete_service.restore_product(item.id):
                    restored += 1
        
        self._status_label.setText(f"Restored {restored} item{'s' if restored != 1 else ''}")
        self._status_label.setStyleSheet("color: green;")
        self._refresh_list()
    
    def _delete_selected(self) -> None:
        """Permanently delete selected items."""
        items = self._get_selected_items()
        if not items:
            QMessageBox.warning(self, "No Selection", "Please select items to delete.")
            return
        
        confirm = QMessageBox.question(
            self,
            "Confirm Permanent Delete",
            f"Are you sure you want to permanently delete {len(items)} item{'s' if len(items) != 1 else ''}?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        deleted = 0
        for item in items:
            if item.item_type == "order":
                if soft_delete_service.permanent_delete_order(item.id):
                    deleted += 1
            else:
                if soft_delete_service.permanent_delete_product(item.id):
                    deleted += 1
        
        self._status_label.setText(f"Permanently deleted {deleted} item{'s' if deleted != 1 else ''}")
        self._status_label.setStyleSheet("color: #b00020;")
        self._refresh_list()
    
    def _empty_trash(self) -> None:
        """Empty all items from trash."""
        count = soft_delete_service.get_deleted_count()
        if count == 0:
            QMessageBox.information(self, "Empty Trash", "Trash is already empty.")
            return
        
        confirm = QMessageBox.question(
            self,
            "Empty Trash",
            f"Are you sure you want to permanently delete all {count} items in trash?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        orders, products = soft_delete_service.empty_trash()
        total = orders + products
        self._status_label.setText(f"Permanently deleted {total} item{'s' if total != 1 else ''}")
        self._status_label.setStyleSheet("color: #b00020;")
        self._refresh_list()
