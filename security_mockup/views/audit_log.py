"""推論根拠・監査ログ画面。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from security_mockup.common import MOCK_VIDEOS, Colors, load_query_history


def _trunc(text: str, n: int = 40) -> str:
    return text[:n] + ("…" if len(text) > n else "")


class AuditLogView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = load_query_history()
        self.filtered = list(self.history)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel("推論根拠・監査ログ")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        # フィルタバー
        filt = QHBoxLayout()
        filt.addWidget(QLabel("映像:"))
        self.video_filter = QComboBox()
        self.video_filter.addItem("すべて")
        self.video_filter.addItems(MOCK_VIDEOS)
        self.video_filter.currentTextChanged.connect(self._apply_filter)
        filt.addWidget(self.video_filter)

        filt.addWidget(QLabel("キーワード:"))
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("質問テキストで検索")
        self.keyword.textChanged.connect(self._apply_filter)
        filt.addWidget(self.keyword, 1)
        root.addLayout(filt)

        # テーブル
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "日時", "質問", "回答", "ステータス"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.cellClicked.connect(self._on_row)
        root.addWidget(self.table, 1)

        # 詳細パネル
        self.detail = self._build_detail()
        root.addWidget(self.detail, 1)

        self._populate()

    def select_query(self, qid: str):
        for i, q in enumerate(self.filtered):
            if q["id"] == qid:
                self.table.selectRow(i)
                self._show_detail(q)
                break

    def _build_detail(self) -> QTabWidget:
        tabs = QTabWidget()

        # 質問と回答
        self.tab_qa = QScrollArea()
        self.tab_qa.setWidgetResizable(True)
        self.qa_host = QWidget()
        self.qa_layout = QVBoxLayout(self.qa_host)
        self.qa_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tab_qa.setWidget(self.qa_host)
        tabs.addTab(self.tab_qa, "質問と回答")

        # 推論過程
        self.tab_reason = QScrollArea()
        self.tab_reason.setWidgetResizable(True)
        self.reason_host = QWidget()
        self.reason_layout = QVBoxLayout(self.reason_host)
        self.reason_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tab_reason.setWidget(self.reason_host)
        tabs.addTab(self.tab_reason, "推論過程")

        # エビデンス
        self.tab_evidence = QScrollArea()
        self.tab_evidence.setWidgetResizable(True)
        self.evidence_host = QWidget()
        self.evidence_layout = QVBoxLayout(self.evidence_host)
        self.evidence_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tab_evidence.setWidget(self.evidence_host)
        tabs.addTab(self.tab_evidence, "エビデンス")

        return tabs

    # ----- フィルタ -----
    def _apply_filter(self):
        video = self.video_filter.currentText()
        kw = self.keyword.text().strip()
        self.filtered = [
            q
            for q in self.history
            if (video == "すべて" or q.get("video_name") == video)
            and (not kw or kw in q["question"])
        ]
        self._populate()

    def _populate(self):
        self.table.setRowCount(len(self.filtered))
        for r, q in enumerate(self.filtered):
            self.table.setItem(r, 0, QTableWidgetItem(q["id"]))
            self.table.setItem(r, 1, QTableWidgetItem(q["timestamp"]))
            self.table.setItem(r, 2, QTableWidgetItem(_trunc(q["question"])))
            self.table.setItem(r, 3, QTableWidgetItem(_trunc(q["answer"])))
            status = QTableWidgetItem("完了")
            from PyQt6.QtGui import QColor

            status.setForeground(QColor(Colors.SUCCESS))
            self.table.setItem(r, 4, status)

    def _on_row(self, row: int, _col: int):
        if 0 <= row < len(self.filtered):
            self._show_detail(self.filtered[row])

    # ----- 詳細表示 -----
    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_detail(self, q: dict):
        self._clear(self.qa_layout)
        self._clear(self.reason_layout)
        self._clear(self.evidence_layout)
        reasoning = q.get("reasoning", {})

        # --- 質問と回答 ---
        self.qa_layout.addWidget(self._heading("質問"))
        self.qa_layout.addWidget(self._body(q["question"]))
        self.qa_layout.addWidget(self._heading("インテント推定"))
        self.qa_layout.addWidget(self._body(reasoning.get("question_intent", "-")))
        self.qa_layout.addWidget(self._heading("最終回答"))
        self.qa_layout.addWidget(self._body(q["answer"]))

        # --- 推論過程（ステッパー） ---
        qa = reasoning.get("qa_results", [])
        reasons = reasoning.get("continue_reasons", [])
        for i, item in enumerate(qa):
            step = QFrame()
            step.setObjectName("Card")
            step.setStyleSheet(
                f"#Card {{ background-color: {Colors.BG_SIDEBAR}; border-radius: 8px; border: 1px solid {Colors.BORDER}; }}"
            )
            sl = QVBoxLayout(step)
            sl.setContentsMargins(12, 10, 12, 10)
            badge = QLabel(f"✓ STEP {i + 1}")
            badge.setStyleSheet(f"color: {Colors.SUCCESS}; font-weight: bold;")
            sl.addWidget(badge)
            sl.addWidget(self._body("Q: " + item["Q"], bold=True))
            sl.addWidget(self._body("A: " + item["A"], color=Colors.TEXT_SUB))
            self.reason_layout.addWidget(step)

            if i < len(reasons):
                cont = QLabel(f"↓ 継続判断: {reasons[i]}")
                cont.setWordWrap(True)
                cont.setStyleSheet(f"color: {Colors.ACCENT}; padding: 4px 8px;")
                self.reason_layout.addWidget(cont)

        # --- エビデンス（フレームサムネイル プレースホルダー） ---
        frames = self._extract_frames(q)
        grid_host = QWidget()
        grid = QHBoxLayout(grid_host)
        grid.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for f in frames:
            thumb = QLabel(f"フレーム\n#{f}")
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setFixedSize(120, 90)
            thumb.setStyleSheet(
                f"background-color: #0a0a18; color: {Colors.TEXT_SUB}; border-radius: 6px; border: 1px solid {Colors.BORDER};"
            )
            grid.addWidget(thumb)
        if not frames:
            self.evidence_layout.addWidget(self._body("関連フレームの言及はありません。"))
        else:
            self.evidence_layout.addWidget(self._heading("関連フレーム"))
            self.evidence_layout.addWidget(grid_host)

    def _extract_frames(self, q: dict) -> list[int]:
        import re

        text = q["answer"] + " " + str(q.get("reasoning", {}))
        return sorted({int(m) for m in re.findall(r"フレーム\s*(\d+)", text)})

    def _heading(self, t: str) -> QLabel:
        lbl = QLabel(t)
        lbl.setStyleSheet(f"color: {Colors.ACCENT}; font-weight: bold; margin-top: 6px;")
        return lbl

    def _body(self, t: str, bold=False, color=None) -> QLabel:
        lbl = QLabel(t)
        lbl.setWordWrap(True)
        style = ""
        if bold:
            style += "font-weight: bold;"
        if color:
            style += f"color: {color};"
        lbl.setStyleSheet(style)
        return lbl
