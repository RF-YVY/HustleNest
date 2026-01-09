from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models.order_models import AppSettings, Order, PaymentOption
from ..services import order_service


class InvoiceManagerDialog(QDialog):
    def __init__(
        self,
        *,
        parent: Optional[QWidget] = None,
        app_settings: AppSettings,
        order: Optional[Order] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Invoice Manager")
        self.resize(520, 640)

        self._app_settings = app_settings
        self._updated_settings: Optional[AppSettings] = None
        self._order = order

        self._order_number_label: Optional[QLabel] = None
        self._order_total_label: Optional[QLabel] = None
        self._order_date_label: Optional[QLabel] = None
        self._order_customer_label: Optional[QLabel] = None
        self._payment_rows: List[Tuple[QWidget, QLineEdit, QLineEdit]] = []
        self._payment_list_layout: Optional[QVBoxLayout] = None
        self._payment_add_button: Optional[QPushButton] = None

        self._build_ui()
        self._populate_fields()

    def get_updated_settings(self) -> Optional[AppSettings]:
        return self._updated_settings

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.setLayout(layout)

        if self._order is not None:
            layout.addWidget(self._build_order_summary())

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.addLayout(form_layout)

        self._slogan_input = QLineEdit()
        self._slogan_input.setPlaceholderText("Your Company Slogan")
        form_layout.addRow("Slogan", self._slogan_input)

        self._street_input = QLineEdit()
        self._street_input.setPlaceholderText("Street Address")
        form_layout.addRow("Street", self._street_input)

        city_state_widget = QWidget()
        city_state_layout = QHBoxLayout()
        city_state_layout.setContentsMargins(0, 0, 0, 0)
        city_state_layout.setSpacing(8)
        city_state_widget.setLayout(city_state_layout)

        self._city_input = QLineEdit()
        self._city_input.setPlaceholderText("City")
        city_state_layout.addWidget(self._city_input)

        self._state_input = QLineEdit()
        self._state_input.setPlaceholderText("State")
        self._state_input.setMaxLength(2)
        city_state_layout.addWidget(self._state_input)

        self._zip_input = QLineEdit()
        self._zip_input.setPlaceholderText("ZIP")
        self._zip_input.setMaxLength(12)
        city_state_layout.addWidget(self._zip_input)

        form_layout.addRow("City / ST / ZIP", city_state_widget)

        self._phone_input = QLineEdit()
        self._phone_input.setPlaceholderText("Primary phone")
        form_layout.addRow("Phone", self._phone_input)

        self._fax_input = QLineEdit()
        self._fax_input.setPlaceholderText("Fax")
        form_layout.addRow("Fax", self._fax_input)

        self._terms_input = QLineEdit()
        self._terms_input.setPlaceholderText("Due on receipt")
        form_layout.addRow("Terms", self._terms_input)

        self._comments_input = QTextEdit()
        self._comments_input.setAcceptRichText(False)
        self._comments_input.setPlaceholderText("Comments or special instructions")
        self._comments_input.setFixedHeight(90)
        form_layout.addRow("Comments", self._comments_input)

        self._contact_name_input = QLineEdit()
        self._contact_name_input.setPlaceholderText("Contact name")
        form_layout.addRow("Contact Name", self._contact_name_input)

        self._contact_phone_input = QLineEdit()
        self._contact_phone_input.setPlaceholderText("Contact phone")
        form_layout.addRow("Contact Phone", self._contact_phone_input)

        self._contact_email_input = QLineEdit()
        self._contact_email_input.setPlaceholderText("Contact email")
        form_layout.addRow("Contact Email", self._contact_email_input)

        payment_container = QWidget()
        payment_layout = QVBoxLayout()
        payment_layout.setContentsMargins(0, 0, 0, 0)
        payment_layout.setSpacing(6)
        payment_container.setLayout(payment_layout)
        self._payment_list_layout = payment_layout

        self._payment_add_button = QPushButton("Add Payment Method")
        self._payment_add_button.clicked.connect(self._handle_add_payment_row)
        self._payment_add_button.setAutoDefault(False)
        self._payment_add_button.setDefault(False)
        payment_layout.addWidget(self._payment_add_button, alignment=Qt.AlignmentFlag.AlignLeft)

        form_layout.addRow("Payment Methods", payment_container)

        self._payment_notes_input = QTextEdit()
        self._payment_notes_input.setAcceptRichText(False)
        self._payment_notes_input.setPlaceholderText("Other payment notes")
        self._payment_notes_input.setFixedHeight(80)
        form_layout.addRow("Payment Notes", self._payment_notes_input)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._handle_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._state_input.editingFinished.connect(self._normalize_state)

    def _populate_fields(self) -> None:
        settings = self._app_settings
        self._slogan_input.setText(settings.invoice_slogan)
        self._street_input.setText(settings.invoice_street)
        self._city_input.setText(settings.invoice_city)
        self._state_input.setText(settings.invoice_state)
        self._zip_input.setText(settings.invoice_zip)
        self._phone_input.setText(settings.invoice_phone)
        self._fax_input.setText(settings.invoice_fax)
        self._terms_input.setText(settings.invoice_terms)
        self._comments_input.setPlainText(settings.invoice_comments)
        self._contact_name_input.setText(settings.invoice_contact_name)
        self._contact_phone_input.setText(settings.invoice_contact_phone)
        self._contact_email_input.setText(settings.invoice_contact_email)
        self._payment_notes_input.setPlainText(settings.payment_other)

        if self._payment_list_layout is not None:
            self._clear_payment_rows()
            if settings.payment_options:
                for option in settings.payment_options:
                    self._add_payment_row(option.label, option.value)
            else:
                self._add_payment_row()

        if self._order is not None:
            order = self._order
            if self._order_number_label is not None:
                self._order_number_label.setText(order.order_number or "--")
            if self._order_date_label is not None:
                order_date = order.order_date.strftime("%B %d, %Y") if order.order_date else "--"
                self._order_date_label.setText(order_date)
            if self._order_total_label is not None:
                include_tax = bool(self._app_settings.tax_add_to_total)
                total_value = order.total_amount + (order.tax_amount if include_tax else 0.0)
                self._order_total_label.setText(self._format_currency(total_value))
            if self._order_customer_label is not None:
                address_lines = [segment.strip() for segment in (order.customer_address or "").splitlines() if segment.strip()]
                address_block = "\n".join(address_lines)
                customer_text = order.customer_name.strip() if order.customer_name else "--"
                if address_block:
                    customer_text = f"{customer_text}\n{address_block}" if customer_text != "--" else address_block
                self._order_customer_label.setText(customer_text or "--")

    def _normalize_state(self) -> None:
        value = self._state_input.text().strip().upper()[:2]
        self._state_input.blockSignals(True)
        self._state_input.setText(value)
        self._state_input.blockSignals(False)

    def _handle_save(self) -> None:
        payment_options: List[PaymentOption] = []
        for _container, label_input, value_input in self._payment_rows:
            label = label_input.text().strip()
            value = value_input.text().strip()
            if label and value:
                payment_options.append(PaymentOption(label=label, value=value))

        updated = replace(
            self._app_settings,
            invoice_slogan=self._slogan_input.text().strip(),
            invoice_street=self._street_input.text().strip(),
            invoice_city=self._city_input.text().strip(),
            invoice_state=self._state_input.text().strip().upper()[:2],
            invoice_zip=self._zip_input.text().strip(),
            invoice_phone=self._phone_input.text().strip(),
            invoice_fax=self._fax_input.text().strip(),
            invoice_terms=self._terms_input.text().strip() or "Due on receipt",
            invoice_comments=self._comments_input.toPlainText().strip(),
            invoice_contact_name=self._contact_name_input.text().strip(),
            invoice_contact_phone=self._contact_phone_input.text().strip(),
            invoice_contact_email=self._contact_email_input.text().strip(),
            payment_options=payment_options,
            payment_other=self._payment_notes_input.toPlainText().strip(),
        )
        self._updated_settings = order_service.update_app_settings(updated)
        self.accept()

    def _handle_add_payment_row(self) -> None:
        self._add_payment_row()

    def _add_payment_row(self, label: str = "", value: str = "") -> None:
        if self._payment_list_layout is None or self._payment_add_button is None:
            return

        row_widget = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_widget.setLayout(row_layout)

        label_input = QLineEdit()
        label_input.setPlaceholderText("Service name")
        label_input.setText(label)

        value_input = QLineEdit()
        value_input.setPlaceholderText("Account, email, or payment link")
        value_input.setText(value)

        remove_button = QPushButton("Remove")
        remove_button.setAutoDefault(False)
        remove_button.setDefault(False)
        remove_button.clicked.connect(partial(self._remove_payment_row, row_widget))

        row_layout.addWidget(label_input, 1)
        row_layout.addWidget(value_input, 2)
        row_layout.addWidget(remove_button)

        insert_index = max(0, self._payment_list_layout.count() - 1)
        self._payment_list_layout.insertWidget(insert_index, row_widget)
        self._payment_rows.append((row_widget, label_input, value_input))

    def _remove_payment_row(self, target: QWidget) -> None:
        retained: List[Tuple[QWidget, QLineEdit, QLineEdit]] = []
        for container, label_input, value_input in self._payment_rows:
            if container is target:
                container.setParent(None)
                container.deleteLater()
                continue
            retained.append((container, label_input, value_input))
        self._payment_rows = retained
        if not self._payment_rows:
            self._add_payment_row()

    def _clear_payment_rows(self) -> None:
        for container, _label_input, _value_input in self._payment_rows:
            container.setParent(None)
            container.deleteLater()
        self._payment_rows.clear()

    def _build_order_summary(self) -> QGroupBox:
        box = QGroupBox("Selected Order")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        box.setLayout(form)

        self._order_number_label = QLabel()
        self._order_number_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Order #", self._order_number_label)

        self._order_date_label = QLabel()
        self._order_date_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Order Date", self._order_date_label)

        self._order_total_label = QLabel()
        self._order_total_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Total", self._order_total_label)

        self._order_customer_label = QLabel()
        self._order_customer_label.setWordWrap(True)
        self._order_customer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Customer", self._order_customer_label)

        return box

    @staticmethod
    def _format_currency(value: float) -> str:
        return f"${value:,.2f}"
