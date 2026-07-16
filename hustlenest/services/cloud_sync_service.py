from __future__ import annotations

import gc
import json
import os
import posixpath
import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Optional

import requests

from ..data import settings_repository
from ..data.database import get_database_path, close_database_for_replacement
from ..models.order_models import AppSettings

try:  # Google Drive (OAuth)
	from google.oauth2.credentials import Credentials
	from google.auth.transport.requests import Request
	from googleapiclient.discovery import build
	from googleapiclient.errors import HttpError
	from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

	_GOOGLE_CLIENT_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
	Credentials = None  # type: ignore[assignment]
	Request = None  # type: ignore[assignment]
	build = None  # type: ignore[assignment]
	HttpError = Exception  # type: ignore[assignment]
	MediaFileUpload = None  # type: ignore[assignment]
	MediaIoBaseDownload = None  # type: ignore[assignment]
	_GOOGLE_CLIENT_AVAILABLE = False

try:  # Google Drive authorization helper
	from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:  # pragma: no cover - optional dependency
	InstalledAppFlow = None  # type: ignore[assignment]

try:  # Dropbox
	import dropbox
	from dropbox.exceptions import ApiError, AuthError
	from dropbox.files import WriteMode

	_DROPBOX_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
	dropbox = None  # type: ignore[assignment]
	ApiError = AuthError = Exception  # type: ignore[assignment]
	WriteMode = None  # type: ignore[assignment]
	_DROPBOX_AVAILABLE = False

try:  # OneDrive (Microsoft Graph)
	import msal

	_MSAL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
	msal = None  # type: ignore[assignment]
	_MSAL_AVAILABLE = False

try:  # Self-hosted SFTP
	import paramiko

	_PARAMIKO_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
	paramiko = None  # type: ignore[assignment]
	_PARAMIKO_AVAILABLE = False


_DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive.file",)
_ONE_DRIVE_SCOPES = ["Files.ReadWrite.All"]


@dataclass
class SyncOutcome:
	success: bool
	message: str = ""
	file_id: Optional[str] = None
	downloaded: bool = False
	uploaded: bool = False


@dataclass
class RemoteFileInfo:
	identifier: Optional[str]
	modified: Optional[datetime]


class CloudSyncError(RuntimeError):
	pass


class BaseProvider:
	def __init__(self, config: Dict[str, str]) -> None:
		self._initial_config = dict(config or {})
		self.config: Dict[str, str] = dict(config or {})

	def validate(self) -> None:  # pragma: no cover - override where needed
		pass

	def get_remote_file(self) -> Optional[RemoteFileInfo]:
		raise NotImplementedError

	def download_file(self, destination: Path) -> None:
		raise NotImplementedError

	def upload_file(self, source: Path) -> RemoteFileInfo:
		raise NotImplementedError

	def config_changed(self) -> bool:
		return self.config != self._initial_config


