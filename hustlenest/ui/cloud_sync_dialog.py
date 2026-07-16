from __future__ import annotations

from dataclasses import replace
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..models.order_models import AppSettings
from ..services import cloud_sync_service, order_service
from ..data.database import get_database_path, close_database_for_replacement


class CloudSyncDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cloud Sync Settings")
        self.resize(620, 520)

        self._settings_snapshot = settings
        self._config: Dict[str, str] = dict(settings.cloud_sync_config or {})
        self._provider_fields: Dict[str, Dict[str, QLineEdit]] = {}
        self._provider_pages: Dict[str, int] = {}
        self._updated_settings: Optional[AppSettings] = None
        self._last_outcome = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        top_form = QFormLayout()
        layout.addLayout(top_form)

        self._enabled_checkbox = QCheckBox("Enable periodic cloud sync")
        self._enabled_checkbox.setChecked(settings.cloud_sync_enabled)
        top_form.addRow("Sync Status", self._enabled_checkbox)

        self._provider_combo = QComboBox()
        self._provider_combo.addItem("Select provider", "")
        self._provider_combo.addItem("Local Folder (sync client)", "local-folder")
        self._provider_combo.addItem("Personal Google Drive", "google-drive")
        self._provider_combo.addItem("Dropbox", "dropbox")
        self._provider_combo.addItem("Microsoft OneDrive", "onedrive")
        self._provider_combo.addItem("Self-Hosted (SFTP)", "sftp")
        top_form.addRow("Provider", self._provider_combo)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 1440)
        self._interval_spin.setSuffix(" min")
        self._interval_spin.setValue(settings.cloud_sync_interval_minutes or 5)
        top_form.addRow("Sync Interval", self._interval_spin)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        empty_page = QLabel("Select a provider to configure cloud sync options.")
        empty_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(empty_page)

        self._register_local_page()
        self._register_google_page()
        self._register_dropbox_page()
        self._register_onedrive_page()
        self._register_sftp_page()

        button_row = QHBoxLayout()
        layout.addLayout(button_row)

        self._download_button = QPushButton("Pull Latest")
        self._download_button.clicked.connect(self._handle_download)
        button_row.addWidget(self._download_button)

        self._upload_button = QPushButton("Upload Now")
        self._upload_button.clicked.connect(self._handle_upload)
        button_row.addWidget(self._upload_button)

        self._authorize_button = QPushButton("Authorize Google Drive")
        self._authorize_button.clicked.connect(self._handle_authorize_google)
        button_row.addWidget(self._authorize_button)

        button_row.addStretch(1)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._handle_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._provider_combo.currentIndexChanged.connect(self._handle_provider_changed)
        self._enabled_checkbox.toggled.connect(self._update_manual_buttons)

        self._initialize_form(settings)
        self._update_manual_buttons()

    def get_updated_settings(self) -> Optional[AppSettings]:
        return self._updated_settings

    def get_last_outcome(self):
        return self._last_outcome

    def _register_google_page(self) -> None:
        page, fields = self._build_page(
            (
                ("Token JSON", self._browse_file_callback("token_path")),
                ("Client Secrets", self._browse_file_callback("client_secrets_path")),
                ("Folder ID", None),
                ("Remote File Name", None),
            ),
            password_fields={"token_path": False, "client_secrets_path": False},
        )
        self._provider_fields["google-drive"] = fields
        index = self._stack.addWidget(page)
        self._provider_pages["google-drive"] = index

    def _register_dropbox_page(self) -> None:
        page, fields = self._build_page(
            (
                ("Access Token", None),
                ("Remote Path", None),
            ),
            password_fields={"access_token": True},
        )
        self._provider_fields["dropbox"] = fields
        index = self._stack.addWidget(page)
        self._provider_pages["dropbox"] = index

    def _register_local_page(self) -> None:
        page, fields = self._build_page(
            (
                ("Directory", self._browse_folder_callback("directory")),
                ("Remote File Name", None),
            ),
            password_fields={},
        )
        self._provider_fields["local-folder"] = fields
        index = self._stack.addWidget(page)
        self._provider_pages["local-folder"] = index

    def _register_onedrive_page(self) -> None:
        page, fields = self._build_page(
            (
                ("Client ID", None),
                ("Client Secret", None),
                ("Tenant", None),
                ("Refresh Token", None),
                ("Remote Path", None),
            ),
            password_fields={"client_secret": True, "refresh_token": True},
        )
        self._provider_fields["onedrive"] = fields
        index = self._stack.addWidget(page)
        self._provider_pages["onedrive"] = index

    def _register_sftp_page(self) -> None:
        page, fields = self._build_page(
            (
                ("Host", None),
                ("Port", None),
                ("Username", None),
                ("Password", None),
                ("Private Key", self._browse_file_callback("private_key_path")),
                ("Remote Path", None),
            ),
            password_fields={"password": True},
        )
        self._provider_fields["sftp"] = fields
        index = self._stack.addWidget(page)
        self._provider_pages["sftp"] = index

    def _build_page(self, rows, password_fields: Dict[str, bool]) -> tuple[QWidget, Dict[str, QLineEdit]]:
        widget = QWidget()
        form = QFormLayout(widget)

        fields: Dict[str, QLineEdit] = {}

        for label_text, browse_callback in rows:
            key = label_text.lower().replace(" ", "_")
            field = QLineEdit()
            if password_fields.get(key):
                field.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
            if browse_callback is not None:
                row_widget = self._build_browse_row(field, browse_callback)
                form.addRow(label_text, row_widget)
            else:
                form.addRow(label_text, field)
            fields[key] = field

        return widget, fields

    def _build_browse_row(self, field: QLineEdit, callback):
        row_widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        row_widget.setLayout(layout)
        layout.addWidget(field)
        button = QPushButton("Browse…")
        button.clicked.connect(lambda: callback(field))
        layout.addWidget(button)
        return row_widget

    def _browse_file_callback(self, key: str):
        def chooser(field: QLineEdit) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Select File", field.text().strip() or "", "All Files (*)")
            if path:
                field.setText(path)

        return chooser

    def _browse_folder_callback(self, key: str):
        def chooser(field: QLineEdit) -> None:
            path = QFileDialog.getExistingDirectory(self, "Select Folder", field.text().strip() or "")
            if path:
                field.setText(path)

        return chooser

    def _initialize_form(self, settings: AppSettings) -> None:
        provider_key = (settings.cloud_sync_provider or "").strip().lower()
        index = self._provider_combo.findData(provider_key)
        if index >= 0:
            self._provider_combo.setCurrentIndex(index)
        else:
            self._provider_combo.setCurrentIndex(0)
        self._populate_fields(provider_key)
        self._handle_provider_changed()

    def _populate_fields(self, provider_key: str) -> None:
        config = self._config
        if provider_key == "local-folder":
            fields = self._provider_fields["local-folder"]
            fields["directory"].setText(config.get("directory", ""))
            fields["remote_file_name"].setText(config.get("file_name", ""))
        elif provider_key == "google-drive":
            fields = self._provider_fields["google-drive"]
            fields["token_json"].setText(config.get("token_path", ""))
            fields["client_secrets"].setText(config.get("client_secrets_path", ""))
            fields["folder_id"].setText(config.get("folder_id", ""))
            fields["remote_file_name"].setText(config.get("file_name", ""))
        elif provider_key == "dropbox":
            fields = self._provider_fields["dropbox"]
            fields["access_token"].setText(config.get("access_token", ""))
            fields["remote_path"].setText(config.get("remote_path", ""))
        elif provider_key == "onedrive":
            fields = self._provider_fields["onedrive"]
            fields["client_id"].setText(config.get("client_id", ""))
            fields["client_secret"].setText(config.get("client_secret", ""))
            fields["tenant"].setText(config.get("tenant_id", ""))
            fields["refresh_token"].setText(config.get("refresh_token", ""))
            fields["remote_path"].setText(config.get("remote_path", ""))
        elif provider_key == "sftp":
            fields = self._provider_fields["sftp"]
            fields["host"].setText(config.get("host", ""))
            fields["port"].setText(config.get("port", ""))
            fields["username"].setText(config.get("username", ""))
            fields["password"].setText(config.get("password", ""))
            fields["private_key"].setText(config.get("private_key_path", ""))
            fields["remote_path"].setText(config.get("remote_path", ""))

    def _collect_provider_config(self) -> Dict[str, str]:
        provider_key = self._provider_combo.currentData()
        result: Dict[str, str] = {}
        if provider_key == "local-folder":
            fields = self._provider_fields["local-folder"]
            result = {
                "directory": fields["directory"].text().strip(),
                "file_name": fields["remote_file_name"].text().strip() or get_database_path().name,
            }
        elif provider_key == "google-drive":
            fields = self._provider_fields["google-drive"]
            result = {
                "token_path": fields["token_json"].text().strip(),
                "client_secrets_path": fields["client_secrets"].text().strip(),
                "folder_id": fields["folder_id"].text().strip() or "root",
                "file_name": fields["remote_file_name"].text().strip() or get_database_path().name,
            }
            file_id = self._config.get("file_id")
            if file_id:
                result["file_id"] = file_id
        elif provider_key == "dropbox":
            fields = self._provider_fields["dropbox"]
            result = {
                "access_token": fields["access_token"].text().strip(),
                "remote_path": fields["remote_path"].text().strip(),
            }
        elif provider_key == "onedrive":
            fields = self._provider_fields["onedrive"]
            result = {
                "client_id": fields["client_id"].text().strip(),
                "client_secret": fields["client_secret"].text().strip(),
                "tenant_id": fields["tenant"].text().strip() or "consumers",
                "refresh_token": fields["refresh_token"].text().strip(),
                "remote_path": fields["remote_path"].text().strip() or "Documents/hustlenest.db",
            }
        elif provider_key == "sftp":
            fields = self._provider_fields["sftp"]
            result = {
                "host": fields["host"].text().strip(),
                "port": fields["port"].text().strip(),
                "username": fields["username"].text().strip(),
                "password": fields["password"].text().strip(),
                "private_key_path": fields["private_key"].text().strip(),
                "remote_path": fields["remote_path"].text().strip(),
            }
        return result

    def _handle_provider_changed(self) -> None:
        provider_key = self._provider_combo.currentData()
        index = self._provider_pages.get(provider_key, 0)
        self._stack.setCurrentIndex(index)
        self._authorize_button.setVisible(provider_key == "google-drive")
        self._populate_fields(provider_key)
        self._update_manual_buttons()

    def _update_manual_buttons(self) -> None:
        enabled = self._enabled_checkbox.isChecked()
        provider_key = self._provider_combo.currentData()
        can_sync = enabled and bool(provider_key)
        self._upload_button.setEnabled(can_sync)
        self._download_button.setEnabled(can_sync)
        if provider_key != "google-drive":
            self._authorize_button.setVisible(False)

    def _apply_fields_to_snapshot(self) -> None:
        provider_key = self._provider_combo.currentData() or ""
        config = self._collect_provider_config()
        self._config = dict(config)
        snapshot = replace(
            self._settings_snapshot,
            cloud_sync_enabled=self._enabled_checkbox.isChecked(),
            cloud_sync_provider=provider_key,
            cloud_sync_interval_minutes=self._interval_spin.value(),
            cloud_sync_config=dict(config),
        )
        self._settings_snapshot = snapshot

    def _handle_download(self) -> None:
        self._apply_fields_to_snapshot()
        # Close database connections before attempting to replace the database file
        close_database_for_replacement()
        outcome = cloud_sync_service.download_database_if_newer(self._settings_snapshot)
        self._last_outcome = outcome
        self._set_status(outcome.message or "Download complete.", error=not outcome.success)
        if outcome.success:
            self._reload_settings()

    def _handle_upload(self) -> None:
        self._apply_fields_to_snapshot()
        outcome = cloud_sync_service.upload_database(self._settings_snapshot)
        self._last_outcome = outcome
        self._set_status(outcome.message or "Upload complete.", error=not outcome.success)
        if outcome.success:
            self._reload_settings()

    def _handle_authorize_google(self) -> None:
        config = self._collect_provider_config()
        client_path = config.get("client_secrets_path", "")
        token_path = config.get("token_path", "")
        if not client_path or not token_path:
            self._set_status("Provide both client secrets and token file paths before authorizing.", error=True)
            return
        outcome = cloud_sync_service.authorize_google_drive(client_path, token_path)
        self._last_outcome = outcome
        self._set_status(outcome.message or "", error=not outcome.success)

    def _handle_save(self) -> None:
        self._apply_fields_to_snapshot()
        config = dict(self._settings_snapshot.cloud_sync_config or {})
        updated = order_service.update_cloud_sync_settings(
            enabled=self._settings_snapshot.cloud_sync_enabled,
            provider=self._settings_snapshot.cloud_sync_provider,
            interval_minutes=self._settings_snapshot.cloud_sync_interval_minutes,
            config=config,
        )
        self._updated_settings = updated
        self.accept()

    def _reload_settings(self) -> None:
        refreshed = order_service.get_app_settings()
        self._settings_snapshot = refreshed
        self._config = dict(refreshed.cloud_sync_config or {})
        provider_key = refreshed.cloud_sync_provider or ""
        index = self._provider_combo.findData(provider_key)
        if index >= 0:
            self._provider_combo.setCurrentIndex(index)
        self._enabled_checkbox.setChecked(refreshed.cloud_sync_enabled)
        self._interval_spin.setValue(refreshed.cloud_sync_interval_minutes or 5)
        self._populate_fields(provider_key)
        self._update_manual_buttons()

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #b00020;" if error else "")
