from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QDoubleSpinBox,
    QFrame,
    QScrollArea,
    QSpinBox,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSplitter,
)

from ..models.order_models import AppSettings, CostComponent, Product
from ..services import order_service
from ..viewmodels.table_models import ListTableModel
from .cost_component_dialog import CostComponentEditorDialog

ProductsChangedCallback = Callable[[Optional[str]], None]
_PHOTO_HINT_DEFAULT = "Images are copied into the application data folder when saved."


class ProductManagerDialog(QDialog):
    def __init__(
        self,
        *,
        parent: Optional[QWidget] = None,
        app_settings: AppSettings,
        product_status_options: List[str],
        on_products_changed: Optional[ProductsChangedCallback] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Product Manager")
        self.resize(1100, 820)

        self._on_products_changed = on_products_changed
        self._app_settings = app_settings
        self._product_status_options = list(product_status_options)

        self._products: List[Product] = []
        self._selected_product: Optional[Product] = None
        self._selection_connected = False
        self._product_pricing_components: List[CostComponent] = []
        self._current_photo_path: Optional[Path] = None

        self._forecast_model = ListTableModel(
            (
                ("Product", lambda row: getattr(row, "name", "")),
                ("SKU", lambda row: getattr(row, "sku", "")),
                ("Inventory", lambda row: getattr(row, "inventory_count", "")),
                (
                    "Avg Weekly",
                    lambda row: f"{getattr(row, 'average_weekly_sales', 0.0):,.1f}",
                ),
                ("Days Left", lambda row: self._days_until_stockout(row)),
                ("Status", lambda row: getattr(row, "status", "")),
                (
                    "Action",
                    lambda row: "Reorder" if getattr(row, "needs_reorder", False) else "",
                ),
            )
        )

        self._products_model = ListTableModel(
            (
                ("SKU", lambda product: getattr(product, "sku", "")),
                ("Name", lambda product: getattr(product, "name", "")),
                ("Inventory", lambda product: getattr(product, "inventory_count", "")),
                ("Unit Cost", lambda product: f"${getattr(product, 'total_unit_cost', 0):,.2f}"),
                ("Price", lambda product: f"${getattr(product, 'default_unit_price', 0):,.2f}"),
                ("Status", lambda product: getattr(product, "status", "")),
                ("Alerts", lambda product: self._product_alert_text(product)),
                ("Description", lambda product: getattr(product, "description", "")),
            )
        )

        self._build_ui()
        self.refresh_data()

    def refresh_data(self, *, select_sku: Optional[str] = None) -> None:
        self._products = order_service.list_products()
        self._products_model.update_rows(self._products)

        selection_model = self._products_table.selectionModel()
        if selection_model is not None and not self._selection_connected:
            selection_model.currentChanged.connect(self._on_product_selection_changed)
            self._selection_connected = True

        forecasts = order_service.list_inventory_forecast()
        self._forecast_model.update_rows(forecasts)

        if select_sku:
            index = next((i for i, product in enumerate(self._products) if product.sku == select_sku), -1)
        elif self._selected_product is not None:
            index = next(
                (i for i, product in enumerate(self._products) if product.sku == self._selected_product.sku),
                -1,
            )
        else:
            index = -1

        if index >= 0:
            self._products_table.selectRow(index)
            model_index = self._products_model.index(index, 0)
            self._products_table.scrollTo(model_index)
            self._selected_product = self._products[index]
        else:
            self._products_table.clearSelection()
            self._selected_product = None

        self._update_product_form(self._selected_product)

    def update_app_settings(self, app_settings: AppSettings) -> None:
        self._app_settings = app_settings
        self._update_product_form(self._selected_product)

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        self.setLayout(layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area, stretch=1)

        content_container = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_container.setLayout(content_layout)
        scroll_area.setWidget(content_container)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        content_layout.addWidget(splitter, stretch=1)

        forecast_container = QWidget()
        forecast_layout = QVBoxLayout()
        forecast_layout.setContentsMargins(0, 0, 0, 0)
        forecast_layout.setSpacing(6)
        forecast_container.setLayout(forecast_layout)
        forecast_layout.addWidget(QLabel("Inventory Forecast"))
        self._forecast_table = QTableView()
        self._forecast_table.setModel(self._forecast_model)
        self._configure_table(self._forecast_table)
        self._forecast_table.setMinimumHeight(220)
        forecast_layout.addWidget(self._forecast_table)
        splitter.addWidget(forecast_container)

        products_container = QWidget()
        products_layout = QVBoxLayout()
        products_layout.setContentsMargins(0, 0, 0, 0)
        products_layout.setSpacing(6)
        products_container.setLayout(products_layout)
        products_layout.addWidget(QLabel("Products"))
        self._products_table = QTableView()
        self._products_table.setModel(self._products_model)
        self._configure_table(self._products_table)
        self._products_table.setMinimumHeight(220)
        products_layout.addWidget(self._products_table)
        splitter.addWidget(products_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        selection_model = self._products_table.selectionModel()
        if selection_model is not None:
            selection_model.currentChanged.connect(self._on_product_selection_changed)
            self._selection_connected = True

        form_group = QWidget()
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        content_layout.addWidget(form_group)

        self._product_sku_input = QLineEdit()
        form_layout.addRow("SKU", self._product_sku_input)

        self._product_name_input = QLineEdit()
        form_layout.addRow("Name", self._product_name_input)

        self._product_description_text = QTextEdit()
        self._product_description_text.setFixedHeight(48)
        form_layout.addRow("Description", self._product_description_text)

        photo_widget = QWidget()
        photo_widget_layout = QHBoxLayout()
        photo_widget_layout.setContentsMargins(0, 0, 0, 0)
        photo_widget_layout.setSpacing(8)
        photo_widget.setLayout(photo_widget_layout)

        photo_fields_layout = QVBoxLayout()
        photo_fields_layout.setContentsMargins(0, 0, 0, 0)
        photo_fields_layout.setSpacing(6)

        photo_path_row = QHBoxLayout()
        photo_path_row.setContentsMargins(0, 0, 0, 0)
        photo_path_row.setSpacing(6)
        self._product_photo_input = QLineEdit()
        self._product_photo_input.textChanged.connect(self._on_photo_path_changed)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._handle_browse_photo)
        self._open_photo_button = QPushButton("Open Image")
        self._open_photo_button.clicked.connect(self._handle_open_photo)
        self._open_photo_button.setEnabled(False)
        photo_path_row.addWidget(self._product_photo_input)
        photo_path_row.addWidget(browse_button)
        photo_path_row.addWidget(self._open_photo_button)
        photo_fields_layout.addLayout(photo_path_row)

        self._photo_hint_label = QLabel(_PHOTO_HINT_DEFAULT)
        self._photo_hint_label.setWordWrap(True)
        photo_fields_layout.addWidget(self._photo_hint_label)

        photo_widget_layout.addLayout(photo_fields_layout)

        self._product_photo_preview = QLabel("No Preview")
        self._product_photo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._product_photo_preview.setFixedSize(160, 160)
        self._product_photo_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self._product_photo_preview.setFrameShadow(QFrame.Shadow.Sunken)
        photo_widget_layout.addWidget(self._product_photo_preview)

        form_layout.addRow("Photo", photo_widget)

        self._product_inventory_input = QSpinBox()
        self._product_inventory_input.setMaximum(1_000_000)
        form_layout.addRow("Inventory", self._product_inventory_input)

        self._product_base_cost_input = QDoubleSpinBox()
        self._product_base_cost_input.setPrefix("$")
        self._product_base_cost_input.setDecimals(2)
        self._product_base_cost_input.setMaximum(1_000_000)
        self._product_base_cost_input.valueChanged.connect(lambda _value: self._update_pricing_summary())
        form_layout.addRow("Base Unit Cost", self._product_base_cost_input)

        self._product_price_input = QDoubleSpinBox()
        self._product_price_input.setPrefix("$")
        self._product_price_input.setDecimals(2)
        self._product_price_input.setMaximum(1_000_000)
        self._product_price_input.valueChanged.connect(lambda _value: self._update_pricing_summary())
        form_layout.addRow("Default Price", self._product_price_input)

        extras_layout = QHBoxLayout()
        self._product_cost_summary_label = QLabel()
        extras_button = QPushButton("Edit Extras…")
        extras_button.clicked.connect(self._handle_product_pricing_components)
        extras_layout.addWidget(extras_button)
        extras_layout.addWidget(self._product_cost_summary_label)
        extras_layout.addStretch(1)
        form_layout.addRow("Extras", extras_layout)

        self._product_status_combo = QComboBox()
        self._product_status_combo.addItems(self._product_status_options)
        form_layout.addRow("Status", self._product_status_combo)

        self._product_alert_hint = QLabel()
        form_layout.addRow("Alerts", self._product_alert_hint)

        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        new_button = QPushButton("New Product")
        new_button.clicked.connect(self._handle_product_new)
        button_layout.addWidget(new_button)

        save_button = QPushButton("Save Changes")
        save_button.clicked.connect(self._handle_product_save)
        button_layout.addWidget(save_button)

        delete_button = QPushButton("Delete Product")
        delete_button.clicked.connect(self._handle_product_delete)
        button_layout.addWidget(delete_button)

        button_layout.addStretch(1)
        self._update_pricing_summary()

    def _on_product_selection_changed(self, current, _previous) -> None:
        row = current.row()
        if 0 <= row < len(self._products):
            self._selected_product = self._products[row]
        else:
            self._selected_product = None
        self._update_product_form(self._selected_product)

    def _update_product_form(self, product: Optional[Product]) -> None:
        if product is None:
            self._product_sku_input.clear()
            self._product_name_input.clear()
            self._product_description_text.clear()
            self._product_photo_input.clear()
            self._update_photo_preview("")
            self._product_inventory_input.setValue(0)
            self._product_base_cost_input.blockSignals(True)
            self._product_base_cost_input.setValue(0.00)
            self._product_base_cost_input.blockSignals(False)
            self._product_price_input.blockSignals(True)
            self._product_price_input.setValue(0.00)
            self._product_price_input.blockSignals(False)
            self._product_status_combo.blockSignals(True)
            if self._product_status_combo.count() > 0:
                self._product_status_combo.setCurrentIndex(0)
            self._product_status_combo.blockSignals(False)
            self._product_pricing_components = []
            self._product_alert_hint.clear()
            self._update_pricing_summary()
            return

        self._product_sku_input.setText(product.sku)
        self._product_name_input.setText(product.name)
        self._product_description_text.setText(product.description)
        self._product_photo_input.setText(product.photo_path)
        self._update_photo_preview(product.photo_path)
        self._product_inventory_input.setValue(product.inventory_count)
        self._product_base_cost_input.blockSignals(True)
        self._product_base_cost_input.setValue(product.base_unit_cost)
        self._product_base_cost_input.blockSignals(False)
        self._product_price_input.blockSignals(True)
        self._product_price_input.setValue(product.default_unit_price)
        self._product_price_input.blockSignals(False)
        self._product_status_combo.blockSignals(True)
        combo_index = self._product_status_combo.findText(
            product.status,
            Qt.MatchFlag.MatchFixedString,
        )
        if combo_index >= 0:
            self._product_status_combo.setCurrentIndex(combo_index)
        elif self._product_status_combo.count() > 0:
            self._product_status_combo.setCurrentIndex(0)
        self._product_status_combo.blockSignals(False)
        self._product_pricing_components = self._clone_components(product.pricing_components)
        self._product_alert_hint.setText(self._product_alert_text(product))
        self._update_pricing_summary()

    def _handle_product_new(self) -> None:
        dialog = _NewProductDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            created = order_service.ensure_product_exists(dialog.sku, dialog.name)
        except ValueError as exc:  # noqa: BLE001
            self._show_message(str(exc))
            return

        self.refresh_data(select_sku=created.sku)
        self._notify_products_changed(created.sku)
        self._show_message("Product created. Add details and save when ready.")

    def _handle_product_save(self) -> None:
        if self._selected_product is None:
            self._show_message("Select a product from the list to update, or add it from the Orders tab.")
            return

        new_sku = self._product_sku_input.text().strip().upper()
        if not new_sku:
            self._show_message("SKU is required.")
            return

        description_text = self._product_description_text.toPlainText().strip()
        photo_path = self._product_photo_input.text().strip()
        status = self._product_status_combo.currentText().strip()

        updated = replace(
            self._selected_product,
            sku=new_sku,
            name=self._product_name_input.text().strip() or new_sku,
            description=description_text,
            photo_path=photo_path,
            inventory_count=self._product_inventory_input.value(),
            is_complete=self._is_product_complete(description_text, photo_path),
            status=status,
            base_unit_cost=self._product_base_cost_input.value(),
            default_unit_price=self._product_price_input.value(),
            pricing_components=self._clone_components(self._product_pricing_components),
        )

        try:
            saved = order_service.update_product(updated)
        except ValueError as exc:  # noqa: BLE001
            self._show_message(str(exc))
            return

        self.refresh_data(select_sku=saved.sku)
        self._notify_products_changed(saved.sku)
        self._show_message("Product details saved.")

    def _handle_product_delete(self) -> None:
        if self._selected_product is None or self._selected_product.id is None:
            self._show_message("Select a product from the list before deleting.")
            return

        confirm = QMessageBox.question(
            self,
            "Product Manager",
            f"Delete {self._selected_product.name}? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            order_service.delete_product(self._selected_product.id)
        except Exception as exc:  # noqa: BLE001
            self._show_message(f"Failed to delete product: {exc}")
            return

        self.refresh_data()
        self._notify_products_changed(None)
        self._show_message("Product deleted.")

    def _handle_product_pricing_components(self) -> None:
        dialog = CostComponentEditorDialog(components=self._product_pricing_components, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._product_pricing_components = dialog.components()
        self._update_pricing_summary()

    def _update_pricing_summary(self) -> None:
        if not hasattr(self, "_product_cost_summary_label"):
            return

        extras_total = sum(component.amount for component in self._product_pricing_components)
        unit_cost = self._product_base_cost_input.value() + extras_total
        default_price = self._product_price_input.value()
        if default_price > 0:
            margin_pct = ((default_price - unit_cost) / default_price) * 100
            margin_text = f"{margin_pct:.1f}%"
        else:
            margin_text = "--"

        self._product_cost_summary_label.setText(
            f"Extras {len(self._product_pricing_components)} | ${extras_total:,.2f} | "
            f"Unit Cost ${unit_cost:,.2f} | Margin {margin_text}"
        )

    def _on_photo_path_changed(self, value: str) -> None:
        self._update_photo_preview(value)

    def _update_photo_preview(self, value: str) -> None:
        if not hasattr(self, "_product_photo_preview"):
            return

        resolved = order_service.resolve_product_photo(value.strip()) if value else None
        self._current_photo_path = resolved
        if resolved and resolved.exists():
            pixmap = QPixmap(str(resolved))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._product_photo_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._product_photo_preview.setPixmap(scaled)
                self._product_photo_preview.setText("")
                self._product_photo_preview.setToolTip(str(resolved))
                if hasattr(self, "_open_photo_button"):
                    self._open_photo_button.setEnabled(True)
                if hasattr(self, "_photo_hint_label"):
                    self._photo_hint_label.setText(f"Currently loaded from:\n{resolved}")
                return

        self._product_photo_preview.setPixmap(QPixmap())
        self._product_photo_preview.setText("No Preview")
        self._product_photo_preview.setToolTip("")
        if hasattr(self, "_open_photo_button"):
            self._open_photo_button.setEnabled(False)
        if hasattr(self, "_photo_hint_label"):
            self._photo_hint_label.setText(_PHOTO_HINT_DEFAULT)
        self._current_photo_path = None

    def _handle_open_photo(self) -> None:
        if not self._current_photo_path:
            return
        if not self._current_photo_path.exists():
            QMessageBox.warning(self, "Product Manager", "Image file is missing on disk.")
            self._update_photo_preview("")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._current_photo_path)))

    def _handle_browse_photo(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Product Photo",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if filename:
            self._product_photo_input.setText(filename)

    def _notify_products_changed(self, select_sku: Optional[str]) -> None:
        if self._on_products_changed is not None:
            self._on_products_changed(select_sku)

    @staticmethod
    def _clone_components(components: Iterable[CostComponent] | None) -> List[CostComponent]:
        if components is None:
            return []
        return [CostComponent(label=component.label, amount=component.amount) for component in components]

    def _product_alert_text(self, product: object) -> str:
        if not isinstance(product, Product):
            return ""
        parts: List[str] = []
        status = (product.status or "").strip()

        if status and status.lower() in {"discontinued", "out of stock"}:
            parts.append(status.title())

        if not product.is_complete:
            parts.append("Needs Details")

        if product.inventory_count <= self._app_settings.low_inventory_threshold:
            parts.append("Low Inventory")

        if not parts:
            return "Ready"

        seen: set[str] = set()
        unique_parts: List[str] = []
        for part in parts:
            upper_part = part.upper()
            if upper_part in seen:
                continue
            seen.add(upper_part)
            unique_parts.append(part)
        return ", ".join(unique_parts)

    def _is_product_complete(self, description: str, photo_path: str) -> bool:
        return bool(description.strip()) and bool(photo_path.strip())

    def _configure_table(self, table: QTableView) -> None:
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def _show_message(self, message: str) -> None:
        QMessageBox.information(self, "Product Manager", message)

    @staticmethod
    def _days_until_stockout(row: object) -> str:
        value = getattr(row, "days_until_stockout", None)
        if value is None:
            return "Infinity"
        return str(value)


class _NewProductDialog(QDialog):
    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Product")
        self._sku: str = ""
        self._name: str = ""

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.setLayout(layout)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        self._sku_input = QLineEdit()
        form_layout.addRow("SKU", self._sku_input)

        self._name_input = QLineEdit()
        form_layout.addRow("Name", self._name_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def sku(self) -> str:
        return self._sku

    @property
    def name(self) -> str:
        return self._name

    def _on_accept(self) -> None:
        sku = self._sku_input.text().strip().upper()
        if not sku:
            QMessageBox.warning(self, "New Product", "SKU is required.")
            return

        name = self._name_input.text().strip() or sku

        self._sku = sku
        self._name = name
        self.accept()