class GoogleDriveProvider(BaseProvider):
	def validate(self) -> None:
		if not _GOOGLE_CLIENT_AVAILABLE:
			raise CloudSyncError(
				"Google Drive support requires google-api-python-client and google-auth packages."
			)
		token_path = self.config.get("token_path", "").strip()
		if not token_path:
			raise CloudSyncError("Provide the token JSON path for Google Drive sync.")
		if not Path(token_path).expanduser().exists():
			raise CloudSyncError(f"Google Drive token file not found at {token_path}.")
		folder_id = self.config.get("folder_id", "").strip()
		if not folder_id:
			self.config["folder_id"] = "root"
		name = self.config.get("file_name", "").strip()
		if not name:
			name = get_database_path().name
		self.config["file_name"] = _normalize_db_filename(name)

	def _credentials(self) -> Credentials:
		assert Credentials is not None and Request is not None
		token_path = Path(self.config.get("token_path", "")).expanduser()
		credentials = Credentials.from_authorized_user_file(str(token_path), scopes=_DRIVE_SCOPES)
		if not credentials.valid:
			if credentials.expired and credentials.refresh_token:
				credentials.refresh(Request())
				token_path.write_text(credentials.to_json())
			else:
				raise CloudSyncError(
					"Google Drive credentials are invalid or expired. Re-run the authorization flow."
				)
		return credentials

	def _service(self):
		assert build is not None
		return build("drive", "v3", credentials=self._credentials(), cache_discovery=False)

	def get_remote_file(self) -> Optional[RemoteFileInfo]:
		service = self._service()
		file_id = (self.config.get("file_id") or "").strip()
		metadata = None
		if file_id:
			metadata = self._metadata_by_id(service, file_id)
			if metadata is None:
				file_id = ""

		if not file_id:
			metadata, file_id = self._metadata_by_query(service)

		if metadata is None:
			return None

		if file_id and file_id != (self.config.get("file_id") or "").strip():
			self.config["file_id"] = file_id

		modified = _parse_iso_datetime(metadata.get("modifiedTime"))
		return RemoteFileInfo(identifier=file_id, modified=modified)

	def download_file(self, destination: Path) -> None:
		service = self._service()
		file_id = (self.config.get("file_id") or "").strip()
		if not file_id:
			raise CloudSyncError("Remote file id missing for Google Drive download.")
		assert MediaIoBaseDownload is not None
		request = service.files().get_media(fileId=file_id)
		with destination.open("wb") as buffer:
			downloader = MediaIoBaseDownload(buffer, request)
			done = False
			while not done:
				_status, done = downloader.next_chunk()

	def upload_file(self, source: Path) -> RemoteFileInfo:
		service = self._service()
		file_id = (self.config.get("file_id") or "").strip()
		metadata = {
			"name": self.config.get("file_name", source.name).strip() or source.name,
			"parents": [self.config.get("folder_id", "root").strip() or "root"],
		}
		assert MediaFileUpload is not None
		media = MediaFileUpload(str(source), mimetype="application/octet-stream", resumable=False)

		if file_id:
			service.files().update(fileId=file_id, media_body=media).execute()
		else:
			created = service.files().create(body=metadata, media_body=media, fields="id, modifiedTime").execute()
			file_id = created.get("id", "")
			if not file_id:
				raise CloudSyncError("Google Drive did not return a file id after upload.")
			self.config["file_id"] = file_id
			metadata = created

		refreshed_meta = self._metadata_by_id(service, file_id)
		if refreshed_meta is None:
			refreshed_meta = metadata
		modified = _parse_iso_datetime(refreshed_meta.get("modifiedTime") if refreshed_meta else None)
		return RemoteFileInfo(identifier=file_id or None, modified=modified)

	def _metadata_by_id(self, service, file_id: str):
		try:
			return service.files().get(fileId=file_id, fields="id, name, modifiedTime").execute()
		except HttpError:
			return None

	def _metadata_by_query(self, service):
		escaped_name = (self.config.get("file_name") or get_database_path().name).replace("'", "\'")
		folder_id = self.config.get("folder_id", "root") or "root"
		query = f"'{folder_id}' in parents and name = '{escaped_name}' and trashed = false"
		response = service.files().list(q=query, pageSize=1, fields="files(id, name, modifiedTime)").execute()
		files = response.get("files", [])
		if not files:
			return None, None
		metadata = files[0]
		return metadata, metadata.get("id")


