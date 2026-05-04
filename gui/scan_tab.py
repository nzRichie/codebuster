from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QProgressBar, QTextEdit,
    QGroupBox, QScrollArea, QFrame, QSizePolicy, QCheckBox,
)

from core.scanner import find_files, FoundFile
from core.comparator import compare_files, FileStats, ComparisonResult
from core.database import Database


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class ScanWorker(QThread):
    progress = pyqtSignal(int, int)          # completed, total
    log_message = pyqtSignal(str)
    finished = pyqtSignal(int)               # scan_id
    error = pyqtSignal(str)

    def __init__(
        self,
        root_dir: str,
        target_names: list[str],
        db_path: str,
        only_matching_filenames: bool,
    ) -> None:
        super().__init__()
        self._root_dir = root_dir
        self._target_names = target_names
        self._db_path = db_path  # path only — connection opened inside the thread
        self._only_matching_filenames = only_matching_filenames

    def run(self) -> None:
        # Open a fresh connection inside this thread to satisfy SQLite's
        # same-thread requirement.
        db = Database(db_dir=os.path.dirname(self._db_path) or ".")
        scan_id: int | None = None
        try:
            self.log_message.emit(f"Scanning {self._root_dir} …")
            files: list[FoundFile] = find_files(self._root_dir, self._target_names)

            if not files:
                self.error.emit("No matching files found in the selected directory.")
                return

            self.log_message.emit(f"Found {len(files)} file(s). Normalizing and comparing …")

            file_id_map: dict[str, int] = {}

            def _progress(done: int, total: int) -> None:
                self.progress.emit(done, total)

            stats_list, comparisons = compare_files(
                files,
                progress_callback=_progress,
                only_matching_filenames=self._only_matching_filenames,
            )
            skipped_count = len(files) - len(stats_list)

            if not stats_list:
                self.error.emit("No non-empty matching files found in the selected directory.")
                return

            if skipped_count:
                self.log_message.emit(f"Skipped {skipped_count} empty file(s).")

            self.log_message.emit("Saving results …")
            scan_id = db.insert_scan(self._root_dir, self._target_names)

            # Persist file rows
            file_rows = [
                (
                    scan_id,
                    stat.path,
                    stat.folder,
                    stat.line_count,
                    stat.word_count,
                    stat.char_count,
                    stat.normalized_path,
                )
                for stat in stats_list
            ]
            file_ids = db.insert_file_rows(file_rows)
            file_id_map = {
                stat.path: file_id
                for stat, file_id in zip(stats_list, file_ids)
            }

            # Persist comparison rows
            db.insert_comparison_rows(
                [
                    (
                        scan_id,
                        file_id_map[cmp.file1.path],
                        file_id_map[cmp.file2.path],
                        cmp.similarity,
                    )
                    for cmp in comparisons
                ]
            )

            db.delete_older_matching_scans(
                scan_id,
                self._root_dir,
                self._target_names,
            )
            self.log_message.emit(
                f"Done. {len(comparisons)} pair(s) compared. Results saved."
            )
            self.finished.emit(scan_id)

        except Exception as exc:  # noqa: BLE001
            if scan_id is not None:
                db.delete_scan(scan_id)
            self.error.emit(str(exc))
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Filename entry list widget
# ---------------------------------------------------------------------------

