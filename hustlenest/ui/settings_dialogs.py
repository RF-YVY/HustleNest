"""Settings dialogs for theme, backup, dashboard customization, and data import."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..data import settings_repository
from ..services import backup_service, import_service, report_service, theme_service
from ..services.backup_service import get_backup_scheduler
from ..services.theme_service import get_theme_manager
from ..models.order_models import AppSettings


class ThemeSettingsWidget(QWidget):
    """Widget for theme/appearance settings."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Theme selection
        theme_group = QGroupBox("Application Theme")
        theme_layout = QVBoxLayout()
        theme_group.setLayout(theme_layout)
        
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Color Theme:"))
        
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Light Mode", "light")
        self._theme_combo.addItem("Dark Mode", "dark")
        
        # Set current theme
        current = get_theme_manager().current_theme
        index = self._theme_combo.findData(current)
        if index >= 0:
            self._theme_combo.setCurrentIndex(index)
        
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch(1)
        
        theme_layout.addLayout(theme_row)
        
        hint_label = QLabel("Theme changes take effect immediately.")
        hint_label.setStyleSheet("color: #666; font-size: 11px;")
        theme_layout.addWidget(hint_label)
        
        layout.addWidget(theme_group)
        layout.addStretch(1)
    
    def _on_theme_changed(self, index: int) -> None:
        theme = self._theme_combo.currentData()
        if theme:
            get_theme_manager().set_theme(theme)