class DropboxProvider(BaseProvider):
	def validate(self) -> None:
		if not _DROPBOX_AVAILABLE:
			raise CloudSyncError("Dropbox support requires the dropbox package. Install it with pip.")
		token = self.config.get("access_token", "").strip()
		if not token:
			raise CloudSyncError("Provide a Dropbox access token.")
		path = self.config.get("remote_path", "").strip()
		if not path:
			raise CloudSyncError("Provide the remote Dropbox path, e.g., /Apps/HustleNest/hustlenest.db")
		if not path.startswith("/"):
			self.config["remote_path"] = "/" + path

	def _client(self):
		assert dropbox is not None
		return dropbox.Dropbox(self.config.get("access_token", "").strip())

	def get_remote_file(self) -> Optional[RemoteFileInfo]:
		client = self._client()
		path = self.config.get("remote_path", "").strip()
		try:
			metadata = client.files_get_metadata(path)
		except AuthError as error:  # type: ignore[name-defined]
			raise CloudSyncError(f"Dropbox authentication failed: {error}")
		except ApiError:
			return None

		modified = metadata.server_modified if hasattr(metadata, "server_modified") else None
		if isinstance(modified, datetime):
			modified = modified.astimezone(timezone.utc)
		else:
			modified = None
		return RemoteFileInfo(identifier=getattr(metadata, "id", None), modified=modified)

	def download_file(self, destination: Path) -> None:
		client = self._client()
		path = self.config.get("remote_path", "").strip()
		client.files_download_to_file(str(destination), path)

	def upload_file(self, source: Path) -> RemoteFileInfo:
		client = self._client()
		path = self.config.get("remote_path", "").strip()
		with source.open("rb") as handle:
			metadata = client.files_upload(handle.read(), path, mode=WriteMode("overwrite"))
		modified = metadata.server_modified.astimezone(timezone.utc) if metadata.server_modified else None
		return RemoteFileInfo(identifier=getattr(metadata, "id", None), modified=modified)


class LocalFolderProvider(BaseProvider):
	def validate(self) -> None:
		raw_directory = (self.config.get("directory", "") or "").strip()
		if not raw_directory:
			raise CloudSyncError("Select a target directory for local folder sync.")
		directory = Path(raw_directory).expanduser()
		if not directory.exists():
			directory.mkdir(parents=True, exist_ok=True)
		if not directory.is_dir():
			raise CloudSyncError(f"Local sync path is not a directory: {directory}")
		self.config["directory"] = str(directory)
		name = self.config.get("file_name", "").strip()
		if not name:
			name = get_database_path().name
		self.config["file_name"] = _normalize_db_filename(name)

	def _remote_path(self) -> Path:
		directory = Path(self.config.get("directory", "")).expanduser()
		file_name = (self.config.get("file_name") or get_database_path().name).strip()
		return directory / (file_name or get_database_path().name)

	def get_remote_file(self) -> Optional[RemoteFileInfo]:
		remote_path = self._remote_path()
		if not remote_path.exists():
			return None
		modified = datetime.fromtimestamp(remote_path.stat().st_mtime, tz=timezone.utc)
		return RemoteFileInfo(identifier=str(remote_path), modified=modified)

	def download_file(self, destination: Path) -> None:
		remote_path = self._remote_path()
		if not remote_path.exists():
			raise CloudSyncError(f"Remote file not found at {remote_path}.")
		shutil.copy2(remote_path, destination)

	def upload_file(self, source: Path) -> RemoteFileInfo:
		remote_path = self._remote_path()
		remote_path.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source, remote_path)
		modified = datetime.fromtimestamp(remote_path.stat().st_mtime, tz=timezone.utc)
		return RemoteFileInfo(identifier=str(remote_path), modified=modified)