class FilenameListWidget(QWidget):
    """A dynamic list of filename inputs with add/remove controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._rows: list[QLineEdit] = []
        self._add_row("MergeRuns.java")

    def _add_row(self, text: str = "") -> None:
        row = QHBoxLayout()
        edit = QLineEdit(text)
        edit.setPlaceholderText("e.g. Assignment1.java, .py, .cs, or .js")
        edit.setMinimumWidth(240)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setToolTip("Remove this filename")
        remove_btn.clicked.connect(lambda: self._remove_row(edit, container))

        row.addWidget(edit)
        row.addWidget(remove_btn)

        container = QWidget()
        container.setLayout(row)
        self._rows.append(edit)
        self._layout.addWidget(container)

    def _remove_row(self, edit: QLineEdit, container: QWidget) -> None:
        if len(self._rows) <= 1:
            return  # always keep at least one row
        self._rows.remove(edit)
        container.deleteLater()

    def add_row(self) -> None:
        self._add_row()

    def get_filenames(self) -> list[str]:
        return [e.text().strip() for e in self._rows if e.text().strip()]


# ---------------------------------------------------------------------------
# Scan Tab
# ---------------------------------------------------------------------------

class ScanTab(QWidget):
    scan_completed = pyqtSignal(int)   # emitted with scan_id when done

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self._worker: ScanWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(16)

        # --- Title ---
        title = QLabel("New Scan")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        outer.addWidget(title)

        # --- Directory picker ---
        dir_group = QGroupBox("Submission Root Directory")
        dir_layout = QHBoxLayout(dir_group)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Select the folder containing student submissions …")
        self._dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse …")
        browse_btn.clicked.connect(self._browse_dir)
        dir_layout.addWidget(self._dir_edit)
        dir_layout.addWidget(browse_btn)
        outer.addWidget(dir_group)

        # --- Filename list ---
        fn_group = QGroupBox("Target Filename(s) or Extension(s) to Compare")
        fn_layout = QVBoxLayout(fn_group)
        fn_help = QLabel(
            "Enter exact filenames or file types, e.g. Assignment1.java, .py, .cs, or .js."
        )
        fn_help.setStyleSheet("color:#4b5563; font-size:12px;")
        self._filename_list = FilenameListWidget()
        add_fn_btn = QPushButton("+ Add Target")
        add_fn_btn.setFixedWidth(130)
        add_fn_btn.clicked.connect(self._filename_list.add_row)
        fn_layout.addWidget(fn_help)
        fn_layout.addWidget(self._filename_list)
        fn_layout.addWidget(add_fn_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(fn_group)

        # --- Comparison options ---
        options_group = QGroupBox("Comparison Options")
        options_layout = QVBoxLayout(options_group)
        self._matching_names_check = QCheckBox("Only compare files with matching filenames")
        self._matching_names_check.setChecked(True)
        self._matching_names_check.setToolTip(
            "When scanning by extension, skip comparisons between differently named files."
        )
        options_layout.addWidget(self._matching_names_check)
        outer.addWidget(options_group)

        # --- Scan button ---
        self._scan_btn = QPushButton("  Start Scan  ")
        self._scan_btn.setStyleSheet(
            "QPushButton { background:#2563eb; color:white; font-size:14px;"
            " padding:8px 24px; border-radius:6px; }"
            "QPushButton:hover { background:#1d4ed8; }"
            "QPushButton:disabled { background:#93c5fd; }"
        )
        self._scan_btn.clicked.connect(self._start_scan)
        outer.addWidget(self._scan_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # --- Progress bar ---
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        # --- Log output ---
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(160)
        self._log.setStyleSheet("font-family: monospace; font-size: 12px;")
        log_layout.addWidget(self._log)
        outer.addWidget(log_group)

        outer.addStretch()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _browse_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Submission Root Directory", os.path.expanduser("~")
        )
        if path:
            self._dir_edit.setText(path)

    def _start_scan(self) -> None:
        root_dir = self._dir_edit.text().strip()
        if not root_dir or not os.path.isdir(root_dir):
            self._log.append("<font color='red'>Please select a valid directory.</font>")
            return

        filenames = self._filename_list.get_filenames()
        if not filenames:
            self._log.append("<font color='red'>Please enter at least one target filename or extension.</font>")
            return

        self._scan_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._log.clear()

        self._worker = ScanWorker(
            root_dir,
            filenames,
            self._db.path,
            self._matching_names_check.isChecked(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        pct = int(done / total * 100) if total else 0
        if total and done >= total:
            pct = 95
        self._progress_bar.setValue(pct)
        self._progress_bar.setFormat(f"{done} / {total} pairs  ({pct}%)")

    def _on_log(self, msg: str) -> None:
        self._log.append(msg)

    def _on_finished(self, scan_id: int) -> None:
        self._scan_btn.setEnabled(True)
        self._progress_bar.setValue(100)
        self.scan_completed.emit(scan_id)

    def _on_error(self, msg: str) -> None:
        self._scan_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._log.append(f"<font color='red'><b>Error:</b> {msg}</font>")