class DashboardSettingsWidget(QWidget):
    """Widget for dashboard customization settings."""
    
    # Section definitions: key -> (title, description)
    SECTIONS = {
        "product_sales": ("Product Sales Breakdown", "Shows product-level sales metrics"),
        "top_customers": ("Top Customers", "Lists your highest-value customers"),
        "notifications": ("Notifications", "Displays alerts and reminders"),
        "outstanding_orders": ("Outstanding Orders", "Lists orders awaiting completion"),
        "completed_orders": ("Completed Orders", "Shows recently fulfilled orders"),
    }
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._section_checkboxes: Dict[str, QCheckBox] = {}
        self._collapsed_checkboxes: Dict[str, QCheckBox] = {}
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Description
        desc_label = QLabel(
            "<h3>Dashboard Sections</h3>"
            "<p>Customize which sections appear on your dashboard and their default state. "
            "You can also click on section headers in the dashboard to collapse/expand them.</p>"
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Sections configuration
        sections_group = QGroupBox("Section Visibility")
        sections_layout = QVBoxLayout()
        sections_group.setLayout(sections_layout)
        
        for section_key, (title, description) in self.SECTIONS.items():
            section_row = QWidget()
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 4, 0, 4)
            section_row.setLayout(row_layout)
            
            # Visibility checkbox
            visible_cb = QCheckBox(title)
            visible_cb.setToolTip(description)
            visible_cb.setChecked(True)
            visible_cb.stateChanged.connect(lambda state, key=section_key: self._on_visibility_changed(key, state))
            self._section_checkboxes[section_key] = visible_cb
            row_layout.addWidget(visible_cb)
            
            row_layout.addStretch(1)
            
            # Collapsed by default checkbox
            collapsed_cb = QCheckBox("Start collapsed")
            collapsed_cb.stateChanged.connect(lambda state, key=section_key: self._on_collapsed_changed(key, state))
            self._collapsed_checkboxes[section_key] = collapsed_cb
            row_layout.addWidget(collapsed_cb)
            
            sections_layout.addWidget(section_row)
        
        layout.addWidget(sections_group)
        
        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout()
        actions_group.setLayout(actions_layout)
        
        expand_all_btn = QPushButton("Expand All")
        expand_all_btn.clicked.connect(self._expand_all)
        actions_layout.addWidget(expand_all_btn)
        
        collapse_all_btn = QPushButton("Collapse All")
        collapse_all_btn.clicked.connect(self._collapse_all)
        actions_layout.addWidget(collapse_all_btn)
        
        show_all_btn = QPushButton("Show All")
        show_all_btn.clicked.connect(self._show_all)
        actions_layout.addWidget(show_all_btn)
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        actions_layout.addWidget(reset_btn)
        
        actions_layout.addStretch(1)
        
        layout.addWidget(actions_group)
        layout.addStretch(1)
        
        # Note
        note_label = QLabel(
            "<i>Note: Changes are saved automatically and apply immediately to the dashboard.</i>"
        )
        note_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(note_label)
    
    def _load_settings(self) -> None:
        """Load current section states from settings."""
        try:
            raw = settings_repository.get_setting("dashboard_sections_json")
            if raw:
                states = json.loads(raw)
                for section_key, state_dict in states.items():
                    if section_key in self._section_checkboxes:
                        visible = state_dict.get("visible", True)
                        collapsed = state_dict.get("collapsed", False)
                        self._section_checkboxes[section_key].setChecked(visible)
                        self._collapsed_checkboxes[section_key].setChecked(collapsed)
        except (json.JSONDecodeError, TypeError):
            pass
    
    def _save_settings(self) -> None:
        """Save section states to settings."""
        states = {}
        for section_key in self.SECTIONS:
            states[section_key] = {
                "visible": self._section_checkboxes[section_key].isChecked(),
                "collapsed": self._collapsed_checkboxes[section_key].isChecked(),
            }
        settings_repository.set_setting("dashboard_sections_json", json.dumps(states))
        self._apply_to_live_sections()
    
    def _apply_to_live_sections(self) -> None:
        """Apply changes to live dashboard sections if available."""
        try:
            from .collapsible_group import get_section_manager
            manager = get_section_manager()
            for section_key, checkbox in self._section_checkboxes.items():
                section = manager.get_section(section_key)
                if section:
                    section.set_section_visible(checkbox.isChecked())
            for section_key, checkbox in self._collapsed_checkboxes.items():
                section = manager.get_section(section_key)
                if section:
                    section.set_collapsed(checkbox.isChecked())
        except ImportError:
            pass
    
    def _on_visibility_changed(self, section_key: str, state: int) -> None:
        self._save_settings()
    
    def _on_collapsed_changed(self, section_key: str, state: int) -> None:
        self._save_settings()
    
    def _expand_all(self) -> None:
        for cb in self._collapsed_checkboxes.values():
            cb.setChecked(False)
        self._save_settings()
    
    def _collapse_all(self) -> None:
        for cb in self._collapsed_checkboxes.values():
            cb.setChecked(True)
        self._save_settings()
    
    def _show_all(self) -> None:
        for cb in self._section_checkboxes.values():
            cb.setChecked(True)
        self._save_settings()
    
    def _reset_defaults(self) -> None:
        for cb in self._section_checkboxes.values():
            cb.setChecked(True)
        for cb in self._collapsed_checkboxes.values():
            cb.setChecked(False)
        self._save_settings()