class OneDriveProvider(BaseProvider):
	def validate(self) -> None:
		if not _MSAL_AVAILABLE:
			raise CloudSyncError("OneDrive support requires the msal package. Install it with pip.")
		required = {
			"client_id": "Client ID",
			"client_secret": "Client secret",
			"tenant_id": "Tenant (use 'consumers' for personal accounts)",
			"refresh_token": "Refresh token",
		}
		for key, label in required.items():
			if not (self.config.get(key) or "").strip():
				raise CloudSyncError(f"{label} is required for OneDrive sync.")
		remote_path = self.config.get("remote_path", "").strip()
		if not remote_path:
			self.config["remote_path"] = "Documents/hustlenest.db"

	def _acquire_token(self) -> str:
		assert msal is not None
		authority = f"https://login.microsoftonline.com/{self.config.get('tenant_id').strip()}"
		app = msal.ConfidentialClientApplication(
			client_id=self.config.get("client_id", "").strip(),
			client_credential=self.config.get("client_secret", "").strip(),
			authority=authority,
		)
		result = app.acquire_token_by_refresh_token(
			self.config.get("refresh_token", "").strip(), scopes=_ONE_DRIVE_SCOPES
		)
		if not result or "access_token" not in result:
			raise CloudSyncError(result.get("error_description", "Unable to refresh OneDrive token."))
		new_refresh = result.get("refresh_token")
		if new_refresh and new_refresh != self.config.get("refresh_token"):
			self.config["refresh_token"] = new_refresh
		return result["access_token"]

	def _headers(self) -> Dict[str, str]:
		token = self._acquire_token()
		return {"Authorization": f"Bearer {token}"}

	def _item_url(self) -> str:
		path = self.config.get("remote_path", "Documents/hustlenest.db").strip().strip("/")
		safe_path = requests.utils.quote(path)
		return f"https://graph.microsoft.com/v1.0/me/drive/root:/{safe_path}:"

	def get_remote_file(self) -> Optional[RemoteFileInfo]:
		try:
			response = requests.get(self._item_url(), headers=self._headers(), timeout=30)
		except requests.RequestException as error:
			raise CloudSyncError(f"OneDrive request error: {error}") from error
		if response.status_code == 404:
			return None
		if response.status_code >= 400:
			raise CloudSyncError(f"OneDrive request failed: {response.status_code} {response.text}")
		data = response.json()
		identifier = data.get("id")
		modified = _parse_iso_datetime(data.get("lastModifiedDateTime"))
		return RemoteFileInfo(identifier=identifier, modified=modified)

	def download_file(self, destination: Path) -> None:
		url = self._item_url() + "/content"
		try:
			response = requests.get(url, headers=self._headers(), timeout=60, stream=True)
		except requests.RequestException as error:
			raise CloudSyncError(f"OneDrive download failed: {error}") from error
		if response.status_code >= 400:
			raise CloudSyncError(f"OneDrive download failed: {response.status_code} {response.text}")
		with destination.open("wb") as handle:
			for chunk in response.iter_content(chunk_size=1024 * 256):
				if chunk:
					handle.write(chunk)

	def upload_file(self, source: Path) -> RemoteFileInfo:
		url = self._item_url() + "/content"
		try:
			with source.open("rb") as handle:
				response = requests.put(url, data=handle, headers=self._headers(), timeout=120)
		except requests.RequestException as error:
			raise CloudSyncError(f"OneDrive upload failed: {error}") from error
		if response.status_code >= 400:
			raise CloudSyncError(f"OneDrive upload failed: {response.status_code} {response.text}")
		data = response.json()
		identifier = data.get("id")
		modified = _parse_iso_datetime(data.get("lastModifiedDateTime"))
		return RemoteFileInfo(identifier=identifier, modified=modified)


