from __future__ import annotations

from typing import Iterable, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from ..models.order_models import CostComponent


class CostComponentEditorDialog(QDialog):
    def __init__(self, *, components: Iterable[CostComponent] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Extra Costs")
        self.resize(520, 360)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.setLayout(layout)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Label", "Amount"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self._table)

        button_row = QHBoxLayout()
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._handle_add_row)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._handle_remove_row)
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        initial_components = list(components or [])
        self._result_components: List[CostComponent] = [CostComponent(label=c.label, amount=c.amount) for c in initial_components]
        for component in initial_components:
            self._append_component(component)

        if self._table.rowCount() == 0:
            self._append_component()

    def _append_component(self, component: CostComponent | None = None) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        label_text = component.label if component else ""
        amount_value = component.amount if component else 0.0

        label_item = QTableWidgetItem(label_text)
        amount_item = QTableWidgetItem(f"{amount_value:.2f}")
        amount_item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))

        self._table.setItem(row, 0, label_item)
        self._table.setItem(row, 1, amount_item)

    def _handle_add_row(self) -> None:
        self._append_component()

    def _handle_remove_row(self) -> None:
        current = self._table.currentRow()
        if current < 0:
            return
        self._table.removeRow(current)
        if self._table.rowCount() == 0:
            self._append_component()

    def components(self) -> List[CostComponent]:
        return [CostComponent(label=component.label, amount=component.amount) for component in self._result_components]

    def accept(self) -> None:  # noqa: D401
        try:
            self._result_components = self._collect_components()
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Extra Costs", str(exc))
            return
        super().accept()

    def _collect_components(self) -> List[CostComponent]:
        results: List[CostComponent] = []
        for row in range(self._table.rowCount()):
            label_item = self._table.item(row, 0)
            amount_item = self._table.item(row, 1)

            label = label_item.text().strip() if label_item else ""
            amount_text = amount_item.text().strip() if amount_item else "0"

            if not label and not amount_text:
                continue

            try:
                amount = float(amount_text)
            except ValueError as exc:  # noqa: BLE001
                raise ValueError(f"Row {row + 1}: enter a numeric amount.") from exc

            if amount < 0:
                raise ValueError(f"Row {row + 1}: amount cannot be negative.")

            if not label and amount > 0:
                raise ValueError(f"Row {row + 1}: provide a label for the additional cost.")

            if label or amount > 0:
                results.append(CostComponent(label=label, amount=amount))

        return results