class BackupSettingsWidget(QWidget):
    """Widget for backup configuration."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Backup settings
        settings_group = QGroupBox("Automatic Backups")
        settings_layout = QFormLayout()
        settings_group.setLayout(settings_layout)
        
        self._enabled_checkbox = QCheckBox("Enable automatic backups")
        settings_layout.addRow("", self._enabled_checkbox)
        
        # Folder selection
        folder_row = QHBoxLayout()
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText("Select backup folder...")
        folder_row.addWidget(self._folder_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        
        settings_layout.addRow("Backup Folder:", folder_row)
        
        self._frequency_combo = QComboBox()
        self._frequency_combo.addItem("Daily", "daily")
        self._frequency_combo.addItem("Weekly", "weekly")
        self._frequency_combo.addItem("Manual Only", "manual")
        settings_layout.addRow("Frequency:", self._frequency_combo)
        
        self._max_backups_spin = QSpinBox()
        self._max_backups_spin.setRange(1, 100)
        self._max_backups_spin.setValue(10)
        settings_layout.addRow("Keep Last:", self._max_backups_spin)
        
        layout.addWidget(settings_group)
        
        # Actions
        actions_group = QGroupBox("Backup Actions")
        actions_layout = QVBoxLayout()
        actions_group.setLayout(actions_layout)
        
        btn_row = QHBoxLayout()
        
        backup_now_btn = QPushButton("Backup Now")
        backup_now_btn.clicked.connect(self._backup_now)
        btn_row.addWidget(backup_now_btn)
        
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        btn_row.addWidget(save_btn)
        
        btn_row.addStretch(1)
        actions_layout.addLayout(btn_row)
        
        self._status_label = QLabel()
        actions_layout.addWidget(self._status_label)
        
        layout.addWidget(actions_group)
        
        # Backup list
        backups_group = QGroupBox("Available Backups")
        backups_layout = QVBoxLayout()
        backups_group.setLayout(backups_layout)
        
        self._backups_table = QTableWidget()
        self._backups_table.setColumnCount(3)
        self._backups_table.setHorizontalHeaderLabels(["Filename", "Date", "Size"])
        self._backups_table.horizontalHeader().setStretchLastSection(True)
        self._backups_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._backups_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        backups_layout.addWidget(self._backups_table)
        
        restore_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.clicked.connect(self._refresh_backups)
        restore_row.addWidget(refresh_btn)
        
        restore_btn = QPushButton("Restore Selected")
        restore_btn.clicked.connect(self._restore_selected)
        restore_row.addWidget(restore_btn)
        
        restore_row.addStretch(1)
        backups_layout.addLayout(restore_row)
        
        layout.addWidget(backups_group)
    
    def _load_settings(self) -> None:
        scheduler = get_backup_scheduler()
        scheduler.load_settings()
        
        self._enabled_checkbox.setChecked(scheduler.is_enabled)
        self._folder_input.setText(scheduler.backup_folder)
        
        freq_index = self._frequency_combo.findData(scheduler.frequency)
        if freq_index >= 0:
            self._frequency_combo.setCurrentIndex(freq_index)
        
        self._max_backups_spin.setValue(scheduler.max_backups)
        
        if scheduler.last_backup:
            self._status_label.setText(f"Last backup: {scheduler.last_backup.strftime('%Y-%m-%d %H:%M')}")
        
        self._refresh_backups()
    
    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Backup Folder",
            self._folder_input.text() or str(Path.home()),
        )
        if folder:
            self._folder_input.setText(folder)
    
    def _save_settings(self) -> None:
        scheduler = get_backup_scheduler()
        scheduler.save_settings(
            enabled=self._enabled_checkbox.isChecked(),
            folder=self._folder_input.text().strip(),
            frequency=self._frequency_combo.currentData() or "daily",
            max_backups=self._max_backups_spin.value(),
        )
        self._status_label.setText("Settings saved.")
        self._status_label.setStyleSheet("color: green;")
    
    def _backup_now(self) -> None:
        # Save settings first
        self._save_settings()
        
        scheduler = get_backup_scheduler()
        success, message = scheduler.perform_backup()
        
        if success:
            self._status_label.setText(message)
            self._status_label.setStyleSheet("color: green;")
            self._refresh_backups()
        else:
            self._status_label.setText(message)
            self._status_label.setStyleSheet("color: red;")
    
    def _refresh_backups(self) -> None:
        scheduler = get_backup_scheduler()
        backups = scheduler.list_backups()
        
        self._backups_table.setRowCount(len(backups))
        for row, (filename, created, size) in enumerate(backups):
            self._backups_table.setItem(row, 0, QTableWidgetItem(filename))
            self._backups_table.setItem(row, 1, QTableWidgetItem(created.strftime("%Y-%m-%d %H:%M")))
            size_mb = size / (1024 * 1024)
            self._backups_table.setItem(row, 2, QTableWidgetItem(f"{size_mb:.2f} MB"))
    
    def _restore_selected(self) -> None:
        selection = self._backups_table.selectedItems()
        if not selection:
            QMessageBox.warning(self, "No Selection", "Please select a backup to restore.")
            return
        
        row = selection[0].row()
        filename_item = self._backups_table.item(row, 0)
        if filename_item is None:
            return
        filename = filename_item.text()
        
        confirm = QMessageBox.question(
            self,
            "Confirm Restore",
            f"Are you sure you want to restore '{filename}'?\n\n"
            "This will replace your current database. The application will need to restart.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        scheduler = get_backup_scheduler()
        success, message = scheduler.restore_backup(filename)
        
        if success:
            QMessageBox.information(
                self,
                "Restore Complete",
                f"{message}\n\nPlease restart the application to use the restored database.",
            )
        else:
            QMessageBox.critical(self, "Restore Failed", message)


class DataImportDialog(QDialog):
    """Dialog for importing data from CSV/Excel files."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Data")
        self.resize(800, 600)
        self._file_path: str = ""
        self._columns: List[import_service.ImportColumn] = []
        self._mappings: List[import_service.ColumnMapping] = []
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Step 1: File selection
        file_group = QGroupBox("Step 1: Select File")
        file_layout = QHBoxLayout()
        file_group.setLayout(file_layout)
        
        self._file_input = QLineEdit()
        self._file_input.setPlaceholderText("Select a CSV or Excel file...")
        self._file_input.setReadOnly(True)
        file_layout.addWidget(self._file_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        
        layout.addWidget(file_group)
        
        # Step 2: Import type
        type_group = QGroupBox("Step 2: Select Import Type")
        type_layout = QHBoxLayout()
        type_group.setLayout(type_layout)
        
        type_layout.addWidget(QLabel("Import as:"))
        self._type_combo = QComboBox()
        self._type_combo.addItem("Products", "products")
        self._type_combo.addItem("Orders", "orders")
        self._type_combo.addItem("Customers", "customers")
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self._type_combo)
        
        self._skip_duplicates_checkbox = QCheckBox("Skip duplicates (don't update existing)")
        self._skip_duplicates_checkbox.setChecked(True)
        type_layout.addWidget(self._skip_duplicates_checkbox)
        
        type_layout.addStretch(1)
        layout.addWidget(type_group)
        
        # Step 3: Column mapping
        mapping_group = QGroupBox("Step 3: Map Columns")
        mapping_layout = QVBoxLayout()
        mapping_group.setLayout(mapping_layout)
        
        self._mapping_table = QTableWidget()
        self._mapping_table.setColumnCount(4)
        self._mapping_table.setHorizontalHeaderLabels(["Source Column", "Sample Data", "→", "Target Field"])
        self._mapping_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._mapping_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._mapping_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._mapping_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._mapping_table.setColumnWidth(2, 30)
        mapping_layout.addWidget(self._mapping_table)
        
        auto_map_btn = QPushButton("Auto-Map Columns")
        auto_map_btn.clicked.connect(self._auto_map)
        mapping_layout.addWidget(auto_map_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        layout.addWidget(mapping_group)
        
        # Progress and status
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        self._status_label = QLabel()
        layout.addWidget(self._status_label)
        
        # Buttons
        button_box = QDialogButtonBox()
        self._import_btn = QPushButton("Import")
        self._import_btn.clicked.connect(self._do_import)
        self._import_btn.setEnabled(False)
        button_box.addButton(self._import_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_box.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        
        layout.addWidget(button_box)
    
    def _browse_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Import File",
            str(Path.home()),
            "Data Files (*.csv *.xlsx);;CSV Files (*.csv);;Excel Files (*.xlsx)",
        )
        if file_path:
            self._file_path = file_path
            self._file_input.setText(file_path)
            self._load_preview()
    
    def _load_preview(self) -> None:
        if not self._file_path:
            return
        
        try:
            suffix = Path(self._file_path).suffix.lower()
            if suffix == ".csv":
                self._columns, data, _ = import_service.read_csv_preview(self._file_path)
            elif suffix == ".xlsx":
                self._columns, data, _ = import_service.read_excel_preview(self._file_path)
            else:
                self._status_label.setText(f"Unsupported file type: {suffix}")
                return
            
            self._populate_mapping_table()
            self._auto_map()
            self._import_btn.setEnabled(True)
            self._status_label.setText(f"Loaded {len(self._columns)} columns from file.")
            
        except Exception as e:
            self._status_label.setText(f"Error loading file: {e}")
            self._status_label.setStyleSheet("color: red;")
    
    def _populate_mapping_table(self) -> None:
        self._mapping_table.setRowCount(len(self._columns))
        
        import_type = self._type_combo.currentData()
        target_fields = import_service.get_field_definitions(import_type)
        
        for row, col in enumerate(self._columns):
            # Source column name
            self._mapping_table.setItem(row, 0, QTableWidgetItem(col.name))
            
            # Sample data
            sample = ", ".join(col.sample_values[:3])
            if len(sample) > 50:
                sample = sample[:47] + "..."
            self._mapping_table.setItem(row, 1, QTableWidgetItem(sample))
            
            # Arrow
            self._mapping_table.setItem(row, 2, QTableWidgetItem("→"))
            
            # Target field combo
            combo = QComboBox()
            combo.addItem("(Skip)", "")
            for field_name, field_def in target_fields.items():
                label = field_def.get("label", field_name)
                required = field_def.get("required", False)
                if required:
                    label += " *"
                combo.addItem(label, field_name)
            
            self._mapping_table.setCellWidget(row, 3, combo)
    
    def _on_type_changed(self, index: int) -> None:
        if self._columns:
            self._populate_mapping_table()
            self._auto_map()
    
    def _auto_map(self) -> None:
        if not self._columns:
            return
        
        import_type = self._type_combo.currentData()
        target_fields = import_service.get_field_definitions(import_type)
        
        auto_mappings = import_service.auto_map_columns(self._columns, target_fields)
        
        # Apply auto-mappings to the table
        for mapping in auto_mappings:
            row = mapping.source_column
            combo = self._mapping_table.cellWidget(row, 3)
            if isinstance(combo, QComboBox):
                index = combo.findData(mapping.target_field)
                if index >= 0:
                    combo.setCurrentIndex(index)
        
        self._status_label.setText(f"Auto-mapped {len(auto_mappings)} columns.")
    
    def _collect_mappings(self) -> List[import_service.ColumnMapping]:
        mappings = []
        import_type = self._type_combo.currentData()
        target_fields = import_service.get_field_definitions(import_type)
        
        for row in range(self._mapping_table.rowCount()):
            combo = self._mapping_table.cellWidget(row, 3)
            if not isinstance(combo, QComboBox):
                continue
            
            target = combo.currentData()
            if not target:
                continue
            
            field_def = target_fields.get(target, {})
            field_type = field_def.get("type", "text")
            transform = None
            if field_type == "date":
                transform = "date"
            elif field_type == "number":
                transform = "number"
            elif field_type == "boolean":
                transform = "boolean"
            
            mappings.append(import_service.ColumnMapping(
                source_column=row,
                target_field=target,
                transform=transform,
            ))
        
        return mappings
    
    def _do_import(self) -> None:
        if not self._file_path:
            QMessageBox.warning(self, "No File", "Please select a file to import.")
            return
        
        mappings = self._collect_mappings()
        if not mappings:
            QMessageBox.warning(self, "No Mappings", "Please map at least one column.")
            return
        
        import_type = self._type_combo.currentData()
        skip_duplicates = self._skip_duplicates_checkbox.isChecked()
        
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        self._import_btn.setEnabled(False)
        
        try:
            if import_type == "products":
                result = import_service.import_products(self._file_path, mappings, skip_duplicates)
            elif import_type == "orders":
                result = import_service.import_orders(self._file_path, mappings, skip_duplicates)
            elif import_type == "customers":
                result = import_service.import_customers(self._file_path, mappings, skip_duplicates)
            else:
                result = import_service.ImportResult(
                    success=False,
                    imported_count=0,
                    skipped_count=0,
                    error_count=1,
                    errors=[f"Unknown import type: {import_type}"],
                )
            
            self._progress_bar.setVisible(False)
            self._import_btn.setEnabled(True)
            
            # Show results
            message = f"Import complete!\n\n"
            message += f"Imported: {result.imported_count}\n"
            message += f"Skipped: {result.skipped_count}\n"
            message += f"Errors: {result.error_count}\n"
            
            if result.errors:
                message += f"\nFirst few errors:\n"
                for error in result.errors[:5]:
                    message += f"  • {error}\n"
                if len(result.errors) > 5:
                    message += f"  ... and {len(result.errors) - 5} more"
            
            if result.imported_count > 0:
                QMessageBox.information(self, "Import Complete", message)
                self.accept()
            else:
                QMessageBox.warning(self, "Import Issues", message)
                
        except Exception as e:
            self._progress_bar.setVisible(False)
            self._import_btn.setEnabled(True)
            QMessageBox.critical(self, "Import Error", f"An error occurred:\n{e}")


class ReportExportDialog(QDialog):
    """Dialog for exporting reports to PDF."""
    
    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Reports")
        self.resize(500, 450)
        self._settings = settings
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Report type selection
        type_group = QGroupBox("Report Type")
        type_layout = QVBoxLayout()
        type_group.setLayout(type_layout)
        
        self._report_type_combo = QComboBox()
        self._report_type_combo.addItem("Sales Report", "sales")
        self._report_type_combo.addItem("Inventory Report", "inventory")
        self._report_type_combo.addItem("Profit & Loss Statement", "pnl")
        self._report_type_combo.addItem("Customer Report", "customer")
        self._report_type_combo.addItem("Period Comparison", "comparison")
        self._report_type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self._report_type_combo)
        
        layout.addWidget(type_group)
        
        # Date range
        self._date_group = QGroupBox("Date Range")
        date_layout = QFormLayout()
        self._date_group.setLayout(date_layout)
        
        self._period_combo = QComboBox()
        self._period_combo.addItem("This Month", "this_month")
        self._period_combo.addItem("Last Month", "last_month")
        self._period_combo.addItem("This Quarter", "this_quarter")
        self._period_combo.addItem("Last Quarter", "last_quarter")
        self._period_combo.addItem("This Year", "this_year")
        self._period_combo.addItem("Last Year", "last_year")
        self._period_combo.addItem("Last 30 Days", "last_30_days")
        self._period_combo.addItem("Last 90 Days", "last_90_days")
        self._period_combo.addItem("Custom", "custom")
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        date_layout.addRow("Period:", self._period_combo)
        
        self._start_date = QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._start_date.setDate(QDate.currentDate().addMonths(-1))
        self._start_date.setVisible(False)
        self._start_date_label = QLabel("Start Date:")
        self._start_date_label.setVisible(False)
        date_layout.addRow(self._start_date_label, self._start_date)
        
        self._end_date = QDateEdit()
        self._end_date.setCalendarPopup(True)
        self._end_date.setDate(QDate.currentDate())
        self._end_date.setVisible(False)
        self._end_date_label = QLabel("End Date:")
        self._end_date_label.setVisible(False)
        date_layout.addRow(self._end_date_label, self._end_date)
        
        layout.addWidget(self._date_group)
        
        # Comparison options (hidden by default)
        self._comparison_group = QGroupBox("Comparison Settings")
        comparison_layout = QFormLayout()
        self._comparison_group.setLayout(comparison_layout)
        
        self._compare_type_combo = QComboBox()
        self._compare_type_combo.addItem("This Month vs Last Month", "month_vs_month")
        self._compare_type_combo.addItem("This Quarter vs Last Quarter", "quarter_vs_quarter")
        self._compare_type_combo.addItem("This Year vs Last Year", "year_vs_year")
        comparison_layout.addRow("Compare:", self._compare_type_combo)
        
        self._comparison_group.setVisible(False)
        layout.addWidget(self._comparison_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        options_group.setLayout(options_layout)
        
        self._include_details_checkbox = QCheckBox("Include order details (Sales Report only)")
        self._include_details_checkbox.setChecked(True)
        options_layout.addWidget(self._include_details_checkbox)
        
        layout.addWidget(options_group)
        
        # Status
        self._status_label = QLabel()
        layout.addWidget(self._status_label)
        
        layout.addStretch(1)
        
        # Buttons
        button_box = QDialogButtonBox()
        
        export_btn = QPushButton("Export to PDF")
        export_btn.clicked.connect(self._do_export)
        button_box.addButton(export_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_box.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        
        layout.addWidget(button_box)
    
    def _on_type_changed(self, index: int) -> None:
        report_type = self._report_type_combo.currentData()
        
        # Show/hide date range based on report type
        needs_dates = report_type in ("sales", "pnl", "customer", "comparison")
        self._date_group.setVisible(needs_dates)
        
        # Show comparison options
        self._comparison_group.setVisible(report_type == "comparison")
        
        # Show details option only for sales
        self._include_details_checkbox.setVisible(report_type == "sales")
    
    def _on_period_changed(self, index: int) -> None:
        period = self._period_combo.currentData()
        is_custom = period == "custom"
        
        # Show/hide custom date inputs
        self._start_date.setVisible(is_custom)
        self._end_date.setVisible(is_custom)
        
        # Update labels using explicit references stored during setup
        if hasattr(self, "_start_date_label"):
            self._start_date_label.setVisible(is_custom)
        if hasattr(self, "_end_date_label"):
            self._end_date_label.setVisible(is_custom)
    
    def _get_date_range(self) -> Tuple:
        from datetime import date, timedelta
        
        period = self._period_combo.currentData()
        
        if period == "custom":
            start = self._start_date.date().toPython()
            end = self._end_date.date().toPython()
            return start, end
        
        return report_service._get_period_dates(period)
    
    def _do_export(self) -> None:
        from datetime import date, timedelta
        
        report_type = self._report_type_combo.currentData()
        
        # Generate the appropriate report
        try:
            if report_type == "sales":
                start, end = self._get_date_range()
                html = report_service.generate_sales_report_html(
                    start, end, self._settings,
                    include_details=self._include_details_checkbox.isChecked(),
                )
                default_name = f"SalesReport_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.pdf"
                
            elif report_type == "inventory":
                html = report_service.generate_inventory_report_html(self._settings)
                default_name = f"InventoryReport_{date.today().strftime('%Y%m%d')}.pdf"
                
            elif report_type == "pnl":
                start, end = self._get_date_range()
                html = report_service.generate_pnl_report_html(start, end, self._settings)
                default_name = f"ProfitLoss_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.pdf"
                
            elif report_type == "customer":
                start, end = self._get_date_range()
                html = report_service.generate_customer_report_html(start, end, self._settings)
                default_name = f"CustomerReport_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.pdf"
                
            elif report_type == "comparison":
                compare_type = self._compare_type_combo.currentData()
                today = date.today()
                
                if compare_type == "month_vs_month":
                    # This month
                    p1_start = today.replace(day=1)
                    p1_end = today
                    # Last month
                    p2_end = p1_start - timedelta(days=1)
                    p2_start = p2_end.replace(day=1)
                    p1_label = "This Month"
                    p2_label = "Last Month"
                    
                elif compare_type == "quarter_vs_quarter":
                    quarter = (today.month - 1) // 3
                    p1_start = date(today.year, quarter * 3 + 1, 1)
                    p1_end = today
                    if quarter == 0:
                        p2_start = date(today.year - 1, 10, 1)
                        p2_end = date(today.year - 1, 12, 31)
                    else:
                        p2_start = date(today.year, (quarter - 1) * 3 + 1, 1)
                        p2_end = p1_start - timedelta(days=1)
                    p1_label = "This Quarter"
                    p2_label = "Last Quarter"
                    
                else:  # year_vs_year
                    p1_start = date(today.year, 1, 1)
                    p1_end = today
                    p2_start = date(today.year - 1, 1, 1)
                    p2_end = date(today.year - 1, 12, 31)
                    p1_label = str(today.year)
                    p2_label = str(today.year - 1)
                
                html = report_service.generate_comparison_report_html(
                    p1_start, p1_end, p2_start, p2_end,
                    p1_label, p2_label, self._settings,
                )
                default_name = f"Comparison_{p1_label.replace(' ', '')}vs{p2_label.replace(' ', '')}.pdf"
            else:
                self._status_label.setText(f"Unknown report type: {report_type}")
                return
            
            # Save to PDF
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Report",
                str(Path.home() / "Documents" / default_name),
                "PDF Files (*.pdf);;HTML Files (*.html)",
            )
            
            if not file_path:
                return
            
            # Check file extension
            if file_path.lower().endswith(".html"):
                # Save as HTML
                Path(file_path).write_text(html, encoding="utf-8")
                self._status_label.setText(f"Saved: {file_path}")
                self._status_label.setStyleSheet("color: green;")
            else:
                # Try to generate PDF using Qt's print support
                self._save_as_pdf(html, file_path)
            
        except Exception as e:
            self._status_label.setText(f"Error: {e}")
            self._status_label.setStyleSheet("color: red;")
    
    def _save_as_pdf(self, html: str, file_path: str) -> None:
        """Save HTML as PDF using QTextDocument."""
        from PySide6.QtGui import QTextDocument, QFont
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtCore import QMarginsF, QSizeF
        
        # Create printer for PDF - use ScreenResolution for proper text sizing
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageMargins(QMarginsF(25, 20, 25, 20))
        
        # Create document
        doc = QTextDocument()
        
        # Set default font to ensure readable base size
        default_font = QFont("Segoe UI", 12)
        doc.setDefaultFont(default_font)
        
        # Set page size to match printer's page rect for proper layout
        page_rect = printer.pageRect(QPrinter.Unit.Point)
        doc.setPageSize(QSizeF(page_rect.width(), page_rect.height()))
        
        # Set the HTML content
        doc.setHtml(html)
        
        # Print to PDF
        doc.print_(printer)
        
        self._status_label.setText(f"Saved: {file_path}")
        self._status_label.setStyleSheet("color: green;")
        
        QMessageBox.information(self, "Export Complete", f"Report saved to:\n{file_path}")


class AdvancedSettingsDialog(QDialog):
    """Dialog containing advanced settings: Theme, Backup, Import."""
    
    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.resize(700, 550)
        self._settings = settings
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Tab widget
        tabs = QTabWidget()
        
        # Theme tab
        theme_widget = ThemeSettingsWidget()
        tabs.addTab(theme_widget, "Appearance")
        
        # Dashboard tab
        dashboard_widget = DashboardSettingsWidget()
        tabs.addTab(dashboard_widget, "Dashboard")
        
        # Backup tab
        backup_widget = BackupSettingsWidget()
        tabs.addTab(backup_widget, "Backups")
        
        # Import tab
        import_widget = QWidget()
        import_layout = QVBoxLayout()
        import_widget.setLayout(import_layout)
        
        import_label = QLabel(
            "<h3>Data Import</h3>"
            "<p>Import data from CSV or Excel files. You can import:</p>"
            "<ul>"
            "<li><b>Products:</b> SKU, name, description, inventory, pricing</li>"
            "<li><b>Orders:</b> Order numbers, customers, dates, status</li>"
            "</ul>"
            "<p>Click the button below to start the import wizard.</p>"
        )
        import_label.setWordWrap(True)
        import_layout.addWidget(import_label)
        
        import_btn = QPushButton("Open Import Wizard...")
        import_btn.clicked.connect(self._open_import_wizard)
        import_layout.addWidget(import_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        import_layout.addStretch(1)
        tabs.addTab(import_widget, "Import Data")
        
        layout.addWidget(tabs)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)
    
    def _open_import_wizard(self) -> None:
        dialog = DataImportDialog(self)
        dialog.exec()
