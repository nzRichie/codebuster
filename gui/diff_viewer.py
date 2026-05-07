from __future__ import annotations

import os
from html import escape
from difflib import SequenceMatcher

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtGui import (
    QTextCursor, QTextCharFormat, QTextFormat, QColor, QFont,
    QDesktopServices,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QTextEdit, QFrame, QComboBox, QFileDialog, QMessageBox,
)

from core.database import Database, FileRow, ComparisonRow
from core.normalizer.base import get_normalizer


# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------
MATCH_BG  = QColor(0xFF, 0xE0, 0x66)   # yellow  – identical region
UNIQUE_BG = QColor(0xFF, 0xD6, 0xD6)   # red-ish – text only in this file
MATCH_HEX  = "#ffe066"
UNIQUE_HEX = "#ffd6d6"


# ---------------------------------------------------------------------------
# Scroll-synced read-only text pane
# ---------------------------------------------------------------------------

class CodePane(QTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        font = QFont("Courier New", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self._partner: CodePane | None = None
        self._syncing = False
        self._sync_enabled = True
        self.verticalScrollBar().valueChanged.connect(self._on_vscroll)
        self.horizontalScrollBar().valueChanged.connect(self._on_hscroll)

    def set_partner(self, other: "CodePane") -> None:
        self._partner = other

    def set_sync_enabled(self, enabled: bool) -> None:
        self._sync_enabled = enabled

    def _on_vscroll(self, value: int) -> None:
        if self._sync_enabled and self._partner and not self._partner._syncing:
            self._syncing = True
            my_max = self.verticalScrollBar().maximum()
            if my_max:
                pct = value / my_max
                other_max = self._partner.verticalScrollBar().maximum()
                self._partner.verticalScrollBar().setValue(int(pct * other_max))
            self._syncing = False

    def _on_hscroll(self, value: int) -> None:
        if self._sync_enabled and self._partner and not self._partner._syncing:
            self._syncing = True
            my_max = self.horizontalScrollBar().maximum()
            if my_max:
                pct = value / my_max
                other_max = self._partner.horizontalScrollBar().maximum()
                self._partner.horizontalScrollBar().setValue(int(pct * other_max))
            self._syncing = False


# ---------------------------------------------------------------------------
# Diff rendering helpers
# ---------------------------------------------------------------------------

def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def _safe_export_filename(file1: FileRow, file2: FileRow) -> str:
    name = f"{file1.folder}_vs_{file2.folder}_diff.html"
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)


def _compute_line_tags_normalized(
    text_a: str, text_b: str, normalizer
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (lines_a, lines_b, tags_a, tags_b) using normalized content.

    Matching is determined by comparing the concatenated normalized strings,
    then mapping equal normalized character ranges back to the original lines.
    A non-empty line is tagged as a match only when every normalized character
    on that line is part of an equal range. Lines whose normalized form is
    empty (comment-only or whitespace-only) are tagged 'none' and receive no
    highlight colour.
    """
    lines_a = text_a.splitlines(keepends=False)
    lines_b = text_b.splitlines(keepends=False)

    norm_a = normalizer.normalize_lines(text_a)
    norm_b = normalizer.normalize_lines(text_b)

    # Keep tag arrays aligned exactly with the displayed original lines.
    while len(norm_a) < len(lines_a):
        norm_a.append("")
    while len(norm_b) < len(lines_b):
        norm_b.append("")
    norm_a = norm_a[:len(lines_a)]
    norm_b = norm_b[:len(lines_b)]

    # "none" for blank-normalized lines (comments/whitespace), else "unique"
    tags_a: list[str] = ["none" if not n else "unique" for n in norm_a]
    tags_b: list[str] = ["none" if not n else "unique" for n in norm_b]

    text_norm_a = "".join(norm_a)
    text_norm_b = "".join(norm_b)
    char_to_line_a = [
        line_index
        for line_index, normalized_line in enumerate(norm_a)
        for _ in normalized_line
    ]
    char_to_line_b = [
        line_index
        for line_index, normalized_line in enumerate(norm_b)
        for _ in normalized_line
    ]
    matched_chars_a = [0] * len(norm_a)
    matched_chars_b = [0] * len(norm_b)

    matcher = SequenceMatcher(None, text_norm_a, text_norm_b, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for k in range(i1, i2):
                matched_chars_a[char_to_line_a[k]] += 1
            for k in range(j1, j2):
                matched_chars_b[char_to_line_b[k]] += 1

    for i, normalized_line in enumerate(norm_a):
        if normalized_line and matched_chars_a[i] == len(normalized_line):
            tags_a[i] = "match"
    for i, normalized_line in enumerate(norm_b):
        if normalized_line and matched_chars_b[i] == len(normalized_line):
            tags_b[i] = "match"

    return lines_a, lines_b, tags_a, tags_b


def _line_extra_selections(
    pane: CodePane, lines: list[str], tags: list[str]
) -> None:
    """
    Populate a pane with plain text and apply line-level ExtraSelections
    for highlighting. This is the Qt-idiomatic approach that works
    regardless of whether the widget is currently visible.
    """
    pane.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    if not lines:
        pane.setPlainText("(File is empty)")
        pane.setExtraSelections([])
        pane.moveCursor(QTextCursor.MoveOperation.Start)
        return

    pane.setPlainText("\n".join(lines))

    doc = pane.document()
    selections: list[QTextEdit.ExtraSelection] = []

    for i, tag in enumerate(tags):
        if tag not in ("match", "unique"):
            continue
        block = doc.findBlockByNumber(i)
        if not block.isValid():
            continue

        color = MATCH_BG if tag == "match" else UNIQUE_BG
        fmt = QTextCharFormat()
        fmt.setBackground(color)
        # FullWidthSelection extends the highlight to the right edge of the widget
        fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)

        sel = QTextEdit.ExtraSelection()
        sel.format = fmt
        cur = QTextCursor(block)
        cur.clearSelection()
        sel.cursor = cur
        selections.append(sel)

    pane.setExtraSelections(selections)
    pane.moveCursor(QTextCursor.MoveOperation.Start)


def _html_line_blocks(lines: list[str], tags: list[str]) -> str:
    if not lines:
        return '<div class="line">(File is empty)</div>'

    blocks: list[str] = []
    for line, tag in zip(lines, tags):
        cls = f"line {tag}" if tag in ("match", "unique") else "line"
        blocks.append(f'<div class="{cls}">{escape(line)}</div>')
    return "".join(blocks)


def _char_extra_selections(
    pane: CodePane,
    text: str,
    opcodes: list[tuple[str, int, int, int, int]],
    is_a: bool,
) -> None:
    """
    Populate a pane with plain text and apply CHARACTER-level ExtraSelections.
    Used for normalized (single-line) content where line-level diff is useless.
    """
    pane.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    if not text:
        pane.setPlainText("(File is empty)")
        pane.setExtraSelections([])
        pane.moveCursor(QTextCursor.MoveOperation.Start)
        return

    pane.setPlainText(text)

    doc = pane.document()
    selections: list[QTextEdit.ExtraSelection] = []

    for op, i1, i2, j1, j2 in opcodes:
        if is_a:
            start, end = i1, i2
            if op == "insert":
                continue   # nothing in text_a for an insert
        else:
            start, end = j1, j2
            if op == "delete":
                continue   # nothing in text_b for a delete

        if start == end:
            continue

        color = MATCH_BG if op == "equal" else UNIQUE_BG
        fmt = QTextCharFormat()
        fmt.setBackground(color)

        sel = QTextEdit.ExtraSelection()
        sel.format = fmt
        cur = QTextCursor(doc)
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        sel.cursor = cur
        selections.append(sel)

    pane.setExtraSelections(selections)
    pane.moveCursor(QTextCursor.MoveOperation.Start)


def _html_char_spans(
    text: str,
    opcodes: list[tuple[str, int, int, int, int]],
    is_a: bool,
) -> str:
    if not text:
        return '<span class="empty">(File is empty)</span>'

    spans: list[str] = []
    for op, i1, i2, j1, j2 in opcodes:
        if is_a:
            start, end = i1, i2
            if op == "insert":
                continue
        else:
            start, end = j1, j2
            if op == "delete":
                continue

        if start == end:
            continue

        cls = "match" if op == "equal" else "unique"
        spans.append(f'<span class="{cls}">{escape(text[start:end])}</span>')

    return "".join(spans)


def _build_diff_html(
    title: str,
    left_label: str,
    right_label: str,
    left_body: str,
    right_body: str,
    similarity: float,
    mode_label: str,
    wrap_long_lines: bool = False,
) -> str:
    escaped_title = escape(title)
    body_class = ' class="wrap-long-lines"' if wrap_long_lines else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escaped_title}</title>
  <style>
    :root {{
      --match-bg: {MATCH_HEX};
      --unique-bg: {UNIQUE_HEX};
      --border: #d1d5db;
      --muted: #4b5563;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      padding: 24px;
      color: #111827;
      background: #f9fafb;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 22px;
    }}
    .meta {{
      margin-bottom: 16px;
      color: var(--muted);
      font-size: 14px;
    }}
    .legend {{
      display: flex;
      gap: 18px;
      align-items: center;
      margin-bottom: 16px;
      font-size: 14px;
    }}
    .legend-item {{
      display: inline-flex;
      gap: 6px;
      align-items: center;
    }}
    .swatch {{
      width: 16px;
      height: 16px;
      border: 1px solid #9ca3af;
      display: inline-block;
    }}
    .swatch.match {{
      background: var(--match-bg);
    }}
    .swatch.unique {{
      background: var(--unique-bg);
    }}
    .diff-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 16px;
      height: calc(100vh - 150px);
      min-height: 360px;
    }}
    .file-panel {{
      min-width: 0;
      min-height: 0;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: white;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .file-title {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      font-weight: 700;
      font-size: 13px;
      background: #f3f4f6;
    }}
    .code {{
      flex: 1;
      min-height: 0;
      overflow: auto;
      margin: 0;
      padding: 8px 0;
      white-space: pre;
      font: 13px/1.25 "Courier New", Courier, monospace;
      tab-size: 4;
    }}
    body.wrap-long-lines .code {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .line {{
      min-height: 1.25em;
      padding: 0 12px;
      white-space: pre;
    }}
    .match {{
      background: var(--match-bg);
    }}
    .unique {{
      background: var(--unique-bg);
    }}
    .empty {{
      padding: 0 12px;
    }}
  </style>
</head>
<body{body_class}>
  <h1>{escaped_title}</h1>
  <div class="meta">Similarity: {similarity * 100:.1f}% · View: {escape(mode_label)}</div>
  <div class="legend" aria-label="Highlight legend">
    <span class="legend-item"><span class="swatch match"></span>Matching region</span>
    <span class="legend-item"><span class="swatch unique"></span>Unique region</span>
  </div>
  <main class="diff-grid">
    <section class="file-panel">
      <div class="file-title">{escape(left_label)}</div>
      <div class="code">{left_body}</div>
    </section>
    <section class="file-panel">
      <div class="file-title">{escape(right_label)}</div>
      <div class="code">{right_body}</div>
    </section>
  </main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Diff Viewer widget
# ---------------------------------------------------------------------------

class DiffViewer(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self._file1: FileRow | None = None
        self._file2: FileRow | None = None
        self._similarity: float = 0.0
        self._show_normalized = False
        self._sync_scrolling = True
        self._comparisons: list[ComparisonRow] = []
        self._file_cache: dict[int, FileRow] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ---- Header row ----
        header = QHBoxLayout()

        # Pair selector combo
        header.addWidget(QLabel("Pair:"))
        self._pair_combo = QComboBox()
        self._pair_combo.setMinimumWidth(360)
        self._pair_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._pair_combo.currentIndexChanged.connect(self._on_combo_changed)
        header.addWidget(self._pair_combo, stretch=1)

        header.addSpacing(16)

        self._sim_label = QLabel()
        self._sim_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        header.addWidget(self._sim_label)

        header.addStretch()

        self._toggle_btn = QPushButton("Show Normalized")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setStyleSheet(
            "QPushButton { padding:4px 14px; border-radius:5px;"
            " background:#e5e7eb; }"
            "QPushButton:checked { background:#2563eb; color:white; }"
        )
        self._toggle_btn.toggled.connect(self._on_toggle)
        header.addWidget(self._toggle_btn)

        self._sync_scroll_btn = QPushButton("Sync Scrolling: On")
        self._sync_scroll_btn.setCheckable(True)
        self._sync_scroll_btn.setChecked(True)
        self._sync_scroll_btn.setStyleSheet(
            "QPushButton { padding:4px 14px; border-radius:5px;"
            " background:#e5e7eb; }"
            "QPushButton:checked { background:#2563eb; color:white; }"
        )
        self._sync_scroll_btn.toggled.connect(self._on_scroll_sync_toggled)
        header.addWidget(self._sync_scroll_btn)

        self._export_btn = QPushButton("Export HTML")
        self._export_btn.setStyleSheet(
            "QPushButton { padding:4px 14px; border-radius:5px;"
            " background:#e5e7eb; }"
        )
        self._export_btn.clicked.connect(self._on_export_html)
        header.addWidget(self._export_btn)

        layout.addLayout(header)

        # ---- Legend ----
        legend = QHBoxLayout()
        for color_hex, label in (
            (MATCH_HEX, "Matching region"),
            (UNIQUE_HEX, "Unique region"),
        ):
            swatch = QFrame()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(f"background:{color_hex}; border:1px solid #aaa;")
            legend.addWidget(swatch)
            legend.addWidget(QLabel(label))
            legend.addSpacing(16)
        legend.addStretch()
        layout.addLayout(legend)

        # ---- File header labels ----
        fname_row = QHBoxLayout()
        self._fname1_label = QLabel()
        self._fname1_label.setStyleSheet("font-weight:bold; font-size:12px;")
        self._fname2_label = QLabel()
        self._fname2_label.setStyleSheet("font-weight:bold; font-size:12px;")
        fname_row.addWidget(self._fname1_label, 1)
        fname_row.addWidget(self._fname2_label, 1)
        layout.addLayout(fname_row)

        # ---- Splitter with the two code panes ----
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._pane1 = CodePane()
        self._pane2 = CodePane()
        self._pane1.set_partner(self._pane2)
        self._pane2.set_partner(self._pane1)
        self._splitter.addWidget(self._pane1)
        self._splitter.addWidget(self._pane2)
        self._splitter.setSizes([1, 1])
        layout.addWidget(self._splitter, stretch=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_scan(self, scan_id: int) -> None:
        """Populate the pair dropdown from a scan. Called when a scan is loaded."""
        comparisons = self._db.get_comparisons_for_scan(scan_id)
        self._comparisons = []
        self._file_cache.clear()

        # Block signals for the entire combo rebuild including setCurrentIndex so
        # _on_combo_changed never fires from here — we do one explicit load below.
        self._pair_combo.blockSignals(True)
        self._pair_combo.clear()
        for cmp in comparisons:
            f1 = self._cached_file(cmp.file1_id)
            f2 = self._cached_file(cmp.file2_id)
            if f1 and f2:
                self._comparisons.append(cmp)
                label = (
                    f"{f1.folder}  vs  {f2.folder}"
                    f"  —  {cmp.similarity * 100:.1f}%"
                )
                self._pair_combo.addItem(label)
        self._pair_combo.setCurrentIndex(0 if self._comparisons else -1)
        self._pair_combo.blockSignals(False)

        # Explicitly load the first pair now.
        if self._comparisons:
            self._load_from_comparisons(0)
        else:
            self._file1 = None
            self._file2 = None
            self._similarity = 0.0
            self._refresh()

    def load_pair(self, file1_id: int, file2_id: int, similarity: float) -> None:
        """Load a specific pair, e.g. when 'View →' is clicked in Results tab."""
        self._file1 = self._cached_file(file1_id)
        self._file2 = self._cached_file(file2_id)
        self._similarity = similarity

        # Sync combo box without re-triggering load
        self._pair_combo.blockSignals(True)
        for i, cmp in enumerate(self._comparisons):
            if cmp.file1_id == file1_id and cmp.file2_id == file2_id:
                self._pair_combo.setCurrentIndex(i)
                break
        self._pair_combo.blockSignals(False)

        self._show_normalized = False
        self._toggle_btn.blockSignals(True)
        self._toggle_btn.setChecked(False)
        self._toggle_btn.setText("Show Normalized")
        self._toggle_btn.blockSignals(False)

        self._refresh()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cached_file(self, file_id: int) -> FileRow | None:
        if file_id not in self._file_cache:
            row = self._db.get_file(file_id)
            if row:
                self._file_cache[file_id] = row
        return self._file_cache.get(file_id)

    def _current_paths_and_labels(self) -> tuple[str, str, str, str, str]:
        if not self._file1 or not self._file2:
            raise ValueError("No pair loaded")

        if self._show_normalized:
            path1 = self._file1.normalized_path
            path2 = self._file2.normalized_path
            label_suffix = " [normalized]"
            mode_label = "Normalized"
        else:
            path1 = self._file1.path
            path2 = self._file2.path
            label_suffix = ""
            mode_label = "Original"

        fname1 = os.path.basename(path1) + label_suffix
        fname2 = os.path.basename(path2) + label_suffix
        label1 = f"{self._file1.folder} / {fname1}"
        label2 = f"{self._file2.folder} / {fname2}"
        return path1, path2, label1, label2, mode_label

    def _load_from_comparisons(self, index: int) -> None:
        if not (0 <= index < len(self._comparisons)):
            return
        cmp = self._comparisons[index]
        self._file1 = self._cached_file(cmp.file1_id)
        self._file2 = self._cached_file(cmp.file2_id)
        self._similarity = cmp.similarity

        self._show_normalized = False
        self._toggle_btn.blockSignals(True)
        self._toggle_btn.setChecked(False)
        self._toggle_btn.setText("Show Normalized")
        self._toggle_btn.blockSignals(False)

        self._refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        """Re-apply content when the widget becomes visible for the first time.

        load_scan / load_pair may be called before the window is shown, while
        the widget is still hidden and not yet laid out.  ExtraSelections set on
        a hidden widget are not reliably rendered in all Qt builds, so we force
        a fresh render the moment the tab becomes visible.
        """
        super().showEvent(event)
        if self._file1 and self._file2:
            # Defer by one event-loop tick so the splitter has been laid out.
            QTimer.singleShot(0, self._refresh)

    def _refresh(self) -> None:
        if not self._file1 or not self._file2:
            msg = "(No pair loaded — run a scan and select a pair from Results.)"
            self._pane1.setPlainText(msg)
            self._pane2.setPlainText(msg)
            return

        path1, path2, label1, label2, _mode_label = self._current_paths_and_labels()

        self._sim_label.setText(
            f"Similarity: {self._similarity * 100:.1f}%"
        )

        self._fname1_label.setText(f"◀  {label1}")
        self._fname2_label.setText(f"▶  {label2}")

        try:
            text1 = _read(path1)
            text2 = _read(path2)
        except Exception as exc:
            err = f"Could not read file:\n{exc}"
            self._pane1.setPlainText(err)
            self._pane2.setPlainText(err)
            return

        try:
            if self._show_normalized:
                # Character-level diff — normalized text is one long line, so
                # line-level comparison would tag everything as unique.
                opcodes = SequenceMatcher(None, text1, text2, autojunk=False).get_opcodes()
                _char_extra_selections(self._pane1, text1, opcodes, is_a=True)
                _char_extra_selections(self._pane2, text2, opcodes, is_a=False)
            else:
                # Line-level diff for original source files, matching derived
                # from normalized content so it is consistent with the score.
                normalizer = get_normalizer(os.path.basename(self._file1.path))
                lines1, lines2, tags1, tags2 = _compute_line_tags_normalized(
                    text1, text2, normalizer
                )
                _line_extra_selections(self._pane1, lines1, tags1)
                _line_extra_selections(self._pane2, lines2, tags2)
        except Exception as exc:
            import traceback
            err = f"Diff rendering error:\n{traceback.format_exc()}"
            self._pane1.setPlainText(err)
            self._pane2.setPlainText(err)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot(int)
    def _on_combo_changed(self, index: int) -> None:
        self._load_from_comparisons(index)

    @pyqtSlot(bool)
    def _on_toggle(self, checked: bool) -> None:
        self._show_normalized = checked
        self._toggle_btn.setText("Show Original" if checked else "Show Normalized")
        self._refresh()

    @pyqtSlot(bool)
    def _on_scroll_sync_toggled(self, checked: bool) -> None:
        self._sync_scrolling = checked
        self._pane1.set_sync_enabled(checked)
        self._pane2.set_sync_enabled(checked)
        self._sync_scroll_btn.setText(
            "Sync Scrolling: On" if checked else "Sync Scrolling: Off"
        )

    @pyqtSlot()
    def _on_export_html(self) -> None:
        if not self._file1 or not self._file2:
            QMessageBox.information(
                self,
                "Export HTML",
                "No pair is loaded. Run a scan and select a pair first.",
            )
            return

        default_name = _safe_export_filename(self._file1, self._file2)
        save_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Diff HTML",
            default_name,
            "HTML Files (*.html);;All Files (*)",
        )
        if not save_path:
            return
        if not os.path.splitext(save_path)[1]:
            save_path += ".html"

        try:
            path1, path2, label1, label2, mode_label = self._current_paths_and_labels()
            text1 = _read(path1)
            text2 = _read(path2)

            if self._show_normalized:
                opcodes = list(
                    SequenceMatcher(None, text1, text2, autojunk=False).get_opcodes()
                )
                body1 = _html_char_spans(text1, opcodes, is_a=True)
                body2 = _html_char_spans(text2, opcodes, is_a=False)
            else:
                normalizer = get_normalizer(os.path.basename(self._file1.path))
                lines1, lines2, tags1, tags2 = _compute_line_tags_normalized(
                    text1, text2, normalizer
                )
                body1 = _html_line_blocks(lines1, tags1)
                body2 = _html_line_blocks(lines2, tags2)

            html = _build_diff_html(
                "CodeBuster Diff Export",
                label1,
                label2,
                body1,
                body2,
                self._similarity,
                mode_label,
                wrap_long_lines=self._show_normalized,
            )
            with open(save_path, "w", encoding="utf-8") as fh:
                fh.write(html)

            if QDesktopServices.openUrl(QUrl.fromLocalFile(save_path)):
                QMessageBox.information(
                    self,
                    "Export HTML",
                    f"Exported and opened:\n{save_path}",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export HTML",
                    f"Exported, but could not open automatically:\n{save_path}",
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export HTML",
                f"Could not export diff HTML:\n{exc}",
            )
