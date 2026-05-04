from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QDialog, QDialogButtonBox, QLabel, QListWidget,
    QListWidgetItem, QHBoxLayout, QPushButton, QMessageBox,
    QStatusBar,
)

from core.database import Database, ScanRow
from gui.scan_tab import ScanTab
from gui.results_tab import ResultsTab
from gui.diff_viewer import DiffViewer
from gui.stats_tab import StatsTab


# ---------------------------------------------------------------------------
# Scan history dialog
# ---------------------------------------------------------------------------

class ScanHistoryDialog(QDialog):
    def __init__(self, scans: list[ScanRow], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scan History")
        self.setMinimumWidth(560)
        self.selected_scan_id: int | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a previous scan to load:"))

        self._list = QListWidget()
        for scan in scans:
            item_text = (
                f"#{scan.id}  |  {scan.created_at}  |  {scan.root_dir}  "
                f"[{scan.filenames}]"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, scan.id)
            self._list.addItem(item)
        self._list.setCurrentRow(0)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        item = self._list.currentItem()
        if item:
            self.selected_scan_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    # Tab indices
    TAB_SCAN = 0
    TAB_RESULTS = 1
    TAB_DIFF = 2
    TAB_STATS = 3

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CodeBuster — Plagiarism Detector")
        self.resize(1280, 800)

        self._db = Database(db_dir=".")

        self._build_ui()
        self._auto_load_latest_scan()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # Scan tab
        self._scan_tab = ScanTab(self._db)
        self._scan_tab.scan_completed.connect(self._on_scan_completed)
        self._tabs.addTab(self._scan_tab, "  Scan  ")

        # Results tab
        self._results_tab = ResultsTab(self._db)
        self._results_tab.view_pair_requested.connect(self._on_view_pair)
        self._tabs.addTab(self._results_tab, "  Results  ")

        # Diff viewer tab
        self._diff_viewer = DiffViewer(self._db)
        self._tabs.addTab(self._diff_viewer, "  Diff Viewer  ")

        # Stats tab
        self._stats_tab = StatsTab(self._db)
        self._tabs.addTab(self._stats_tab, "  Statistics  ")

        root_layout.addWidget(self._tabs)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Menu bar
        self._build_menu()

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        new_scan_action = file_menu.addAction("&New Scan")
        new_scan_action.setShortcut("Ctrl+N")
        new_scan_action.triggered.connect(
            lambda: self._tabs.setCurrentIndex(self.TAB_SCAN)
        )

        load_scan_action = file_menu.addAction("&Load Previous Scan …")
        load_scan_action.setShortcut("Ctrl+O")
        load_scan_action.triggered.connect(self._load_previous_scan)

        file_menu.addSeparator()

        delete_scan_action = file_menu.addAction("&Delete Current Scan …")
        delete_scan_action.triggered.connect(self._delete_current_scan)

        file_menu.addSeparator()

        quit_action = file_menu.addAction("&Quit")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)

        view_menu = menu_bar.addMenu("&View")
        for idx, label in enumerate(["Scan", "Results", "Diff Viewer", "Statistics"]):
            action = view_menu.addAction(label)
            action.triggered.connect(
                lambda _checked, i=idx: self._tabs.setCurrentIndex(i)
            )

    # ------------------------------------------------------------------
    # Auto-load
    # ------------------------------------------------------------------

    def _auto_load_latest_scan(self) -> None:
        scan = self._db.get_latest_scan()
        if scan:
            self._load_scan(scan.id)
            self._status_bar.showMessage(
                f"Loaded previous scan #{scan.id} from {scan.created_at}", 6000
            )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_scan_completed(self, scan_id: int) -> None:
        self._load_scan(scan_id)
        self._tabs.setCurrentIndex(self.TAB_RESULTS)
        self._status_bar.showMessage(f"Scan #{scan_id} complete.", 5000)

    def _on_view_pair(self, file1_id: int, file2_id: int, similarity: float) -> None:
        self._diff_viewer.load_pair(file1_id, file2_id, similarity)
        self._tabs.setCurrentIndex(self.TAB_DIFF)

    def _load_scan(self, scan_id: int) -> None:
        self._current_scan_id = scan_id
        self._results_tab.load_scan(scan_id)
        self._stats_tab.load_scan(scan_id)
        self._diff_viewer.load_scan(scan_id)

    def _load_previous_scan(self) -> None:
        scans = self._db.get_all_scans()
        if not scans:
            QMessageBox.information(self, "No Scans", "No previous scans found.")
            return

        dlg = ScanHistoryDialog(scans, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_scan_id is not None:
            self._load_scan(dlg.selected_scan_id)
            self._tabs.setCurrentIndex(self.TAB_RESULTS)
            self._status_bar.showMessage(
                f"Loaded scan #{dlg.selected_scan_id}.", 4000
            )

    def _delete_current_scan(self) -> None:
        scan_id = getattr(self, "_current_scan_id", None)
        if scan_id is None:
            QMessageBox.information(self, "No Scan", "No scan is currently loaded.")
            return

        reply = QMessageBox.question(
            self,
            "Delete Scan",
            f"Delete scan #{scan_id} and all its comparison data?\n"
            "Normalized files on disk will NOT be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_scan(scan_id)
            self._current_scan_id = None
            self._status_bar.showMessage(f"Scan #{scan_id} deleted.", 4000)
            # Try to load next available scan
            self._auto_load_latest_scan()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._db.close()
        super().closeEvent(event)
