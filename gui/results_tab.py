from __future__ import annotations

import os
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QAbstractItemView, QComboBox,
)
from PyQt6.QtGui import QColor, QBrush

from core.database import Database, ComparisonRow, FileRow


# Colour thresholds for the Similarity % cell
def _sim_color(sim: float) -> QColor:
    if sim >= 0.85:
        return QColor(255, 99, 99)    # red
    if sim >= 0.60:
        return QColor(255, 200, 80)   # amber
    if sim >= 0.40:
        return QColor(200, 230, 255)  # light blue
    return QColor(200, 240, 200)      # light green


@dataclass(frozen=True)
class _ResultRow:
    cmp: ComparisonRow
    f1: FileRow
    f2: FileRow
    f1_folder_lower: str
    f2_folder_lower: str
    f1_basename: str
    f2_basename: str


class ResultsTab(QWidget):
    view_pair_requested = pyqtSignal(int, int, float)   # file1_id, file2_id, similarity

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self._scan_id: int | None = None
        self._all_rows: list[_ResultRow] = []
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(200)
        self._filter_timer.timeout.connect(self._apply_filter)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("Comparison Results")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()
        self._scan_label = QLabel("")
        self._scan_label.setStyleSheet("color: #666;")
        title_row.addWidget(self._scan_label)
        layout.addLayout(title_row)

        # Filter bar
        filter_group = QGroupBox("Filter")
        filter_layout = QHBoxLayout(filter_group)

        filter_layout.addWidget(QLabel("Keyword in folder names:"))
        self._keyword_edit = QLineEdit()
        self._keyword_edit.setPlaceholderText("e.g. smith  or  lab3")
        self._keyword_edit.setMaximumWidth(240)
        self._keyword_edit.textChanged.connect(self._schedule_filter)
        filter_layout.addWidget(self._keyword_edit)

        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("Min similarity %:"))
        self._min_sim_edit = QLineEdit("0")
        self._min_sim_edit.setMaximumWidth(60)
        self._min_sim_edit.textChanged.connect(self._schedule_filter)
        filter_layout.addWidget(self._min_sim_edit)

        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("Filename:"))
        self._filename_combo = QComboBox()
        self._filename_combo.setMinimumWidth(180)
        self._filename_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._filename_combo)

        filter_layout.addSpacing(20)
        clear_btn = QPushButton("Clear Filters")
        clear_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_btn)
        filter_layout.addStretch()

        layout.addWidget(filter_group)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Student 1", "Student 2", "Similarity %",
            "File 1 Path", "File 2 Path", "View",
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(5, 72)
        self._table.horizontalHeader().setSortIndicatorShown(True)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.doubleClicked.connect(self._on_row_double_click)
        layout.addWidget(self._table)

        # Status bar
        self._status_label = QLabel("No scan loaded.")
        self._status_label.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_scan(self, scan_id: int) -> None:
        """
        Load all comparison data for a scan into memory (_all_rows).
        Called once per scan load — subsequent tab switches use the
        cached list and never re-query the database.
        """
        self._scan_id = scan_id
        scan = self._db.get_scan(scan_id)
        if scan:
            self._scan_label.setText(
                f"Scan #{scan.id}  |  {scan.root_dir}  |  {scan.created_at}"
            )

        comparisons = self._db.get_comparisons_for_scan(scan_id)
        file_cache: dict[int, FileRow] = {}

        def _get_file(fid: int) -> FileRow:
            if fid not in file_cache:
                f = self._db.get_file(fid)
                if f:
                    file_cache[fid] = f
            return file_cache[fid]

        self._all_rows = []
        for cmp in comparisons:
            f1 = _get_file(cmp.file1_id)
            f2 = _get_file(cmp.file2_id)
            self._all_rows.append(_ResultRow(
                cmp=cmp,
                f1=f1,
                f2=f2,
                f1_folder_lower=f1.folder.lower(),
                f2_folder_lower=f2.folder.lower(),
                f1_basename=os.path.basename(f1.path),
                f2_basename=os.path.basename(f2.path),
            ))

        self._populate_filename_filter()
        self._filter_timer.stop()
        self._apply_filter()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _schedule_filter(self, *_args: object) -> None:
        self._filter_timer.start()

    def _apply_filter(self, *_args: object) -> None:
        self._filter_timer.stop()
        keyword = self._keyword_edit.text().strip().lower()
        selected_filename = self._filename_combo.currentData()
        try:
            min_sim = float(self._min_sim_edit.text()) / 100.0
        except ValueError:
            min_sim = 0.0

        visible = [
            row
            for row in self._all_rows
            if row.cmp.similarity >= min_sim
            and (
                not keyword
                or keyword in row.f1_folder_lower
                or keyword in row.f2_folder_lower
            )
            and (
                not selected_filename
                or (
                    row.f1_basename == selected_filename
                    and row.f2_basename == selected_filename
                )
            )
        ]

        self._populate_table(visible)
        self._status_label.setText(
            f"Showing {len(visible)} of {len(self._all_rows)} pair(s)"
        )

    def _clear_filters(self) -> None:
        self._filter_timer.stop()
        self._keyword_edit.blockSignals(True)
        self._min_sim_edit.blockSignals(True)
        self._filename_combo.blockSignals(True)
        self._keyword_edit.clear()
        self._min_sim_edit.setText("0")
        self._filename_combo.setCurrentIndex(0)
        self._keyword_edit.blockSignals(False)
        self._min_sim_edit.blockSignals(False)
        self._filename_combo.blockSignals(False)
        self._apply_filter()

    def _populate_filename_filter(self) -> None:
        filenames = sorted({
            basename
            for row in self._all_rows
            for basename in (row.f1_basename, row.f2_basename)
        })

        self._filename_combo.blockSignals(True)
        self._filename_combo.clear()
        self._filename_combo.addItem("All files", None)
        for filename in filenames:
            self._filename_combo.addItem(filename, filename)
        self._filename_combo.blockSignals(False)

    def _populate_table(
        self, rows: list[_ResultRow]
    ) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))

        for row_idx, row in enumerate(rows):
            cmp = row.cmp
            f1 = row.f1
            f2 = row.f2
            sim_pct = round(cmp.similarity * 100, 2)

            items = [
                QTableWidgetItem(f1.folder),
                QTableWidgetItem(f2.folder),
                _NumericItem(f"{sim_pct:.2f}%", cmp.similarity),
                QTableWidgetItem(f1.path),
                QTableWidgetItem(f2.path),
                QTableWidgetItem("View"),
            ]

            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 2:
                    item.setBackground(QBrush(_sim_color(cmp.similarity)))
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                elif col == 5:
                    item.setForeground(QBrush(QColor(37, 99, 235)))
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                item.setData(Qt.ItemDataRole.UserRole, cmp)
                self._table.setItem(row_idx, col, item)

        self._table.setSortingEnabled(True)

    def _on_cell_clicked(self, row: int, column: int) -> None:
        if column != 5:
            return
        self._emit_pair_for_row(row)

    def _on_row_double_click(self, index) -> None:
        self._emit_pair_for_row(index.row())

    def _emit_pair_for_row(self, row: int) -> None:
        item = self._table.item(row, 0)
        if not item:
            return
        cmp = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(cmp, ComparisonRow):
            self.view_pair_requested.emit(cmp.file1_id, cmp.file2_id, cmp.similarity)


# ---------------------------------------------------------------------------
# Custom sortable numeric item
# ---------------------------------------------------------------------------

class _NumericItem(QTableWidgetItem):
    """Table item that sorts numerically even though it displays as text."""

    def __init__(self, text: str, value: float) -> None:
        super().__init__(text)
        self._value = value

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, _NumericItem):
            return self._value < other._value
        return super().__lt__(other)
