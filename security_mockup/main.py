"""SecurityDIVE - 映像監視インテリジェンス（PyQt6 モックアップ）。

エントリーポイント。サイドバーナビゲーションと QStackedWidget による画面切替を提供する。
"""
from __future__ import annotations

import os
import sys

# パッケージとしてインポートできるよう、リポジトリルートを sys.path に追加
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from security_mockup.common import RESOURCES_DIR, Colors  # noqa: E402
from security_mockup.views.alert_rules import AlertRulesView  # noqa: E402
from security_mockup.views.audit_log import AuditLogView  # noqa: E402
from security_mockup.views.dashboard import DashboardView  # noqa: E402
from security_mockup.views.query_chat import QueryChatView  # noqa: E402
from security_mockup.views.video_player import VideoPlayerView  # noqa: E402

NAV_ITEMS = [
    ("📊", "ダッシュボード"),
    ("🎬", "映像再生"),
    ("💬", "クエリ"),
    ("🔔", "アラートルール"),
    ("📋", "監査ログ"),
]


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecurityDIVE - 映像監視インテリジェンス")
        self.resize(1920, 1080)
        self.setMinimumSize(1280, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.dashboard = DashboardView()
        self.video = VideoPlayerView()
        self.query = QueryChatView()
        self.rules = AlertRulesView()
        self.audit = AuditLogView()
        for v in (self.dashboard, self.video, self.query, self.rules, self.audit):
            self.stack.addWidget(v)
        body.addWidget(self.stack, 1)

        body_host = QWidget()
        body_host.setLayout(body)
        root.addWidget(body_host, 1)

        self._connect_signals()
        self._select(0)

    # ----- ヘッダー -----
    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("HeaderBar")
        header.setFixedHeight(56)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 0, 20, 0)
        title = QLabel("SecurityDIVE")
        title.setObjectName("HeaderTitle")
        sub = QLabel("映像監視インテリジェンス")
        sub.setStyleSheet(f"color: {Colors.TEXT_SUB};")
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch()
        status = QLabel("● ローカルモード")
        status.setObjectName("StatusBadge")
        lay.addWidget(status)
        return header

    # ----- サイドバー -----
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 16, 12, 16)
        lay.setSpacing(6)

        logo = QLabel("🛡 SecurityDIVE")
        logo.setObjectName("SidebarLogo")
        lay.addWidget(logo)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for i, (icon, text) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"  {icon}   {text}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, idx=i: self._select(idx))
            self.nav_group.addButton(btn, i)
            lay.addWidget(btn)

        lay.addStretch()
        ver = QLabel("v0.1.0 mockup")
        ver.setStyleSheet(f"color: {Colors.TEXT_SUB}; font-size: 10px;")
        lay.addWidget(ver)
        return side

    def _select(self, idx: int):
        self.stack.setCurrentIndex(idx)
        btn = self.nav_group.button(idx)
        if btn:
            btn.setChecked(True)

    # ----- 画面間シグナル接続 -----
    def _connect_signals(self):
        # ダッシュボード -> 映像再生 / 監査ログ
        self.dashboard.alertActivated.connect(self._goto_frame)
        self.dashboard.queryActivated.connect(self._goto_audit)
        self.dashboard.cameraRequested.connect(lambda: self._select(1))
        # クエリ回答 -> 映像再生
        self.query.frameRequested.connect(self._goto_frame_only)

    def _goto_frame(self, _video_name: str, frame_idx: int):
        self._select(1)
        self.video.seek_to_frame(frame_idx)

    def _goto_frame_only(self, frame_idx: int):
        self._select(1)
        self.video.seek_to_frame(frame_idx)

    def _goto_audit(self, qid: str):
        self._select(4)
        self.audit.select_query(qid)


def load_stylesheet() -> str:
    qss_path = os.path.join(RESOURCES_DIR, "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            return f.read()
    return ""


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
