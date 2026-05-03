from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QFont, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QGroupBox, QScrollArea, QFrame, QSizePolicy, QSpinBox,
    QPushButton,
)

from core.database import Database


# ---------------------------------------------------------------------------
# Tiny bar-chart widget (no external charting library needed)
# ---------------------------------------------------------------------------

class BarChart(QWidget):
    """Minimal bar chart drawn with QPainter."""

    BAR_COLOR = QColor(37, 99, 235)     # blue-600
    AXIS_COLOR = QColor(100, 100, 100)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: list[tuple[str, int]] = []
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_left = 36
        margin_bottom = 36
        margin_top = 10
        margin_right = 10

        chart_w = w - margin_left - margin_right
        chart_h = h - margin_bottom - margin_top

        max_val = max(v for _, v in self._data) if self._data else 1
        n = len(self._data)
        bar_width = max(4, chart_w // n - 4)

        # Axis lines
        pen = QPen(self.AXIS_COLOR, 1)
        painter.setPen(pen)
        painter.drawLine(margin_left, margin_top, margin_left, h - margin_bottom)
        painter.drawLine(margin_left, h - margin_bottom, w - margin_right, h - margin_bottom)

        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        for i, (label, val) in enumerate(self._data):
            bar_h = int(val / max_val * chart_h) if max_val else 0
            x = margin_left + i * (chart_w // n) + (chart_w // n - bar_width) // 2
            y = h - margin_bottom - bar_h

            painter.fillRect(x, y, bar_width, bar_h, self.BAR_COLOR)

            # value on top of bar
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            if bar_h > 14:
                painter.drawText(x, y - 2, bar_width, 14,
                                 Qt.AlignmentFlag.AlignHCenter, str(val))

            # x-axis label (rotated)
            painter.save()
            painter.translate(x + bar_width // 2, h - margin_bottom + 4)
            painter.rotate(40)
            painter.drawText(0, 0, label)
            painter.restore()

        painter.end()


# ---------------------------------------------------------------------------
# Stat card helper
# ---------------------------------------------------------------------------

def _stat_card(title: str, value: str) -> QWidget:
    card = QFrame()
    card.setFrameShape(QFrame.Shape.StyledPanel)
    card.setStyleSheet(
        "QFrame { background:#f3f4f6; border-radius:8px; padding:6px; }"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 8, 12, 8)
    lbl_title = QLabel(title)
    lbl_title.setStyleSheet("color:#6b7280; font-size:11px;")
    lbl_value = QLabel(value)
    lbl_value.setStyleSheet("font-size:22px; font-weight:bold;")
    lbl_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
    layout.addWidget(lbl_title)
    layout.addWidget(lbl_value)
    return card


# ---------------------------------------------------------------------------
# Stats Tab
# ---------------------------------------------------------------------------

class StatsTab(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self._scan_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("Statistics")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        title_row.addWidget(refresh_btn)
        outer.addLayout(title_row)

        # Scroll area for all stat content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(16)
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # --- Similarity stats group ---
        sim_group = QGroupBox("Similarity Statistics")
        sim_grid = QGridLayout(sim_group)
        self._card_mean = _stat_card("Mean Similarity", "—")
        self._card_median = _stat_card("Median Similarity", "—")
        self._card_min = _stat_card("Min Similarity", "—")
        self._card_max = _stat_card("Max Similarity", "—")
        self._card_pairs = _stat_card("Total Pairs", "—")
        for col, card in enumerate([
            self._card_mean, self._card_median,
            self._card_min, self._card_max, self._card_pairs,
        ]):
            sim_grid.addWidget(card, 0, col)
        self._content_layout.addWidget(sim_group)

        # Threshold counter
        threshold_group = QGroupBox("Pairs Above Threshold")
        threshold_layout = QHBoxLayout(threshold_group)
        threshold_layout.addWidget(QLabel("Threshold %:"))
        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(0, 100)
        self._threshold_spin.setValue(80)
        self._threshold_spin.valueChanged.connect(self._update_threshold)
        threshold_layout.addWidget(self._threshold_spin)
        self._threshold_label = QLabel("—")
        self._threshold_label.setStyleSheet("font-size:16px; font-weight:bold; margin-left:12px;")
        threshold_layout.addWidget(self._threshold_label)
        threshold_layout.addStretch()
        self._content_layout.addWidget(threshold_group)

        # --- File stats group ---
        file_group = QGroupBox("File / Submission Statistics")
        file_grid = QGridLayout(file_group)
        self._card_files = _stat_card("Total Files", "—")
        self._card_avg_lines = _stat_card("Avg Lines / File", "—")
        self._card_avg_words = _stat_card("Avg Words / File", "—")
        self._card_avg_chars = _stat_card("Avg Chars / File", "—")
        for col, card in enumerate([
            self._card_files, self._card_avg_lines,
            self._card_avg_words, self._card_avg_chars,
        ]):
            file_grid.addWidget(card, 0, col)
        self._content_layout.addWidget(file_group)

        # --- Histogram ---
        hist_group = QGroupBox("Similarity Distribution")
        hist_layout = QVBoxLayout(hist_group)
        self._histogram = BarChart()
        hist_layout.addWidget(self._histogram)
        self._content_layout.addWidget(hist_group)

        self._content_layout.addStretch()

        self._no_data_label = QLabel("No scan loaded. Run a scan first.")
        self._no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_data_label.setStyleSheet("color:#9ca3af; font-size:14px;")
        outer.addWidget(self._no_data_label)
        scroll.setVisible(False)
        self._scroll = scroll

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_scan(self, scan_id: int) -> None:
        self._scan_id = scan_id
        self._no_data_label.setVisible(False)
        self._scroll.setVisible(True)
        self._refresh()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        if self._scan_id is None:
            return

        sim_stats = self._db.get_similarity_stats(self._scan_id)
        file_stats = self._db.get_file_stats(self._scan_id)

        def _pct(v) -> str:
            return f"{v * 100:.1f}%" if v is not None else "—"

        def _fmt(v, decimals=1) -> str:
            return f"{v:.{decimals}f}" if v is not None else "—"

        self._card_mean.findChild(QLabel, "", Qt.FindChildOption.FindDirectChildrenOnly)
        # Update card values by finding the bold QLabel (second child)
        def _set_card(card: QWidget, value: str) -> None:
            labels = card.findChildren(QLabel)
            if len(labels) >= 2:
                labels[1].setText(value)

        _set_card(self._card_mean,   _pct(sim_stats.get("mean")))
        _set_card(self._card_median, _pct(sim_stats.get("median")))
        _set_card(self._card_min,    _pct(sim_stats.get("minimum")))
        _set_card(self._card_max,    _pct(sim_stats.get("maximum")))
        _set_card(self._card_pairs,  str(sim_stats.get("pair_count", "—")))

        _set_card(self._card_files,     str(file_stats.get("file_count", "—")))
        _set_card(self._card_avg_lines, _fmt(file_stats.get("avg_lines")))
        _set_card(self._card_avg_words, _fmt(file_stats.get("avg_words")))
        _set_card(self._card_avg_chars, _fmt(file_stats.get("avg_chars")))

        self._update_threshold()

        hist_data = self._db.get_similarity_histogram(self._scan_id, buckets=10)
        self._histogram.set_data(hist_data)

    def _update_threshold(self) -> None:
        if self._scan_id is None:
            return
        threshold = self._threshold_spin.value() / 100.0
        count = self._db.count_pairs_above_threshold(self._scan_id, threshold)
        self._threshold_label.setText(str(count))