class SFTPProvider(BaseProvider):
	def validate(self) -> None:
		if not _PARAMIKO_AVAILABLE:
			raise CloudSyncError("SFTP sync requires the paramiko package. Install it with pip.")
		host = self.config.get("host", "").strip()
		username = self.config.get("username", "").strip()
		remote_path = self.config.get("remote_path", "").strip()
		if not host or not username or not remote_path:
			raise CloudSyncError("Host, username, and remote path are required for SFTP sync.")
		port = self.config.get("port", "").strip()
		if port and not port.isdigit():
			raise CloudSyncError("SFTP port must be a number.")

	def _connect(self):
		assert paramiko is not None
		host = self.config.get("host", "").strip()
		port = int(self.config.get("port", "22") or 22)
		username = self.config.get("username", "").strip()
		password = self.config.get("password", "").strip()
		key_path = self.config.get("private_key_path", "").strip()

		transport = paramiko.Transport((host, port))
		pkey = None
		if key_path:
			key_file = Path(key_path).expanduser()
			if not key_file.exists():
				raise CloudSyncError(f"Private key file not found: {key_file}")
			try:
				pkey = paramiko.RSAKey.from_private_key_file(str(key_file))
			except paramiko.PasswordRequiredException as exc:
				raise CloudSyncError(f"Encrypted key requires passphrase: {exc}") from exc

		try:
			transport.connect(username=username, password=password or None, pkey=pkey)
		except paramiko.SSHException as exc:
			transport.close()
			raise CloudSyncError(f"SFTP connection failed: {exc}") from exc

		client = paramiko.SFTPClient.from_transport(transport)
		return client, transport

	def get_remote_file(self) -> Optional[RemoteFileInfo]:
		remote_path = self.config.get("remote_path", "").strip()
		client, transport = self._connect()
		try:
			try:
				stats = client.stat(remote_path)
			except FileNotFoundError:
				return None
			modified = datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc)
			return RemoteFileInfo(identifier=remote_path, modified=modified)
		finally:
			client.close()
			transport.close()

	def download_file(self, destination: Path) -> None:
		remote_path = self.config.get("remote_path", "").strip()
		client, transport = self._connect()
		try:
			client.get(remote_path, str(destination))
		finally:
			client.close()
			transport.close()

	def upload_file(self, source: Path) -> RemoteFileInfo:
		remote_path = self.config.get("remote_path", "").strip()
		client, transport = self._connect()
		try:
			self._ensure_remote_directory(client, remote_path)
			client.put(str(source), remote_path)
			stats = client.stat(remote_path)
		finally:
			client.close()
			transport.close()
		modified = datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc)
		return RemoteFileInfo(identifier=remote_path, modified=modified)

	def _ensure_remote_directory(self, client, remote_path: str) -> None:
		directory = posixpath.dirname(remote_path)
		if not directory or directory == "/":
			return
		segments = directory.split("/")
		current = ""
		for segment in segments:
			if not segment:
				continue
			current += "/" + segment
			try:
				client.stat(current)
			except FileNotFoundError:
				client.mkdir(current)


def is_configured(settings: AppSettings) -> bool:
	provider = _build_provider(settings, silent=True, validate=False)
	if provider is None:
		return False
	try:
		provider.validate()
	except CloudSyncError:
		return False
	return True


def sync_interval_seconds(settings: AppSettings) -> int:
	minutes = max(1, int(settings.cloud_sync_interval_minutes or 5))
	return minutes * 60


def download_database_if_newer(settings: AppSettings) -> SyncOutcome:
	try:
		provider = _build_provider(settings)
	except CloudSyncError as error:
		return SyncOutcome(False, str(error))
	if provider is None:
		return SyncOutcome(False, "Cloud sync is disabled.")

	local_path = get_database_path()
	try:
		remote_info = provider.get_remote_file()
	except CloudSyncError as error:
		return SyncOutcome(False, str(error))

	if remote_info is None or not remote_info.identifier:
		_persist_config_if_needed(settings, provider)
		return SyncOutcome(False, "No remote database found for the selected provider.")

	needs_download = not local_path.exists()
	if not needs_download and _is_database_effectively_empty(local_path):
		needs_download = True
	if not needs_download and remote_info.modified is not None:
		local_modified = datetime.fromtimestamp(local_path.stat().st_mtime, tz=timezone.utc)
		needs_download = remote_info.modified > local_modified

	if not needs_download:
		_persist_config_if_needed(settings, provider)
		return SyncOutcome(True, "Local database is current.", file_id=remote_info.identifier)

	temp_path = local_path.with_suffix(".download")
	temp_path.parent.mkdir(parents=True, exist_ok=True)

	try:
		provider.download_file(temp_path)
	except CloudSyncError as error:
		if temp_path.exists():
			temp_path.unlink(missing_ok=True)
		return SyncOutcome(False, str(error))

	try:
		_validate_database_file(temp_path)
	except CloudSyncError as error:
		temp_path.unlink(missing_ok=True)
		return SyncOutcome(False, str(error))

	try:
		_atomic_replace(local_path, temp_path)
	except PermissionError as error:
		if temp_path.exists():
			temp_path.unlink(missing_ok=True)
		return SyncOutcome(False, f"Could not replace local database. Close other running instances and try again. Details: {error}")
	except OSError as error:
		if temp_path.exists():
			temp_path.unlink(missing_ok=True)
		return SyncOutcome(False, f"Failed to replace local database: {error}")
	_persist_config_if_needed(settings, provider)
	return SyncOutcome(True, "Database pulled from cloud storage.", file_id=remote_info.identifier, downloaded=True)


