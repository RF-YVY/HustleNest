from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Callable, List, Optional, cast

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
    QTableView,
    QTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..data import goal_repository
from ..models.order_models import (
    BusinessGoal,
    CRMContact,
    CRMInteraction,
    DocumentRecord,
    Expense,
    LossRecord,
    Material,
    MaterialTransaction,
    RecurringExpense,
    Vendor,
)
from ..services import (
    crm_service,
    document_service,
    expense_service,
    goal_service,
    inventory_service,
    loss_service,
    material_service,
    order_service,
    vendor_service,
)
from ..viewmodels.table_models import ListTableModel


def _format_date(value: Optional[date], fmt: str = "%Y-%m-%d") -> str:
    return value.strftime(fmt) if value else ""


def _format_document_entity(record: DocumentRecord) -> str:
    if record.entity_id is None:
        return record.entity_type
    return f"{record.entity_type} #{record.entity_id}"


class BusinessToolsDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Business Tools")
        self.resize(1280, 840)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        self._build_losses_tab()
        self._build_materials_tab()
        self._build_expenses_tab()
        self._build_crm_tab()
        self._build_documents_tab()
        self._build_goals_tab()

        self._refresh_losses()
        self._refresh_materials()
        self._refresh_expenses()
        self._refresh_recurring()
        self._refresh_contacts()
        self._refresh_documents()
        self._refresh_goals()

    # Losses tab -------------------------------------------------------------
    def _build_losses_tab(self) -> None:
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        container.setLayout(layout)

        self._loss_model = ListTableModel(
            (
                ("Date", lambda row: getattr(row, "loss_date", date.min).strftime("%Y-%m-%d")),
                ("Category", lambda row: getattr(row, "category", "")),
                ("Amount", lambda row: f"${getattr(row, 'amount', 0.0):,.2f}"),
                ("Product", lambda row: getattr(row, "product_name", "")),
                ("Material", lambda row: getattr(row, "material_name", "")),
                ("Quantity", lambda row: f"{getattr(row, 'quantity', 0.0):g}"),
                ("Notes", lambda row: getattr(row, "description", "")),
            )
        )
        self._loss_table = QTableView()
        self._loss_table.setModel(self._loss_model)
        self._configure_table(self._loss_table)
        self._loss_table.selectionModel().currentChanged.connect(self._on_loss_selected)
        layout.addWidget(self._loss_table, stretch=3)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_group = QWidget()
        form_group.setLayout(form)
        layout.addWidget(form_group, stretch=2)

        self._loss_date_input = QDateEdit()
        self._loss_date_input.setCalendarPopup(True)
        self._loss_date_input.setDate(QDate.currentDate())
        form.addRow("Loss Date", self._loss_date_input)

        self._loss_amount_input = QDoubleSpinBox()
        self._loss_amount_input.setRange(0.0, 1_000_000_000.0)
        self._loss_amount_input.setPrefix("$")
        self._loss_amount_input.setDecimals(2)
        form.addRow("Amount", self._loss_amount_input)

        self._loss_category_combo = QComboBox()
        self._loss_category_combo.setEditable(True)
        loss_category_line_edit = self._loss_category_combo.lineEdit()
        if loss_category_line_edit is not None:
            loss_category_line_edit.setPlaceholderText("Select or type a category")
        form.addRow("Category", self._loss_category_combo)

        self._loss_description_input = QLineEdit()
        form.addRow("Short Note", self._loss_description_input)

        self._loss_details_input = QTextEdit()
        self._loss_details_input.setPlaceholderText("Internal notes about this loss entry")
        form.addRow("Details", self._loss_details_input)

        self._loss_product_checkbox = QCheckBox("Product Loss")
        self._loss_product_checkbox.toggled.connect(self._on_loss_product_toggle)
        form.addRow("Affects Inventory", self._loss_product_checkbox)

        self._loss_product_combo = QComboBox()
        self._loss_product_combo.setEditable(False)
        form.addRow("Product", self._loss_product_combo)

        self._loss_material_combo = QComboBox()
        self._loss_material_combo.setEditable(False)
        form.addRow("Material", self._loss_material_combo)

        self._loss_quantity_input = QDoubleSpinBox()
        self._loss_quantity_input.setDecimals(3)
        self._loss_quantity_input.setRange(0.0, 1_000_000.0)
        form.addRow("Quantity", self._loss_quantity_input)

        self._loss_unit_input = QLineEdit()
        form.addRow("Unit", self._loss_unit_input)

        self._loss_recorded_by_input = QLineEdit()
        form.addRow("Recorded By", self._loss_recorded_by_input)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self._loss_new_button = QPushButton("New")
        self._loss_new_button.clicked.connect(self._reset_loss_form)
        buttons.addWidget(self._loss_new_button)
        self._loss_save_button = QPushButton("Save Loss")
        self._loss_save_button.clicked.connect(self._save_loss)
        buttons.addWidget(self._loss_save_button)
        self._loss_delete_button = QPushButton("Delete Selected")
        self._loss_delete_button.clicked.connect(self._delete_loss)
        buttons.addWidget(self._loss_delete_button)
        buttons.addStretch(1)

        self._current_loss_id: Optional[int] = None
        self._tab_widget.addTab(container, "Losses")

    def _refresh_losses(self) -> None:
        losses = loss_service.list_losses(limit=500)
        self._loss_model.update_rows(losses)
        self._load_product_material_options()
        self._load_loss_categories()
        if self._current_loss_id is None:
            self._loss_table.clearSelection()

    def _load_product_material_options(self) -> None:
        products = order_service.list_products()
        current_product = self._loss_product_combo.currentData()
        self._loss_product_combo.clear()
        self._loss_product_combo.addItem("-- None --", None)
        for product in products:
            self._loss_product_combo.addItem(f"{product.sku} - {product.name}", product.id)
        if current_product:
            index = self._loss_product_combo.findData(current_product)
            if index >= 0:
                self._loss_product_combo.setCurrentIndex(index)

        materials = material_service.list_materials()
        current_material = self._loss_material_combo.currentData()
        self._loss_material_combo.clear()
        self._loss_material_combo.addItem("-- None --", None)
        for material in materials:
            label = f"{material.sku} - {material.name}" if material.sku else material.name
            self._loss_material_combo.addItem(label, material.id)
        if current_material:
            index = self._loss_material_combo.findData(current_material)
            if index >= 0:
                self._loss_material_combo.setCurrentIndex(index)

    def _reset_loss_form(self) -> None:
        self._current_loss_id = None
        self._loss_date_input.setDate(QDate.currentDate())
        self._loss_amount_input.setValue(0.0)
        if self._loss_category_combo.count() > 0:
            self._loss_category_combo.setCurrentIndex(0)
        if self._loss_category_combo.isEditable():
            self._loss_category_combo.setEditText("")
        self._loss_description_input.clear()
        self._loss_details_input.clear()
        self._loss_product_checkbox.setChecked(False)
        self._loss_product_combo.setCurrentIndex(0)
        self._loss_material_combo.setCurrentIndex(0)
        self._loss_quantity_input.setValue(0.0)
        self._loss_unit_input.clear()
        self._loss_recorded_by_input.clear()
        self._loss_table.clearSelection()

    def _on_loss_product_toggle(self, state: bool) -> None:
        self._loss_product_combo.setEnabled(state)

    def _collect_loss_from_form(self) -> LossRecord:
        loss_date = cast(date, self._loss_date_input.date().toPython())
        record = LossRecord(
            id=self._current_loss_id,
            amount=self._loss_amount_input.value(),
            loss_date=loss_date,
            category=self._loss_category_combo.currentText().strip(),
            description=self._loss_description_input.text().strip(),
            details=self._loss_details_input.toPlainText().strip(),
            is_product_loss=self._loss_product_checkbox.isChecked(),
            recorded_by=self._loss_recorded_by_input.text().strip(),
            quantity=self._loss_quantity_input.value(),
            unit=self._loss_unit_input.text().strip(),
            order_id=None,
            order_item_id=None,
            product_id=self._loss_product_combo.currentData(),
            material_id=self._loss_material_combo.currentData(),
        )
        return record

    def _save_loss(self) -> None:
        try:
            record = self._collect_loss_from_form()
            if record.amount <= 0:
                raise ValueError("Loss amount must be greater than zero.")
            if not record.category:
                raise ValueError("Category is required.")
            loss_id = loss_service.save_loss(record)
            self._current_loss_id = loss_id
            self._refresh_losses()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to save loss", str(exc))

    def _delete_loss(self) -> None:
        if self._current_loss_id is None:
            QMessageBox.information(self, "Delete loss", "Select an entry to delete.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete loss",
            "Delete the selected loss entry?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            loss_service.delete_loss(self._current_loss_id)
            self._current_loss_id = None
            self._refresh_losses()
            self._reset_loss_form()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to delete loss", str(exc))

    def _on_loss_selected(self, current, _previous) -> None:
        if not current.isValid():
            return
        row = current.row()
        loss = cast(LossRecord, self._loss_model._rows[row])
        self._current_loss_id = loss.id
        self._loss_date_input.setDate(QDate(loss.loss_date.year, loss.loss_date.month, loss.loss_date.day))
        self._loss_amount_input.setValue(loss.amount)
        if loss.category:
            idx = self._loss_category_combo.findText(loss.category)
            if idx >= 0:
                self._loss_category_combo.setCurrentIndex(idx)
            else:
                self._loss_category_combo.setEditText(loss.category)
        else:
            if self._loss_category_combo.count() > 0:
                self._loss_category_combo.setCurrentIndex(0)
            if self._loss_category_combo.isEditable():
                self._loss_category_combo.setEditText("")
        self._loss_description_input.setText(loss.description)
        self._loss_details_input.setPlainText(loss.details)
        self._loss_product_checkbox.setChecked(loss.is_product_loss)
        self._loss_quantity_input.setValue(loss.quantity)
        self._loss_unit_input.setText(loss.unit)
        self._loss_recorded_by_input.setText(loss.recorded_by)
        product_index = self._loss_product_combo.findData(loss.product_id)
        self._loss_product_combo.setCurrentIndex(max(0, product_index))
        material_index = self._loss_material_combo.findData(loss.material_id)
        self._loss_material_combo.setCurrentIndex(max(0, material_index))

    # Materials tab ---------------------------------------------------------
    def _build_materials_tab(self) -> None:
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        container.setLayout(layout)

        self._materials_model = ListTableModel(
            (
                ("SKU", lambda row: cast(Material, row).sku),
                ("Name", lambda row: cast(Material, row).name),
                ("Category", lambda row: cast(Material, row).category),
                ("Qty", lambda row: f"{cast(Material, row).quantity_on_hand:g}"),
                ("Unit", lambda row: cast(Material, row).unit_of_measure),
                ("Reorder", lambda row: f"{cast(Material, row).reorder_point:g}"),
                ("Cost", lambda row: f"${cast(Material, row).cost_per_unit:,.2f}"),
                ("Vendor", lambda row: self._material_vendor_name(cast(Material, row))),
            )
        )
        self._materials_table = QTableView()
        self._materials_table.setModel(self._materials_model)
        self._configure_table(self._materials_table)
        self._materials_table.selectionModel().currentChanged.connect(self._on_material_selected)
        layout.addWidget(self._materials_table, stretch=3)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_group = QWidget()
        form_group.setLayout(form)
        layout.addWidget(form_group, stretch=2)

        self._material_sku_input = QLineEdit()
        form.addRow("SKU", self._material_sku_input)

        self._material_name_input = QLineEdit()
        form.addRow("Name", self._material_name_input)

        self._material_category_combo = QComboBox()
        self._material_category_combo.setEditable(True)
        form.addRow("Category", self._material_category_combo)

        self._material_description_input = QLineEdit()
        form.addRow("Description", self._material_description_input)

        self._material_unit_input = QLineEdit()
        form.addRow("Unit", self._material_unit_input)

        self._material_quantity_input = QDoubleSpinBox()
        self._material_quantity_input.setDecimals(3)
        self._material_quantity_input.setRange(0.0, 1_000_000.0)
        form.addRow("Quantity", self._material_quantity_input)

        self._material_reorder_input = QDoubleSpinBox()
        self._material_reorder_input.setDecimals(3)
        self._material_reorder_input.setRange(0.0, 1_000_000.0)
        form.addRow("Reorder Point", self._material_reorder_input)

        self._material_cost_input = QDoubleSpinBox()
        self._material_cost_input.setDecimals(4)
        self._material_cost_input.setRange(0.0, 1_000_000.0)
        self._material_cost_input.setPrefix("$")
        form.addRow("Unit Cost", self._material_cost_input)

        self._material_vendor_combo = QComboBox()
        self._material_vendor_combo.setEditable(True)
        form.addRow("Vendor", self._wrap_vendor_combo(self._material_vendor_combo))

        self._material_lead_time_input = QSpinBox()
        self._material_lead_time_input.setRange(0, 365)
        form.addRow("Lead Time (days)", self._material_lead_time_input)

        self._material_notes_input = QTextEdit()
        form.addRow("Notes", self._material_notes_input)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self._material_new_button = QPushButton("New")
        self._material_new_button.clicked.connect(self._reset_material_form)
        buttons.addWidget(self._material_new_button)
        self._material_save_button = QPushButton("Save Material")
        self._material_save_button.clicked.connect(self._save_material)
        buttons.addWidget(self._material_save_button)
        self._material_adjust_button = QPushButton("Adjust Quantity")
        self._material_adjust_button.clicked.connect(self._adjust_material)
        buttons.addWidget(self._material_adjust_button)
        self._material_transactions_button = QPushButton("View Transactions")
        self._material_transactions_button.clicked.connect(self._show_material_transactions)
        buttons.addWidget(self._material_transactions_button)
        self._material_delete_button = QPushButton("Delete")
        self._material_delete_button.clicked.connect(self._delete_material)
        buttons.addWidget(self._material_delete_button)
        buttons.addStretch(1)

        self._current_material_id: Optional[int] = None
        self._tab_widget.addTab(container, "Materials")

    def _refresh_materials(self) -> None:
        materials = material_service.list_materials()
        self._materials_model.update_rows(materials)
        self._load_material_categories()
        if hasattr(self, "_loss_category_combo"):
            self._load_loss_categories(preserve=self._loss_category_combo.currentText().strip())
        if hasattr(self, "_expense_category_combo") and hasattr(self, "_recurring_category_combo"):
            self._load_expense_categories(
                preserve_expense=self._expense_category_combo.currentText().strip(),
                preserve_recurring=self._recurring_category_combo.currentText().strip(),
            )
        self._load_vendor_options()
        if self._current_material_id is None:
            self._materials_table.clearSelection()

    def _material_vendor_name(self, material: Material) -> str:
        if material.vendor_id is None:
            return ""
        vendor = vendor_service.get_vendor(material.vendor_id)
        return vendor.name if vendor else ""

    def _load_vendor_options(self) -> None:
        vendors = vendor_service.list_vendors()
        current_text = self._material_vendor_combo.currentText()
        self._material_vendor_combo.clear()
        self._material_vendor_combo.addItem("-- None --", None)
        for vendor in vendors:
            self._material_vendor_combo.addItem(vendor.name, vendor.id)
        if current_text:
            idx = self._material_vendor_combo.findText(current_text)
            if idx >= 0:
                self._material_vendor_combo.setCurrentIndex(idx)

    def _load_material_categories(self, preserve: Optional[str] = None) -> None:
        categories = material_service.list_categories()
        current_text = preserve if preserve is not None else self._material_category_combo.currentText().strip()
        self._material_category_combo.blockSignals(True)
        self._material_category_combo.clear()
        self._material_category_combo.addItem("-- None --", "")
        for category in categories:
            self._material_category_combo.addItem(category, category)
        if current_text:
            idx = self._material_category_combo.findText(current_text)
            if idx >= 0:
                self._material_category_combo.setCurrentIndex(idx)
            else:
                self._material_category_combo.setEditText(current_text)
        else:
            self._material_category_combo.setCurrentIndex(0)
            self._material_category_combo.setEditText("")
        self._material_category_combo.blockSignals(False)

    @staticmethod
    def _update_editable_combo(combo: QComboBox, values: List[str], *, preserve: Optional[str] = None) -> None:
        current_text = preserve if preserve is not None else combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        for value in values:
            combo.addItem(value)
        if current_text:
            idx = combo.findText(current_text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                if combo.isEditable():
                    combo.setEditText(current_text)
        else:
            if combo.count() > 0:
                combo.setCurrentIndex(0)
            line_edit = combo.lineEdit()
            if combo.isEditable() and line_edit is not None:
                line_edit.clear()
        combo.blockSignals(False)

    def _load_loss_categories(self, preserve: Optional[str] = None) -> None:
        if not hasattr(self, "_loss_category_combo"):
            return
        category_set = set(loss_service.list_categories())
        category_set.update(material_service.list_categories())
        categories = sorted((value for value in category_set if value), key=lambda value: value.casefold())
        self._update_editable_combo(self._loss_category_combo, categories, preserve=preserve)

    def _load_expense_categories(
        self,
        *,
        preserve_expense: Optional[str] = None,
        preserve_recurring: Optional[str] = None,
    ) -> None:
        if not hasattr(self, "_expense_category_combo") or not hasattr(self, "_recurring_category_combo"):
            return
        category_set = set(expense_service.list_categories())
        category_set.update(material_service.list_categories())
        categories = sorted((value for value in category_set if value), key=lambda value: value.casefold())
        self._update_editable_combo(self._expense_category_combo, categories, preserve=preserve_expense)
        self._update_editable_combo(self._recurring_category_combo, categories, preserve=preserve_recurring)

    def _reset_material_form(self) -> None:
        self._current_material_id = None
        self._material_sku_input.clear()
        self._material_name_input.clear()
        self._material_category_combo.setCurrentIndex(0)
        self._material_category_combo.setEditText("")
        self._material_description_input.clear()
        self._material_unit_input.clear()
        self._material_quantity_input.setValue(0.0)
        self._material_reorder_input.setValue(0.0)
        self._material_cost_input.setValue(0.0)
        self._material_vendor_combo.setCurrentIndex(0)
        self._material_notes_input.clear()
        self._material_lead_time_input.setValue(0)
        self._materials_table.clearSelection()

    def _collect_material_from_form(self) -> Material:
        vendor_id = self._material_vendor_combo.currentData()
        if vendor_id is None:
            vendor_text = self._material_vendor_combo.currentText().strip()
            if vendor_text and vendor_text != "-- None --":
                vendor = vendor_service.ensure_vendor(vendor_text)
                vendor_id = vendor.id
                self._refresh_vendor_lists()
                if vendor_id is not None:
                    index = self._material_vendor_combo.findData(vendor_id)
                    if index >= 0:
                        self._material_vendor_combo.setCurrentIndex(index)
        material = Material(
            id=self._current_material_id,
            sku=self._material_sku_input.text().strip(),
            name=self._material_name_input.text().strip(),
            category=self._material_category_combo.currentText().strip(),
            description=self._material_description_input.text().strip(),
            unit_of_measure=self._material_unit_input.text().strip(),
            quantity_on_hand=self._material_quantity_input.value(),
            reorder_point=self._material_reorder_input.value(),
            cost_per_unit=self._material_cost_input.value(),
            vendor_id=vendor_id,
            last_restocked=None,
            notes=self._material_notes_input.toPlainText().strip(),
            lead_time_days=self._material_lead_time_input.value(),
            archived=False,
        )
        return material

    def _save_material(self) -> None:
        try:
            material = self._collect_material_from_form()
            if not material.name:
                raise ValueError("Name is required")
            material_id = material_service.save_material(material)
            self._current_material_id = material_id
            self._refresh_materials()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to save material", str(exc))

    def _delete_material(self) -> None:
        if self._current_material_id is None:
            QMessageBox.information(self, "Delete material", "Select a material to delete.")
            return
        confirm = QMessageBox.question(self, "Delete material", "Delete the selected material?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            material_service.delete_material(self._current_material_id)
            self._current_material_id = None
            self._refresh_materials()
            self._reset_material_form()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to delete material", str(exc))

    def _adjust_material(self) -> None:
        if self._current_material_id is None:
            QMessageBox.information(self, "Adjust quantity", "Select a material to adjust.")
            return
        delta, ok = _prompt_for_double(self, "Quantity Adjustment", "Enter adjustment amount (positive adds, negative removes):")
        if not ok or abs(delta) < 1e-9:
            return
        material_service.record_adjustment(
            self._current_material_id,
            delta,
            reason="Manual adjustment",
            reference_type="manual",
            created_by="BusinessTools",
        )
        self._refresh_materials()

    def _on_material_selected(self, current, _previous) -> None:
        if not current.isValid():
            return
        material = cast(Material, self._materials_model._rows[current.row()])
        self._current_material_id = material.id
        self._material_sku_input.setText(material.sku)
        self._material_name_input.setText(material.name)
        if material.category:
            idx = self._material_category_combo.findText(material.category)
            if idx >= 0:
                self._material_category_combo.setCurrentIndex(idx)
            else:
                self._material_category_combo.setEditText(material.category)
        else:
            self._material_category_combo.setCurrentIndex(0)
            self._material_category_combo.setEditText("")
        self._material_description_input.setText(material.description)
        self._material_unit_input.setText(material.unit_of_measure)
        self._material_quantity_input.setValue(material.quantity_on_hand)
        self._material_reorder_input.setValue(material.reorder_point)
        self._material_cost_input.setValue(material.cost_per_unit)
        vendor_index = self._material_vendor_combo.findData(material.vendor_id)
        if vendor_index < 0 and material.vendor_id is not None:
            vendor = vendor_service.get_vendor(material.vendor_id)
            if vendor:
                self._material_vendor_combo.addItem(vendor.name, vendor.id)
                vendor_index = self._material_vendor_combo.count() - 1
        self._material_vendor_combo.setCurrentIndex(max(0, vendor_index))
        self._material_notes_input.setPlainText(material.notes)
        self._material_lead_time_input.setValue(material.lead_time_days)

    def _show_material_transactions(self) -> None:
        if self._current_material_id is None:
            QMessageBox.information(self, "Material transactions", "Select a material first.")
            return
        material = material_service.get_material(self._current_material_id)
        if material is None:
            QMessageBox.information(self, "Material transactions", "Could not load the selected material.")
            return
        dialog = MaterialTransactionsDialog(self, material_id=material.id, material_name=material.name)
        dialog.exec()

    # Expenses tab ----------------------------------------------------------
    def _build_expenses_tab(self) -> None:
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        container.setLayout(layout)

        self._expense_model = ListTableModel(
            (
                ("Date", lambda row: cast(Expense, row).expense_date.strftime("%Y-%m-%d")),
                ("Category", lambda row: cast(Expense, row).category),
                ("Amount", lambda row: f"${cast(Expense, row).amount:,.2f}"),
                ("Vendor", lambda row: self._expense_vendor_name(cast(Expense, row))),
                ("Payment", lambda row: cast(Expense, row).payment_method),
                ("Notes", lambda row: cast(Expense, row).notes),
            )
        )
        self._expense_table = QTableView()
        self._expense_table.setModel(self._expense_model)
        self._configure_table(self._expense_table)
        self._expense_table.selectionModel().currentChanged.connect(self._on_expense_selected)
        layout.addWidget(self._expense_table, stretch=3)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_group = QWidget()
        form_group.setLayout(form)
        layout.addWidget(form_group, stretch=2)

        self._expense_date_input = QDateEdit()
        self._expense_date_input.setCalendarPopup(True)
        self._expense_date_input.setDate(QDate.currentDate())
        form.addRow("Date", self._expense_date_input)

        self._expense_category_combo = QComboBox()
        self._expense_category_combo.setEditable(True)
        expense_category_line_edit = self._expense_category_combo.lineEdit()
        if expense_category_line_edit is not None:
            expense_category_line_edit.setPlaceholderText("Select or type a category")
        form.addRow("Category", self._expense_category_combo)

        self._expense_amount_input = QDoubleSpinBox()
        self._expense_amount_input.setPrefix("$")
        self._expense_amount_input.setDecimals(2)
        self._expense_amount_input.setRange(0.0, 1_000_000_000.0)
        form.addRow("Amount", self._expense_amount_input)

        self._expense_vendor_combo = QComboBox()
        self._expense_vendor_combo.setEditable(True)
        form.addRow("Vendor", self._wrap_vendor_combo(self._expense_vendor_combo))

        self._expense_payment_input = QLineEdit()
        form.addRow("Payment Method", self._expense_payment_input)

        self._expense_notes_input = QTextEdit()
        form.addRow("Notes", self._expense_notes_input)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self._expense_new_button = QPushButton("New")
        self._expense_new_button.clicked.connect(self._reset_expense_form)
        buttons.addWidget(self._expense_new_button)
        self._expense_save_button = QPushButton("Save Expense")
        self._expense_save_button.clicked.connect(self._save_expense)
        buttons.addWidget(self._expense_save_button)
        self._expense_delete_button = QPushButton("Delete")
        self._expense_delete_button.clicked.connect(self._delete_expense)
        buttons.addWidget(self._expense_delete_button)
        buttons.addStretch(1)

        recurring_label = QLabel("Recurring Bills")
        recurring_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(recurring_label)

        self._recurring_model = ListTableModel(
            (
                ("Vendor", lambda row: self._recurring_vendor_name(cast(RecurringExpense, row))),
                ("Category", lambda row: cast(RecurringExpense, row).category),
                ("Amount", lambda row: f"${cast(RecurringExpense, row).amount:,.2f}"),
                ("Frequency", lambda row: cast(RecurringExpense, row).frequency),
                ("Next", lambda row: _format_date(cast(RecurringExpense, row).next_occurrence)),
            )
        )
        self._recurring_table = QTableView()
        self._recurring_table.setModel(self._recurring_model)
        self._configure_table(self._recurring_table)
        self._recurring_table.selectionModel().currentChanged.connect(self._on_recurring_selected)
        layout.addWidget(self._recurring_table, stretch=2)

        recurring_buttons = QHBoxLayout()
        layout.addLayout(recurring_buttons)
        self._recurring_new_button = QPushButton("New Recurring")
        self._recurring_new_button.clicked.connect(self._reset_recurring_form)
        recurring_buttons.addWidget(self._recurring_new_button)
        self._recurring_save_button = QPushButton("Save Recurring")
        self._recurring_save_button.clicked.connect(self._save_recurring)
        recurring_buttons.addWidget(self._recurring_save_button)
        self._recurring_delete_button = QPushButton("Delete Recurring")
        self._recurring_delete_button.clicked.connect(self._delete_recurring)
        recurring_buttons.addWidget(self._recurring_delete_button)
        recurring_buttons.addStretch(1)

        recurring_form = QFormLayout()
        recurring_group = QWidget()
        recurring_group.setLayout(recurring_form)
        layout.addWidget(recurring_group, stretch=2)

        self._recurring_vendor_combo = QComboBox()
        self._recurring_vendor_combo.setEditable(True)
        recurring_form.addRow("Vendor", self._wrap_vendor_combo(self._recurring_vendor_combo))

        self._recurring_category_combo = QComboBox()
        self._recurring_category_combo.setEditable(True)
        recurring_category_line_edit = self._recurring_category_combo.lineEdit()
        if recurring_category_line_edit is not None:
            recurring_category_line_edit.setPlaceholderText("Select or type a category")
        recurring_form.addRow("Category", self._recurring_category_combo)

        self._recurring_amount_input = QDoubleSpinBox()
        self._recurring_amount_input.setPrefix("$")
        self._recurring_amount_input.setDecimals(2)
        self._recurring_amount_input.setRange(0.0, 1_000_000_000.0)
        recurring_form.addRow("Amount", self._recurring_amount_input)

        self._recurring_frequency_input = QLineEdit()
        recurring_form.addRow("Frequency", self._recurring_frequency_input)

        self._recurring_start_input = QDateEdit()
        self._recurring_start_input.setCalendarPopup(True)
        self._recurring_start_input.setDate(QDate.currentDate())
        recurring_form.addRow("Start Date", self._recurring_start_input)

        self._recurring_next_input = QDateEdit()
        self._recurring_next_input.setCalendarPopup(True)
        self._recurring_next_input.setDate(QDate.currentDate())
        recurring_form.addRow("Next Occurrence", self._recurring_next_input)

        self._recurring_auto_checkbox = QCheckBox("Auto-record expense when due")
        recurring_form.addRow("Automation", self._recurring_auto_checkbox)

        self._recurring_notes_input = QTextEdit()
        recurring_form.addRow("Notes", self._recurring_notes_input)

        self._current_expense_id: Optional[int] = None
        self._current_recurring_id: Optional[int] = None
        self._tab_widget.addTab(container, "Expenses")

    def _expense_vendor_name(self, expense: Expense) -> str:
        if expense.vendor_id is None:
            return ""
        vendor = vendor_service.get_vendor(expense.vendor_id)
        return vendor.name if vendor else ""

    def _recurring_vendor_name(self, recurring: RecurringExpense) -> str:
        if recurring.vendor_id is None:
            return ""
        vendor = vendor_service.get_vendor(recurring.vendor_id)
        return vendor.name if vendor else ""

    def _refresh_expenses(self) -> None:
        expenses = expense_service.list_expenses(limit=500)
        self._expense_model.update_rows(expenses)
        self._load_vendor_combo(self._expense_vendor_combo)
        self._load_expense_categories()
        if self._current_expense_id is None:
            self._expense_table.clearSelection()

    def _refresh_recurring(self) -> None:
        recurring = expense_service.list_recurring_expenses()
        self._recurring_model.update_rows(recurring)
        self._load_vendor_combo(self._recurring_vendor_combo)
        self._load_expense_categories()
        if self._current_recurring_id is None:
            self._recurring_table.clearSelection()

    def _load_vendor_combo(self, combo: QComboBox) -> None:
        vendors = vendor_service.list_vendors()
        current_text = combo.currentText()
        combo.clear()
        combo.addItem("-- None --", None)
        for vendor in vendors:
            combo.addItem(vendor.name, vendor.id)
        if current_text:
            idx = combo.findText(current_text)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _reset_expense_form(self) -> None:
        self._current_expense_id = None
        self._expense_date_input.setDate(QDate.currentDate())
        if self._expense_category_combo.count() > 0:
            self._expense_category_combo.setCurrentIndex(0)
        if self._expense_category_combo.isEditable():
            line_edit = self._expense_category_combo.lineEdit()
            if line_edit is not None:
                line_edit.clear()
        self._expense_amount_input.setValue(0.0)
        self._expense_vendor_combo.setCurrentIndex(0)
        self._expense_payment_input.clear()
        self._expense_notes_input.clear()
        self._expense_table.clearSelection()

    def _collect_expense_from_form(self) -> Expense:
        vendor_id = self._expense_vendor_combo.currentData()
        if vendor_id is None:
            vendor_text = self._expense_vendor_combo.currentText().strip()
            if vendor_text and vendor_text != "-- None --":
                vendor = vendor_service.ensure_vendor(vendor_text)
                vendor_id = vendor.id
                self._refresh_vendor_lists()
                if vendor_id is not None:
                    index = self._expense_vendor_combo.findData(vendor_id)
                    if index >= 0:
                        self._expense_vendor_combo.setCurrentIndex(index)
        expense = Expense(
            id=self._current_expense_id,
            category=self._expense_category_combo.currentText().strip(),
            amount=self._expense_amount_input.value(),
            expense_date=cast(date, self._expense_date_input.date().toPython()),
            description=self._expense_notes_input.toPlainText().strip(),
            payment_method=self._expense_payment_input.text().strip(),
            vendor_id=vendor_id,
            is_recurring=False,
            recurring_id=None,
            document_id=None,
            tags=[],
            notes=self._expense_notes_input.toPlainText().strip(),
        )
        return expense

    def _save_expense(self) -> None:
        try:
            expense = self._collect_expense_from_form()
            if not expense.category:
                raise ValueError("Category is required")
            if expense.amount <= 0:
                raise ValueError("Amount must be greater than zero")
            expense_id = expense_service.save_expense(expense)
            self._current_expense_id = expense_id
            self._refresh_expenses()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to save expense", str(exc))

    def _delete_expense(self) -> None:
        if self._current_expense_id is None:
            QMessageBox.information(self, "Delete expense", "Select an expense to delete.")
            return
        confirm = QMessageBox.question(self, "Delete expense", "Delete the selected expense?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        expense_service.delete_expense(self._current_expense_id)
        self._current_expense_id = None
        self._refresh_expenses()
        self._reset_expense_form()

    def _on_expense_selected(self, current, _previous) -> None:
        if not current.isValid():
            return
        expense = cast(Expense, self._expense_model._rows[current.row()])
        self._current_expense_id = expense.id
        self._expense_date_input.setDate(QDate(expense.expense_date.year, expense.expense_date.month, expense.expense_date.day))
        if expense.category:
            idx = self._expense_category_combo.findText(expense.category)
            if idx >= 0:
                self._expense_category_combo.setCurrentIndex(idx)
            else:
                self._expense_category_combo.setEditText(expense.category)
        else:
            if self._expense_category_combo.count() > 0:
                self._expense_category_combo.setCurrentIndex(0)
            line_edit = self._expense_category_combo.lineEdit()
            if self._expense_category_combo.isEditable() and line_edit is not None:
                line_edit.clear()
        self._expense_amount_input.setValue(expense.amount)
        vendor_index = self._expense_vendor_combo.findData(expense.vendor_id)
        self._expense_vendor_combo.setCurrentIndex(max(0, vendor_index))
        self._expense_payment_input.setText(expense.payment_method)
        self._expense_notes_input.setPlainText(expense.notes)

    def _reset_recurring_form(self) -> None:
        self._current_recurring_id = None
        self._recurring_vendor_combo.setCurrentIndex(0)
        if self._recurring_category_combo.count() > 0:
            self._recurring_category_combo.setCurrentIndex(0)
        if self._recurring_category_combo.isEditable():
            line_edit = self._recurring_category_combo.lineEdit()
            if line_edit is not None:
                line_edit.clear()
        self._recurring_amount_input.setValue(0.0)
        self._recurring_frequency_input.setText("Monthly")
        self._recurring_start_input.setDate(QDate.currentDate())
        self._recurring_next_input.setDate(QDate.currentDate())
        self._recurring_auto_checkbox.setChecked(False)
        self._recurring_notes_input.clear()
        self._recurring_table.clearSelection()

    def _collect_recurring_from_form(self) -> RecurringExpense:
        vendor_id = self._recurring_vendor_combo.currentData()
        if vendor_id is None:
            vendor_text = self._recurring_vendor_combo.currentText().strip()
            if vendor_text and vendor_text != "-- None --":
                vendor = vendor_service.ensure_vendor(vendor_text)
                vendor_id = vendor.id
                self._refresh_vendor_lists()
                if vendor_id is not None:
                    index = self._recurring_vendor_combo.findData(vendor_id)
                    if index >= 0:
                        self._recurring_vendor_combo.setCurrentIndex(index)
        recurring = RecurringExpense(
            id=self._current_recurring_id,
            category=self._recurring_category_combo.currentText().strip(),
            amount=self._recurring_amount_input.value(),
            frequency=self._recurring_frequency_input.text().strip() or "Monthly",
            start_date=cast(date, self._recurring_start_input.date().toPython()),
            end_date=None,
            day_of_month=None,
            next_occurrence=cast(date, self._recurring_next_input.date().toPython()),
            auto_record=self._recurring_auto_checkbox.isChecked(),
            notes=self._recurring_notes_input.toPlainText().strip(),
            vendor_id=vendor_id,
        )
        return recurring

    def _save_recurring(self) -> None:
        try:
            recurring = self._collect_recurring_from_form()
            if not recurring.category:
                raise ValueError("Category is required")
            if recurring.amount <= 0:
                raise ValueError("Amount must be greater than zero")
            recurring_id = expense_service.save_recurring_expense(recurring)
            self._current_recurring_id = recurring_id
            self._refresh_recurring()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to save recurring expense", str(exc))

    def _delete_recurring(self) -> None:
        if self._current_recurring_id is None:
            QMessageBox.information(self, "Delete recurring bill", "Select a recurring bill to delete.")
            return
        confirm = QMessageBox.question(self, "Delete recurring bill", "Delete the selected recurring bill?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        expense_service.delete_recurring_expense(self._current_recurring_id)
        self._current_recurring_id = None
        self._refresh_recurring()
        self._reset_recurring_form()

    def _on_recurring_selected(self, current, _previous) -> None:
        if not current.isValid():
            return
        recurring = cast(RecurringExpense, self._recurring_model._rows[current.row()])
        self._current_recurring_id = recurring.id
        if recurring.category:
            idx = self._recurring_category_combo.findText(recurring.category)
            if idx >= 0:
                self._recurring_category_combo.setCurrentIndex(idx)
            else:
                self._recurring_category_combo.setEditText(recurring.category)
        else:
            if self._recurring_category_combo.count() > 0:
                self._recurring_category_combo.setCurrentIndex(0)
            line_edit = self._recurring_category_combo.lineEdit()
            if self._recurring_category_combo.isEditable() and line_edit is not None:
                line_edit.clear()
        self._recurring_amount_input.setValue(recurring.amount)
        vendor_index = self._recurring_vendor_combo.findData(recurring.vendor_id)
        self._recurring_vendor_combo.setCurrentIndex(max(0, vendor_index))
        self._recurring_frequency_input.setText(recurring.frequency)
        if recurring.start_date:
            self._recurring_start_input.setDate(QDate(recurring.start_date.year, recurring.start_date.month, recurring.start_date.day))
        if recurring.next_occurrence:
            self._recurring_next_input.setDate(QDate(recurring.next_occurrence.year, recurring.next_occurrence.month, recurring.next_occurrence.day))
        self._recurring_auto_checkbox.setChecked(recurring.auto_record)
        self._recurring_notes_input.setPlainText(recurring.notes)

    # CRM tab ---------------------------------------------------------------
    def _build_crm_tab(self) -> None:
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        container.setLayout(layout)

        self._contact_model = ListTableModel(
            (
                ("Customer", lambda row: cast(CRMContact, row).customer_name),
                ("Company", lambda row: cast(CRMContact, row).company),
                ("Email", lambda row: cast(CRMContact, row).email),
                ("Phone", lambda row: cast(CRMContact, row).phone),
                ("Next Follow-up", lambda row: _format_date(cast(CRMContact, row).next_follow_up)),
            )
        )
        self._contact_table = QTableView()
        self._contact_table.setModel(self._contact_model)
        self._configure_table(self._contact_table)
        self._contact_table.selectionModel().currentChanged.connect(self._on_contact_selected)
        layout.addWidget(self._contact_table, stretch=3)

        form = QFormLayout()
        form_group = QWidget()
        form_group.setLayout(form)
        layout.addWidget(form_group, stretch=2)

        self._contact_name_input = QLineEdit()
        form.addRow("Customer", self._contact_name_input)

        self._contact_company_input = QLineEdit()
        form.addRow("Company", self._contact_company_input)

        self._contact_email_input = QLineEdit()
        form.addRow("Email", self._contact_email_input)

        self._contact_phone_input = QLineEdit()
        form.addRow("Phone", self._contact_phone_input)

        self._contact_address_input = QTextEdit()
        form.addRow("Address", self._contact_address_input)

        self._contact_tags_input = QLineEdit()
        self._contact_tags_input.setPlaceholderText("Comma separated tags")
        form.addRow("Tags", self._contact_tags_input)

        self._contact_follow_date_input = QDateEdit()
        self._contact_follow_date_input.setCalendarPopup(True)
        self._contact_follow_date_input.setDate(QDate.currentDate())
        form.addRow("Next Follow-up", self._contact_follow_date_input)

        self._contact_channel_input = QLineEdit()
        form.addRow("Channel", self._contact_channel_input)

        self._contact_notes_input = QTextEdit()
        form.addRow("Notes", self._contact_notes_input)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self._contact_import_button = QPushButton("Import from Orders")
        self._contact_import_button.clicked.connect(self._import_contacts_from_orders)
        buttons.addWidget(self._contact_import_button)
        self._contact_new_button = QPushButton("New")
        self._contact_new_button.clicked.connect(self._reset_contact_form)
        buttons.addWidget(self._contact_new_button)
        self._contact_save_button = QPushButton("Save Contact")
        self._contact_save_button.clicked.connect(self._save_contact)
        buttons.addWidget(self._contact_save_button)
        self._contact_delete_button = QPushButton("Delete Contact")
        self._contact_delete_button.clicked.connect(self._delete_contact)
        buttons.addWidget(self._contact_delete_button)
        buttons.addStretch(1)

        interaction_label = QLabel("Contact History")
        interaction_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(interaction_label)

        self._interaction_model = ListTableModel(
            (
                ("Date", lambda row: cast(CRMInteraction, row).interaction_date.strftime("%Y-%m-%d %H:%M")),
                ("Channel", lambda row: cast(CRMInteraction, row).channel),
                ("Summary", lambda row: cast(CRMInteraction, row).summary),
                ("Follow-up", lambda row: _format_date(cast(CRMInteraction, row).follow_up_date)),
            )
        )
        self._interaction_table = QTableView()
        self._interaction_table.setModel(self._interaction_model)
        self._configure_table(self._interaction_table)
        layout.addWidget(self._interaction_table, stretch=2)

        interaction_buttons = QHBoxLayout()
        layout.addLayout(interaction_buttons)
        self._interaction_new_button = QPushButton("Log Interaction")
        self._interaction_new_button.clicked.connect(self._log_interaction)
        interaction_buttons.addWidget(self._interaction_new_button)
        self._interaction_delete_button = QPushButton("Delete Interaction")
        self._interaction_delete_button.clicked.connect(self._delete_interaction)
        interaction_buttons.addWidget(self._interaction_delete_button)
        interaction_buttons.addStretch(1)

        self._current_contact_id: Optional[int] = None
        self._current_interaction_id: Optional[int] = None
        self._tab_widget.addTab(container, "CRM")

    def _refresh_contacts(self) -> None:
        contacts = crm_service.list_contacts()
        self._contact_model.update_rows(contacts)
        if self._current_contact_id is None:
            self._contact_table.clearSelection()
        self._interaction_model.update_rows([])

    def _reset_contact_form(self) -> None:
        self._current_contact_id = None
        self._contact_name_input.clear()
        self._contact_company_input.clear()
        self._contact_email_input.clear()
        self._contact_phone_input.clear()
        self._contact_address_input.clear()
        self._contact_tags_input.clear()
        self._contact_follow_date_input.setDate(QDate.currentDate())
        self._contact_channel_input.clear()
        self._contact_notes_input.clear()
        self._contact_table.clearSelection()
        self._interaction_model.update_rows([])

    def _collect_contact_from_form(self) -> CRMContact:
        tags = [tag.strip() for tag in self._contact_tags_input.text().split(",") if tag.strip()]
        contact = CRMContact(
            id=self._current_contact_id,
            customer_name=self._contact_name_input.text().strip(),
            company=self._contact_company_input.text().strip(),
            email=self._contact_email_input.text().strip(),
            phone=self._contact_phone_input.text().strip(),
            address=self._contact_address_input.toPlainText().strip(),
            tags=tags,
            created_at=None,
            last_contacted=None,
            next_follow_up=cast(date, self._contact_follow_date_input.date().toPython()),
            preferred_channel=self._contact_channel_input.text().strip(),
            notes=self._contact_notes_input.toPlainText().strip(),
        )
        return contact

    def _save_contact(self) -> None:
        try:
            contact = self._collect_contact_from_form()
            if not contact.customer_name:
                raise ValueError("Customer name is required")
            contact_id = crm_service.save_contact(contact)
            self._current_contact_id = contact_id
            self._refresh_contacts()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to save contact", str(exc))

    def _delete_contact(self) -> None:
        if self._current_contact_id is None:
            QMessageBox.information(self, "Delete contact", "Select a contact to delete.")
            return
        confirm = QMessageBox.question(self, "Delete contact", "Delete the selected contact?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        crm_service.delete_contact(self._current_contact_id)
        self._current_contact_id = None
        self._refresh_contacts()
        self._reset_contact_form()

    def _import_contacts_from_orders(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Import customers",
            "Import customers from order history into the CRM?\nExisting contacts keep their current details; missing addresses will be filled in.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            created, updated = crm_service.import_contacts_from_orders()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        self._refresh_contacts()
        self._reset_contact_form()

        if created == 0 and updated == 0:
            message = "No new customers were added; all orders already have contacts."
        else:
            parts = []
            if created:
                parts.append(f"added {created} new contact{'s' if created != 1 else ''}")
            if updated:
                parts.append(
                    f"updated {updated} contact{'s' if updated != 1 else ''} with addresses"
                )
            message = "Successfully " + " and ".join(parts) + "."

        QMessageBox.information(self, "Import complete", message)

    def _on_contact_selected(self, current, _previous) -> None:
        if not current.isValid():
            return
        contact = cast(CRMContact, self._contact_model._rows[current.row()])
        self._current_contact_id = contact.id
        self._contact_name_input.setText(contact.customer_name)
        self._contact_company_input.setText(contact.company)
        self._contact_email_input.setText(contact.email)
        self._contact_phone_input.setText(contact.phone)
        self._contact_address_input.setPlainText(contact.address)
        self._contact_tags_input.setText(", ".join(contact.tags))
        if contact.next_follow_up:
            self._contact_follow_date_input.setDate(QDate(contact.next_follow_up.year, contact.next_follow_up.month, contact.next_follow_up.day))
        self._contact_channel_input.setText(contact.preferred_channel)
        self._contact_notes_input.setPlainText(contact.notes)
        contact_id = contact.id
        if contact_id is None:
            self._interaction_model.update_rows([])
            return
        interactions = crm_service.list_interactions(contact_id, limit=200)
        self._interaction_model.update_rows(interactions)

    def _log_interaction(self) -> None:
        if self._current_contact_id is None:
            QMessageBox.information(self, "Log interaction", "Select a contact first.")
            return
        dialog = InteractionDialog(self, contact_id=self._current_contact_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._interaction_model.update_rows(crm_service.list_interactions(self._current_contact_id, limit=200))

    def _delete_interaction(self) -> None:
        selection = self._interaction_table.selectionModel().currentIndex()
        if not selection.isValid():
            QMessageBox.information(self, "Delete interaction", "Select an interaction to delete.")
            return
        interaction = cast(CRMInteraction, self._interaction_model._rows[selection.row()])
        confirm = QMessageBox.question(self, "Delete interaction", "Delete the selected interaction?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if interaction.id is None:
            QMessageBox.information(self, "Delete interaction", "Interaction is missing an identifier.")
            return
        crm_service.delete_interaction(interaction.id)
        if self._current_contact_id is not None:
            self._interaction_model.update_rows(crm_service.list_interactions(self._current_contact_id, limit=200))

    # Documents tab ---------------------------------------------------------
    def _build_documents_tab(self) -> None:
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        container.setLayout(layout)

        self._document_model = ListTableModel(
            (
                ("File", lambda row: Path(cast(DocumentRecord, row).file_path).name),
                ("Category", lambda row: cast(DocumentRecord, row).category),
                ("Entity", lambda row: _format_document_entity(cast(DocumentRecord, row))),
                ("Stored", lambda row: cast(DocumentRecord, row).stored_at),
                ("Tags", lambda row: ", ".join(cast(DocumentRecord, row).tags)),
            )
        )
        self._document_table = QTableView()
        self._document_table.setModel(self._document_model)
        self._configure_table(self._document_table)
        self._document_table.selectionModel().currentChanged.connect(self._on_document_selected)
        layout.addWidget(self._document_table, stretch=3)

        form = QFormLayout()
        form_group = QWidget()
        form_group.setLayout(form)
        layout.addWidget(form_group, stretch=2)

        self._document_entity_type_input = QLineEdit()
        form.addRow("Entity Type", self._document_entity_type_input)

        self._document_entity_id_input = QLineEdit()
        form.addRow("Entity ID", self._document_entity_id_input)

        self._document_category_input = QLineEdit()
        form.addRow("Category", self._document_category_input)

        self._document_description_input = QLineEdit()
        form.addRow("Description", self._document_description_input)

        self._document_tags_input = QLineEdit()
        self._document_tags_input.setPlaceholderText("Comma separated tags")
        form.addRow("Tags", self._document_tags_input)

        self._document_path_label = QLabel("No file selected")
        form.addRow("File", self._document_path_label)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self._document_choose_button = QPushButton("Choose File")
        self._document_choose_button.clicked.connect(self._choose_document_file)
        buttons.addWidget(self._document_choose_button)
        self._document_save_button = QPushButton("Save Document")
        self._document_save_button.clicked.connect(self._save_document)
        buttons.addWidget(self._document_save_button)
        self._document_delete_button = QPushButton("Delete Document")
        self._document_delete_button.clicked.connect(self._delete_document)
        buttons.addWidget(self._document_delete_button)
        buttons.addStretch(1)

        self._current_document_id: Optional[int] = None
        self._selected_document_path: Optional[Path] = None
        self._tab_widget.addTab(container, "Documents")

    def _refresh_documents(self) -> None:
        documents = document_service.list_documents()
        self._document_model.update_rows(documents)
        if self._current_document_id is None:
            self._document_table.clearSelection()

    def _choose_document_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select document")
        if file_path:
            self._selected_document_path = Path(file_path)
            self._document_path_label.setText(self._selected_document_path.name)

    def _collect_document_from_form(self) -> DocumentRecord:
        entity_id_text = self._document_entity_id_input.text().strip()
        entity_id = int(entity_id_text) if entity_id_text.isdigit() else None
        tags = [tag.strip() for tag in self._document_tags_input.text().split(",") if tag.strip()]
        record = DocumentRecord(
            id=self._current_document_id,
            entity_type=self._document_entity_type_input.text().strip() or "general",
            entity_id=entity_id,
            file_path=str(self._selected_document_path or ""),
            category=self._document_category_input.text().strip(),
            description=self._document_description_input.text().strip(),
            tags=tags,
            stored_at="local",
            checksum="",
            created_at=None,
        )
        return record

    def _save_document(self) -> None:
        try:
            record = self._collect_document_from_form()
            if not record.file_path:
                raise ValueError("Select a file to store")
            document_id = document_service.save_document(record)
            self._current_document_id = document_id
            self._refresh_documents()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to save document", str(exc))

    def _delete_document(self) -> None:
        if self._current_document_id is None:
            QMessageBox.information(self, "Delete document", "Select a document to delete.")
            return
        confirm = QMessageBox.question(self, "Delete document", "Delete the selected document?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        document_service.delete_document(self._current_document_id)
        self._current_document_id = None
        self._selected_document_path = None
        self._document_path_label.setText("No file selected")
        self._refresh_documents()

    def _on_document_selected(self, current, _previous) -> None:
        if not current.isValid():
            return
        document = cast(DocumentRecord, self._document_model._rows[current.row()])
        self._current_document_id = document.id
        self._document_entity_type_input.setText(document.entity_type)
        self._document_entity_id_input.setText(str(document.entity_id or ""))
        self._document_category_input.setText(document.category)
        self._document_description_input.setText(document.description)
        self._document_tags_input.setText(", ".join(document.tags))
        self._document_path_label.setText(Path(document.file_path).name)
        self._selected_document_path = Path(document.file_path)

    # Goals tab -------------------------------------------------------------
    def _build_goals_tab(self) -> None:
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        container.setLayout(layout)

        self._goal_model = ListTableModel(
            (
                ("Name", lambda row: cast(BusinessGoal, row).name),
                ("Metric", lambda row: cast(BusinessGoal, row).metric_type),
                ("Target", lambda row: f"{cast(BusinessGoal, row).target_value:,.2f}"),
                ("Current", lambda row: f"{cast(BusinessGoal, row).current_value:,.2f}"),
                ("Status", lambda row: cast(BusinessGoal, row).status),
            )
        )
        self._goal_table = QTableView()
        self._goal_table.setModel(self._goal_model)
        self._configure_table(self._goal_table)
        self._goal_table.selectionModel().currentChanged.connect(self._on_goal_selected)
        layout.addWidget(self._goal_table, stretch=3)

        form = QFormLayout()
        form_group = QWidget()
        form_group.setLayout(form)
        layout.addWidget(form_group, stretch=2)

        self._goal_name_input = QLineEdit()
        form.addRow("Goal Name", self._goal_name_input)

        self._goal_metric_input = QLineEdit()
        self._goal_metric_input.setPlaceholderText("revenue, profit, orders, expenses, losses, crm-followups")
        form.addRow("Metric Type", self._goal_metric_input)

        self._goal_target_input = QDoubleSpinBox()
        self._goal_target_input.setDecimals(2)
        self._goal_target_input.setRange(0.0, 1_000_000_000.0)
        form.addRow("Target Value", self._goal_target_input)

        self._goal_current_input = QDoubleSpinBox()
        self._goal_current_input.setDecimals(2)
        self._goal_current_input.setRange(0.0, 1_000_000_000.0)
        form.addRow("Current Value", self._goal_current_input)

        self._goal_start_input = QDateEdit()
        self._goal_start_input.setCalendarPopup(True)
        self._goal_start_input.setDate(QDate.currentDate())
        form.addRow("Start Date", self._goal_start_input)

        self._goal_end_input = QDateEdit()
        self._goal_end_input.setCalendarPopup(True)
        self._goal_end_input.setDate(QDate.currentDate())
        form.addRow("End Date", self._goal_end_input)

        self._goal_auto_checkbox = QCheckBox("Auto-calculate metric")
        self._goal_auto_checkbox.setChecked(True)
        form.addRow("Automation", self._goal_auto_checkbox)

        self._goal_warning_input = QDoubleSpinBox()
        self._goal_warning_input.setDecimals(2)
        self._goal_warning_input.setRange(0.0, 1.0)
        self._goal_warning_input.setSingleStep(0.05)
        self._goal_warning_input.setValue(0.5)
        form.addRow("Warning Threshold", self._goal_warning_input)

        self._goal_critical_input = QDoubleSpinBox()
        self._goal_critical_input.setDecimals(2)
        self._goal_critical_input.setRange(0.0, 1.0)
        self._goal_critical_input.setSingleStep(0.05)
        self._goal_critical_input.setValue(0.25)
        form.addRow("Critical Threshold", self._goal_critical_input)

        self._goal_notes_input = QTextEdit()
        form.addRow("Notes", self._goal_notes_input)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self._goal_new_button = QPushButton("New Goal")
        self._goal_new_button.clicked.connect(self._reset_goal_form)
        buttons.addWidget(self._goal_new_button)
        self._goal_save_button = QPushButton("Save Goal")
        self._goal_save_button.clicked.connect(self._save_goal)
        buttons.addWidget(self._goal_save_button)
        self._goal_delete_button = QPushButton("Delete Goal")
        self._goal_delete_button.clicked.connect(self._delete_goal)
        buttons.addWidget(self._goal_delete_button)
        buttons.addStretch(1)

        self._current_goal_id: Optional[int] = None
        self._tab_widget.addTab(container, "Goals")

    def _refresh_goals(self) -> None:
        goals = goal_service.evaluate_goals()
        self._goal_model.update_rows(goals)
        if self._current_goal_id is None:
            self._goal_table.clearSelection()

    def _reset_goal_form(self) -> None:
        self._current_goal_id = None
        self._goal_name_input.clear()
        self._goal_metric_input.setText("revenue")
        self._goal_target_input.setValue(0.0)
        self._goal_current_input.setValue(0.0)
        self._goal_start_input.setDate(QDate.currentDate())
        self._goal_end_input.setDate(QDate.currentDate())
        self._goal_auto_checkbox.setChecked(True)
        self._goal_warning_input.setValue(0.5)
        self._goal_critical_input.setValue(0.25)
        self._goal_notes_input.clear()
        self._goal_table.clearSelection()

    def _collect_goal_from_form(self) -> BusinessGoal:
        goal = BusinessGoal(
            id=self._current_goal_id,
            name=self._goal_name_input.text().strip(),
            metric_type=self._goal_metric_input.text().strip(),
            target_value=self._goal_target_input.value(),
            start_date=cast(date, self._goal_start_input.date().toPython()),
            end_date=cast(date, self._goal_end_input.date().toPython()),
            current_value=self._goal_current_input.value(),
            owner="",
            progress_notes=self._goal_notes_input.toPlainText().strip(),
            threshold_warning=self._goal_warning_input.value(),
            threshold_critical=self._goal_critical_input.value(),
            auto_calculate=self._goal_auto_checkbox.isChecked(),
            checkpoints=[],
        )
        return goal

    def _save_goal(self) -> None:
        try:
            goal = self._collect_goal_from_form()
            if not goal.name:
                raise ValueError("Goal name is required")
            goal_id = goal_repository.save_goal(goal)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Unable to save goal", str(exc))
            return
        self._current_goal_id = goal_id
        self._refresh_goals()

    def _delete_goal(self) -> None:
        if self._current_goal_id is None:
            QMessageBox.information(self, "Delete goal", "Select a goal to delete.")
            return
        confirm = QMessageBox.question(self, "Delete goal", "Delete the selected goal?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        goal_repository.delete_goal(self._current_goal_id)
        self._current_goal_id = None
        self._refresh_goals()
        self._reset_goal_form()

    def _on_goal_selected(self, current, _previous) -> None:
        if not current.isValid():
            return
        goal = cast(BusinessGoal, self._goal_model._rows[current.row()])
        self._current_goal_id = goal.id
        self._goal_name_input.setText(goal.name)
        self._goal_metric_input.setText(goal.metric_type)
        self._goal_target_input.setValue(goal.target_value)
        self._goal_current_input.setValue(goal.current_value)
        if goal.start_date:
            self._goal_start_input.setDate(QDate(goal.start_date.year, goal.start_date.month, goal.start_date.day))
        if goal.end_date:
            self._goal_end_input.setDate(QDate(goal.end_date.year, goal.end_date.month, goal.end_date.day))
        self._goal_auto_checkbox.setChecked(goal.auto_calculate)
        self._goal_warning_input.setValue(goal.threshold_warning)
        self._goal_critical_input.setValue(goal.threshold_critical)
        self._goal_notes_input.setPlainText(goal.progress_notes)

    # Utility ----------------------------------------------------------------
    def _configure_table(self, table: QTableView) -> None:
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)

    def _wrap_vendor_combo(self, combo: QComboBox) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        container.setLayout(layout)
        layout.addWidget(combo)
        manage_button = QPushButton("Manage")
        manage_button.setMinimumWidth(90)
        manage_button.clicked.connect(self._open_vendor_manager)
        layout.addWidget(manage_button)
        return container

    def _refresh_vendor_lists(self) -> None:
        self._load_vendor_options()
        self._load_vendor_combo(self._expense_vendor_combo)
        self._load_vendor_combo(self._recurring_vendor_combo)

    def _open_vendor_manager(self) -> None:
        dialog = ManageVendorsDialog(self, on_changed=self._refresh_vendor_lists)
        dialog.exec()
        self._refresh_vendor_lists()

    def refresh_all(self) -> None:
        self._refresh_losses()
        self._refresh_materials()
        self._refresh_expenses()
        self._refresh_recurring()
        self._refresh_contacts()
        self._refresh_documents()
        self._refresh_goals()


class InteractionDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], *, contact_id: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Log Interaction")
        self.resize(420, 320)
        self._contact_id = contact_id

        layout = QVBoxLayout()
        self.setLayout(layout)

        form = QFormLayout()
        layout.addLayout(form)

        self._date_input = QDateEdit()
        self._date_input.setCalendarPopup(True)
        self._date_input.setDate(QDate.currentDate())
        form.addRow("Date", self._date_input)

        self._channel_input = QLineEdit()
        form.addRow("Channel", self._channel_input)

        self._summary_input = QTextEdit()
        form.addRow("Summary", self._summary_input)

        self._follow_up_input = QDateEdit()
        self._follow_up_input.setCalendarPopup(True)
        self._follow_up_input.setDate(QDate.currentDate())
        form.addRow("Follow-up", self._follow_up_input)

        self._follow_action_input = QLineEdit()
        form.addRow("Action", self._follow_action_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save_interaction)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_interaction(self) -> None:
        summary = self._summary_input.toPlainText().strip()
        if not summary:
            QMessageBox.information(self, "Interaction", "Enter a summary of the interaction.")
            return
        interaction_date = datetime.combine(
            cast(date, self._date_input.date().toPython()),
            datetime.min.time(),
        )
        interaction = CRMInteraction(
            id=None,
            contact_id=self._contact_id,
            interaction_date=interaction_date,
            channel=self._channel_input.text().strip(),
            summary=summary,
            follow_up_date=cast(date, self._follow_up_input.date().toPython()),
            follow_up_action=self._follow_action_input.text().strip(),
            order_id=None,
        )
        crm_service.save_interaction(interaction)
        self.accept()


class ManageVendorsDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], *, on_changed: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Vendors")
        self.resize(520, 360)
        self._on_changed = on_changed

        layout = QVBoxLayout()
        self.setLayout(layout)

        self._model = ListTableModel(
            (
                ("Name", lambda row: cast(Vendor, row).name),
                ("Contact", lambda row: cast(Vendor, row).contact_name),
                ("Phone", lambda row: cast(Vendor, row).phone),
            )
        )
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Supplier name")
        self._name_input.returnPressed.connect(self._add_vendor)
        form.addRow("Vendor Name", self._name_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self._add_button = QPushButton("Add Vendor")
        self._add_button.clicked.connect(self._add_vendor)
        buttons.addWidget(self._add_button)

        self._delete_button = QPushButton("Delete Selected")
        self._delete_button.clicked.connect(self._delete_selected)
        buttons.addWidget(self._delete_button)

        buttons.addStretch(1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self._refresh()

    def _notify_changed(self) -> None:
        if self._on_changed is not None:
            self._on_changed()

    def _refresh(self) -> None:
        vendors = vendor_service.list_vendors()
        self._model.update_rows(vendors)
        if vendors:
            self._table.selectRow(0)
        else:
            self._table.clearSelection()

    def _add_vendor(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.information(self, "Add vendor", "Enter a vendor name before adding.")
            return
        vendor = Vendor(id=None, name=name)
        try:
            vendor_service.save_vendor(vendor)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Add vendor", f"Unable to add vendor: {exc}")
            return
        self._name_input.clear()
        self._refresh()
        self._notify_changed()

    def _delete_selected(self) -> None:
        index = self._table.selectionModel().currentIndex()
        if not index.isValid():
            QMessageBox.information(self, "Delete vendor", "Select a vendor to delete.")
            return
        vendor = cast(Vendor, self._model._rows[index.row()])
        if vendor.id is None:
            QMessageBox.information(self, "Delete vendor", "Selected vendor is missing an identifier.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete vendor",
            f"Delete vendor '{vendor.name}'? This will unlink it from materials and expenses.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            vendor_service.delete_vendor(vendor.id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Delete vendor", f"Unable to delete vendor: {exc}")
            return
        self._refresh()
        self._notify_changed()


class MaterialTransactionsDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], *, material_id: Optional[int], material_name: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Transactions - {material_name}")
        self.resize(640, 420)
        self._material_id = material_id

        layout = QVBoxLayout()
        self.setLayout(layout)

        self._model = ListTableModel(
            (
                ("Date", lambda row: cast(MaterialTransaction, row).transaction_date.strftime("%Y-%m-%d %H:%M")),
                ("Delta", lambda row: f"{cast(MaterialTransaction, row).quantity_delta:g}"),
                ("Cost", lambda row: f"${cast(MaterialTransaction, row).unit_cost:,.2f}"),
                ("Reason", lambda row: cast(MaterialTransaction, row).reason),
                ("Reference", lambda row: cast(MaterialTransaction, row).reference_type or ""),
                ("Note", lambda row: cast(MaterialTransaction, row).notes),
            )
        )
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

        self._refresh()

    def _refresh(self) -> None:
        if self._material_id is None:
            self._model.update_rows([])
            return
        transactions = material_service.list_transactions(self._material_id, limit=200)
        self._model.update_rows(transactions)


def _prompt_for_double(parent: QWidget, title: str, message: str) -> tuple[float, bool]:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QVBoxLayout()
    dialog.setLayout(layout)
    layout.addWidget(QLabel(message))
    spin = QDoubleSpinBox()
    spin.setDecimals(3)
    spin.setRange(-1_000_000.0, 1_000_000.0)
    layout.addWidget(spin)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return spin.value(), True
    return 0.0, False
