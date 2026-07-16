"""Database backup scheduler service."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Signal

from ..data import settings_repository
from ..data.database import get_database_path


class BackupScheduler(QObject):
    """Manages automatic database backups."""
    
    backup_completed = Signal(str)  # Emits backup file path
    backup_failed = Signal(str)     # Emits error message
    
    _instance: Optional["BackupScheduler"] = None
    
    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_and_backup)
        self._backup_folder: str = ""
        self._frequency: str = "daily"  # daily, weekly, or manual
        self._enabled: bool = False
        self._max_backups: int = 10
        self._last_backup: Optional[datetime] = None
    
    @classmethod
    def instance(cls) -> "BackupScheduler":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = BackupScheduler()
        return cls._instance
    
    def load_settings(self) -> None:
        """Load backup settings from the database."""
        self._backup_folder = settings_repository.get_setting("backup_folder") or ""
        self._frequency = settings_repository.get_setting("backup_frequency") or "daily"
        enabled_raw = settings_repository.get_setting("backup_enabled") or "0"
        self._enabled = enabled_raw.strip().lower() not in ("0", "false", "no", "")
        
        try:
            self._max_backups = max(1, int(settings_repository.get_setting("backup_max_count") or "10"))
        except ValueError:
            self._max_backups = 10
        
        last_backup_str = settings_repository.get_setting("backup_last_timestamp") or ""
        if last_backup_str:
            try:
                self._last_backup = datetime.fromisoformat(last_backup_str)
            except ValueError:
                self._last_backup = None
        else:
            self._last_backup = None
        
        if self._enabled and self._backup_folder:
            self.start()
        else:
            self.stop()
    
    def save_settings(
        self,
        enabled: bool,
        folder: str,
        frequency: str,
        max_backups: int,
    ) -> None:
        """Save backup settings."""
        self._enabled = enabled
        self._backup_folder = folder
        self._frequency = frequency if frequency in ("daily", "weekly", "manual") else "daily"
        self._max_backups = max(1, max_backups)
        
        settings_repository.set_setting("backup_enabled", "1" if enabled else "0")
        settings_repository.set_setting("backup_folder", folder)
        settings_repository.set_setting("backup_frequency", self._frequency)
        settings_repository.set_setting("backup_max_count", str(self._max_backups))
        
        if self._enabled and self._backup_folder:
            self.start()
        else:
            self.stop()
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    @property
    def backup_folder(self) -> str:
        return self._backup_folder
    
    @property
    def frequency(self) -> str:
        return self._frequency
    
    @property
    def max_backups(self) -> int:
        return self._max_backups
    
    @property
    def last_backup(self) -> Optional[datetime]:
        return self._last_backup
    
    def start(self) -> None:
        """Start the backup scheduler."""
        if not self._timer.isActive():
            # Check every hour
            self._timer.start(60 * 60 * 1000)
            # Do an immediate check
            self._check_and_backup()
    
    def stop(self) -> None:
        """Stop the backup scheduler."""
        if self._timer.isActive():
            self._timer.stop()
    
    def _check_and_backup(self) -> None:
        """Check if a backup is due and perform it if needed."""
        if not self._enabled or not self._backup_folder:
            return
        
        if self._frequency == "manual":
            return
        
        now = datetime.now()
        
        if self._last_backup is None:
            # Never backed up, do it now
            self.perform_backup()
            return
        
        if self._frequency == "daily":
            # Check if last backup was more than 24 hours ago
            if now - self._last_backup >= timedelta(hours=24):
                self.perform_backup()
        elif self._frequency == "weekly":
            # Check if last backup was more than 7 days ago
            if now - self._last_backup >= timedelta(days=7):
                self.perform_backup()
    
    def perform_backup(self) -> Tuple[bool, str]:
        """
        Perform a database backup.
        
        Returns:
            Tuple of (success, message)
        """
        if not self._backup_folder:
            return False, "No backup folder configured"
        
        backup_path = Path(self._backup_folder)
        if not backup_path.exists():
            try:
                backup_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                error_msg = f"Could not create backup folder: {e}"
                self.backup_failed.emit(error_msg)
                return False, error_msg
        
        db_path = get_database_path()
        if not db_path.exists():
            error_msg = "Database file not found"
            self.backup_failed.emit(error_msg)
            return False, error_msg
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"hustlenest_backup_{timestamp}.db"
        backup_file_path = backup_path / backup_filename
        
        try:
            shutil.copy2(db_path, backup_file_path)
        except OSError as e:
            error_msg = f"Backup failed: {e}"
            self.backup_failed.emit(error_msg)
            return False, error_msg
        
        # Update last backup timestamp
        self._last_backup = datetime.now()
        settings_repository.set_setting("backup_last_timestamp", self._last_backup.isoformat())
        
        # Cleanup old backups
        self._cleanup_old_backups()
        
        self.backup_completed.emit(str(backup_file_path))
        return True, f"Backup created: {backup_file_path}"
    
    def _cleanup_old_backups(self) -> None:
        """Remove old backups beyond the max count."""
        if not self._backup_folder:
            return
        
        backup_path = Path(self._backup_folder)
        if not backup_path.exists():
            return
        
        # Find all backup files
        backups: List[Path] = list(backup_path.glob("hustlenest_backup_*.db"))
        
        if len(backups) <= self._max_backups:
            return
        
        # Sort by modification time, oldest first
        backups.sort(key=lambda p: p.stat().st_mtime)
        
        # Remove oldest backups
        to_remove = len(backups) - self._max_backups
        for backup_file in backups[:to_remove]:
            try:
                backup_file.unlink()
            except OSError:
                pass
    
    def list_backups(self) -> List[Tuple[str, datetime, int]]:
        """
        List available backups.
        
        Returns:
            List of tuples (filename, created_date, size_bytes)
        """
        if not self._backup_folder:
            return []
        
        backup_path = Path(self._backup_folder)
        if not backup_path.exists():
            return []
        
        backups: List[Tuple[str, datetime, int]] = []
        for backup_file in backup_path.glob("hustlenest_backup_*.db"):
            try:
                stat = backup_file.stat()
                created = datetime.fromtimestamp(stat.st_mtime)
                size = stat.st_size
                backups.append((backup_file.name, created, size))
            except OSError:
                continue
        
        # Sort by date, newest first
        backups.sort(key=lambda x: x[1], reverse=True)
        return backups
    
    def restore_backup(self, backup_filename: str) -> Tuple[bool, str]:
        """
        Restore a backup file.
        
        Args:
            backup_filename: The name of the backup file to restore
            
        Returns:
            Tuple of (success, message)
        """
        if not self._backup_folder:
            return False, "No backup folder configured"
        
        backup_path = Path(self._backup_folder) / backup_filename
        if not backup_path.exists():
            return False, f"Backup file not found: {backup_filename}"
        
        db_path = get_database_path()
        
        # Create a safety backup before restoring
        safety_backup = db_path.with_suffix(".db.restore-backup")
        try:
            shutil.copy2(db_path, safety_backup)
        except OSError as e:
            return False, f"Could not create safety backup: {e}"
        
        try:
            shutil.copy2(backup_path, db_path)
            return True, f"Restored backup: {backup_filename}"
        except OSError as e:
            # Try to restore the safety backup
            try:
                shutil.copy2(safety_backup, db_path)
            except OSError:
                pass
            return False, f"Restore failed: {e}"
        finally:
            # Clean up safety backup
            try:
                safety_backup.unlink()
            except OSError:
                pass


def get_backup_scheduler() -> BackupScheduler:
    """Get the global backup scheduler instance."""
    return BackupScheduler.instance()