def upload_database(settings: AppSettings) -> SyncOutcome:
	try:
		provider = _build_provider(settings)
	except CloudSyncError as error:
		return SyncOutcome(False, str(error))
	if provider is None:
		return SyncOutcome(False, "Cloud sync is disabled.")

	local_path = get_database_path()
	if not local_path.exists():
		return SyncOutcome(False, f"Local database missing at {local_path}.")

	try:
		with TemporaryDirectory(prefix="hustlenest-cloud-upload-") as temporary:
			snapshot = Path(temporary) / local_path.name
			source = sqlite3.connect(local_path)
			target = sqlite3.connect(snapshot)
			try:
				source.backup(target)
			finally:
				target.close()
				source.close()
			_validate_database_file(snapshot)
			remote_info = provider.upload_file(snapshot)
	except (CloudSyncError, sqlite3.Error, OSError) as error:
		return SyncOutcome(False, f"Cloud upload failed: {error}")

	_persist_config_if_needed(settings, provider)
	return SyncOutcome(True, "Database uploaded to cloud storage.", file_id=remote_info.identifier, uploaded=True)


def authorize_google_drive(client_secrets_path: str, token_output_path: str) -> SyncOutcome:
	if InstalledAppFlow is None:
		return SyncOutcome(False, "google-auth-oauthlib is required to run the authorization flow.")

	client_path = Path(client_secrets_path).expanduser()
	if not client_path.exists():
		return SyncOutcome(False, f"Client secrets file not found: {client_path}")

	try:
		flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes=_DRIVE_SCOPES)
		credentials = flow.run_local_server(port=0)
	except Exception as error:  # noqa: BLE001
		return SyncOutcome(False, f"Authorization failed: {error}")

	token_path = Path(token_output_path).expanduser()
	token_path.parent.mkdir(parents=True, exist_ok=True)
	token_path.write_text(credentials.to_json())
	return SyncOutcome(True, f"Authorization complete. Token saved to {token_path}")


def _build_provider(
	settings: AppSettings,
	*,
	silent: bool = False,
	validate: bool = True,
) -> Optional[BaseProvider]:
	if not settings.cloud_sync_enabled:
		return None

	provider_key = (settings.cloud_sync_provider or "").strip().lower()
	if not provider_key:
		if silent:
			return None
		raise CloudSyncError("Select a cloud sync provider before enabling sync.")

	config = dict(settings.cloud_sync_config or {})
	provider_map = {
		"local-folder": LocalFolderProvider,
		"google-drive": GoogleDriveProvider,
		"dropbox": DropboxProvider,
		"onedrive": OneDriveProvider,
		"sftp": SFTPProvider,
	}

	provider_cls = provider_map.get(provider_key)
	if provider_cls is None:
		if silent:
			return None
		raise CloudSyncError(f"Unsupported cloud sync provider: {settings.cloud_sync_provider}")

	provider = provider_cls(config)
	if validate:
		provider.validate()
	return provider


def _persist_config_if_needed(settings: AppSettings, provider: BaseProvider) -> None:
	if not provider.config_changed():
		return
	settings.cloud_sync_config = dict(provider.config)
	settings_repository.set_setting(
		"cloud_sync_settings_json",
		json.dumps(provider.config, ensure_ascii=False),
	)


