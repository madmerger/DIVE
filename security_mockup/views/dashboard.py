"""ダッシュボード画面。"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from security_mockup.common import (
    Colors,
    SEVERITY_COLOR,
    SEVERITY_LABEL,
    load_alerts,
    load_query_history,
)


def _kpi_card(title: str, value: str, bg: str, fg: str = "#ffffff") -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    card.setStyleSheet(f"#Card {{ background-color: {bg}; border-radius: 12px; }}")
    card.setMinimumHeight(110)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 14, 18, 14)
    t = QLabel(title)
    t.setStyleSheet(f"color: {fg}; font-size: 12px;")
    v = QLabel(value)
    v.setObjectName("KpiValue")
    v.setStyleSheet(f"color: {fg}; font-size: 32px; font-weight: bold;")
    lay.addWidget(t)
    lay.addWidget(v)
    lay.addStretch()
    return card


class DashboardView(QWidget):
    alertActivated = pyqtSignal(str, int)  # video_name, frame_idx
    queryActivated = pyqtSignal(str)  # query id
    cameraRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.alerts = load_alerts()
        self.queries = load_query_history()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(18)

        title = QLabel("ダッシュボード")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        # ---- KPI カード ----
        unack = sum(1 for a in self.alerts if not a.get("acknowledged"))
        kpi = QHBoxLayout()
        kpi.setSpacing(16)
        kpi.addWidget(_kpi_card("本日のアラート数", str(len(self.alerts)), Colors.DANGER))
        kpi.addWidget(_kpi_card("未確認アラート", str(unack), Colors.WARNING, "#1a1a2e"))
        kpi.addWidget(_kpi_card("処理済み映像", "12", Colors.INFO))
        kpi.addWidget(_kpi_card("最終更新", "2025-06-19 09:30", "#3a3a52"))
        root.addLayout(kpi)

        # ---- 中央: アラート一覧 + クエリ履歴 ----
        mid = QHBoxLayout()
        mid.setSpacing(16)
        mid.addWidget(self._build_alert_table(), 2)
        mid.addWidget(self._build_query_panel(), 1)
        root.addLayout(mid, 1)

        # ---- 下部: カメラ一覧 ----
        root.addWidget(self._build_camera_grid())

    # ----- アラート一覧テーブル -----
    def _build_alert_table(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("Card")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(14, 12, 14, 14)
        head = QLabel("アラート一覧")
        head.setObjectName("SectionTitle")
        lay.addWidget(head)

        self.table = QTableWidget(len(self.alerts), 5)
        self.table.setHorizontalHeaderLabels(["重要度", "ルール名", "映像名", "時刻", "状態"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self._populate_alerts()
        self.table.cellDoubleClicked.connect(self._on_alert_double)
        lay.addWidget(self.table)

        hint = QLabel("行をダブルクリックで該当フレームの映像へジャンプ")
        hint.setStyleSheet(f"color: {Colors.TEXT_SUB}; font-size: 11px;")
        lay.addWidget(hint)
        return wrap

    def _populate_alerts(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.alerts))
        for r, a in enumerate(self.alerts):
            sev = a["severity"]
            sev_item = QTableWidgetItem(f"● {SEVERITY_LABEL.get(sev, sev)}")
            sev_item.setForeground(QColor(SEVERITY_COLOR.get(sev, Colors.TEXT_MAIN)))
            sev_item.setData(Qt.ItemDataRole.UserRole, a)
            self.table.setItem(r, 0, sev_item)
            self.table.setItem(r, 1, QTableWidgetItem(a["rule_name"]))
            self.table.setItem(r, 2, QTableWidgetItem(a["video_name"]))
            self.table.setItem(r, 3, QTableWidgetItem(a["timestamp"]))

            state_widget = QWidget()
            sl = QHBoxLayout(state_widget)
            sl.setContentsMargins(4, 2, 4, 2)
            btn = QPushButton("確認済み" if a.get("acknowledged") else "未確認")
            btn.setProperty("ack", a.get("acknowledged", False))
            if a.get("acknowledged"):
                btn.setStyleSheet(f"color: {Colors.SUCCESS};")
            else:
                btn.setObjectName("PrimaryButton")
            btn.clicked.connect(lambda _=False, row=r: self._toggle_ack(row))
            sl.addWidget(btn)
            self.table.setCellWidget(r, 4, state_widget)
        self.table.setSortingEnabled(True)

    def _toggle_ack(self, row: int):
        self.alerts[row]["acknowledged"] = not self.alerts[row].get("acknowledged")
        self._populate_alerts()

    def _on_alert_double(self, row: int, _col: int):
        item = self.table.item(row, 0)
        a = item.data(Qt.ItemDataRole.UserRole)
        if a:
            self.alertActivated.emit(a["video_name"], a["frame_idx"])

    # ----- 直近クエリ履歴 -----
    def _build_query_panel(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("Card")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(14, 12, 14, 14)
        head = QLabel("直近のクエリ履歴")
        head.setObjectName("SectionTitle")
        lay.addWidget(head)

        for q in self.queries[:3]:
            card = QFrame()
            card.setStyleSheet(
                f"background-color: {Colors.BG_SIDEBAR}; border-radius: 8px; border: 1px solid {Colors.BORDER};"
            )
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            ql = QLabel("Q: " + q["question"])
            ql.setWordWrap(True)
            ql.setStyleSheet("font-weight: bold;")
            ans = q["answer"]
            preview = ans[:60] + ("…" if len(ans) > 60 else "")
            al = QLabel("A: " + preview)
            al.setWordWrap(True)
            al.setStyleSheet(f"color: {Colors.TEXT_SUB};")
            cl.addWidget(ql)
            cl.addWidget(al)
            card.mousePressEvent = lambda _e, qid=q["id"]: self.queryActivated.emit(qid)
            lay.addWidget(card)

        lay.addStretch()
        return wrap

    # ----- カメラ一覧グリッド -----
    def _build_camera_grid(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("Card")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(14, 12, 14, 14)
        head = QLabel("カメラ一覧")
        head.setObjectName("SectionTitle")
        lay.addWidget(head)

        grid = QGridLayout()
        grid.setSpacing(14)
        cams = [
            ("裏口カメラ", "録画中", Colors.SUCCESS),
            ("正面カメラ", "録画中", Colors.SUCCESS),
            ("駐車場カメラ", "処理中", Colors.WARNING),
            ("搬入口カメラ", "オフライン", Colors.TEXT_SUB),
        ]
        for i, (name, status, color) in enumerate(cams):
            cam = QFrame()
            cam.setStyleSheet(
                f"background-color: {Colors.BG_SIDEBAR}; border-radius: 8px; border: 1px solid {Colors.BORDER};"
            )
            cam.setCursor(Qt.CursorShape.PointingHandCursor)
            cl = QVBoxLayout(cam)
            cl.setContentsMargins(10, 10, 10, 10)
            thumb = QLabel("📷 NO SIGNAL" if status == "オフライン" else "📹 LIVE")
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setMinimumHeight(90)
            thumb.setStyleSheet(
                f"background-color: #0a0a18; border-radius: 6px; color: {color}; font-size: 14px;"
            )
            nm = QLabel(name)
            nm.setStyleSheet("font-weight: bold;")
            badge = QLabel(f"● {status}")
            badge.setStyleSheet(f"color: {color}; font-size: 11px;")
            cl.addWidget(thumb)
            cl.addWidget(nm)
            cl.addWidget(badge)
            cam.mousePressEvent = lambda _e: self.cameraRequested.emit()
            grid.addWidget(cam, 0, i)

        host = QWidget()
        host.setLayout(grid)
        lay.addWidget(host)
        return wrap
