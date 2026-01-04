from __future__ import annotations

from typing import Callable, Iterable, List, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


ColumnAccessor = Callable[[object], object]


class ListTableModel(QAbstractTableModel):
    def __init__(self, columns: Sequence[tuple[str, ColumnAccessor]], rows: Iterable[object] | None = None) -> None:
        super().__init__()
        self._columns: List[tuple[str, ColumnAccessor]] = list(columns)
        self._rows: List[object] = list(rows or [])

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object | None:  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            _, accessor = self._columns[index.column()]
            value = accessor(self._rows[index.row()])
            return "" if value is None else value

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> object | None:  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            title, _ = self._columns[section]
            return title
        return super().headerData(section, orientation, role)

    def update_rows(self, rows: Iterable[object]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def clear(self) -> None:
        self.update_rows([])