def _atomic_replace(destination: Path, temporary: Path) -> None:
	# First, try to release all database handles
	lock_error = close_database_for_replacement()
	if lock_error:
		# Log but continue - we'll try anyway
		pass
	
	_prepare_destination_for_replace(destination)
	
	# Force garbage collection to release Python-side references
	gc.collect()
	time.sleep(0.15)
	
	if destination.exists():
		backup = destination.with_suffix(".bak")
		try:
			if backup.exists():
				backup.unlink()
			destination.replace(backup)
		except OSError:
			# Try to remove read-only attribute and retry
			_clear_readonly(destination)
			try:
				if backup.exists():
					backup.unlink()
				destination.replace(backup)
			except OSError:
				pass

	last_error: Optional[Exception] = None
	for attempt in range(5):  # Increased from 3 to 5 attempts
		try:
			# Try shutil.move first as it handles cross-device moves better
			shutil.move(str(temporary), str(destination))
			return
		except PermissionError as error:
			last_error = error
			_clear_readonly(destination)
			gc.collect()  # Force GC on each attempt
			try:
				destination.unlink(missing_ok=True)
			except OSError:
				pass
			time.sleep(0.3 * (attempt + 1))  # Progressive backoff
			continue
		except OSError as error:
			last_error = error
			gc.collect()
			time.sleep(0.3 * (attempt + 1))
			continue

	# Final attempt with Path.replace
	if temporary.exists():
		try:
			temporary.replace(destination)
			return
		except (PermissionError, OSError) as error:
			last_error = error

	if last_error:
		raise last_error


def _prepare_destination_for_replace(destination: Path) -> None:
	"""Attempt to flush WAL and free handles before replacing the database."""
	if not destination.exists():
		return
	
	# Multiple attempts to checkpoint and switch journal mode
	for attempt in range(3):
		try:
			# Use a short timeout and explicit close
			conn = sqlite3.connect(str(destination), timeout=2.0)
			cursor = conn.cursor()
			try:
				cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
				cursor.execute("PRAGMA journal_mode=DELETE;")
			except sqlite3.Error:
				pass
			finally:
				cursor.close()
				conn.close()
			break
		except sqlite3.Error:
			time.sleep(0.1)
	
	# Force garbage collection
	gc.collect()
	
	# Try to remove WAL/SHM files with retries
	for suffix in ("-wal", "-shm"):
		candidate = destination.with_name(destination.name + suffix)
		for _ in range(3):
			try:
				if candidate.exists():
					_clear_readonly(candidate)
					candidate.unlink()
				break
			except OSError:
				time.sleep(0.1)


def _parse_iso_datetime(raw: Optional[str]) -> Optional[datetime]:
	if not raw:
		return None
	normalized = raw.replace("Z", "+00:00")
	try:
		parsed = datetime.fromisoformat(normalized)
	except ValueError:
		return None
	if parsed.tzinfo is None:
		return parsed.replace(tzinfo=timezone.utc)
	return parsed.astimezone(timezone.utc)


def _normalize_db_filename(name: str) -> str:
	"""Ensure the remote database file name has a .db extension."""
	clean = (name or "").strip()
	if not clean:
		return get_database_path().name
	if Path(clean).suffix:
		return clean
	return f"{clean}.db"


def _is_database_effectively_empty(db_path: Path) -> bool:
	"""Treat a freshly created DB with no business rows as empty so pulls overwrite it."""
	try:
		with sqlite3.connect(db_path) as connection:
			cursor = connection.cursor()
			tables = [
				"orders",
				"order_items",
				"products",
				"vendors",
				"materials",
				"expenses",
				"recurring_expenses",
			]
			for table in tables:
				row = cursor.execute(f"SELECT COUNT(1) FROM {table}").fetchone()
				if row and row[0] > 0:
					return False
			return True
	except sqlite3.Error:
		return False


def _validate_database_file(db_path: Path) -> None:
	"""Reject corrupt or unrelated downloads before replacing the live database."""
	try:
		connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
		try:
			check = connection.execute("PRAGMA quick_check").fetchone()
			if check is None or str(check[0]).lower() != "ok":
				raise CloudSyncError("Downloaded database failed its integrity check.")
			tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
			if not {"settings", "orders", "products"}.issubset(tables):
				raise CloudSyncError("Downloaded file is not a HustleNest database.")
		finally:
			connection.close()
	except sqlite3.Error as error:
		raise CloudSyncError(f"Downloaded database could not be validated: {error}") from error


def _clear_readonly(path: Path) -> None:
	"""Best-effort removal of read-only attribute so replacements succeed on Windows."""
	try:
		if path.exists():
			path.chmod(0o666)
	except OSError:
		pass
