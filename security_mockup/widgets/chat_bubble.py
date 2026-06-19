"""チャット吹き出しウィジェット。"""
from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from security_mockup.common import Colors

FRAME_REF_RE = re.compile(r"フレーム\s*(\d+)")


class ChatBubble(QWidget):
    """ユーザー / AI のチャット吹き出し。

    AI 吹き出しでは「推論過程を見る」ボタンとフレーム番号リンクを提供する。
    """

    frameLinkClicked = pyqtSignal(int)
    reasoningRequested = pyqtSignal()

    def __init__(self, text: str, is_user: bool, has_reasoning: bool = False, parent=None):
        super().__init__(parent)
        self.is_user = is_user

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)

        bubble = QFrame()
        bubble.setObjectName("Card")
        bubble.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        bubble.setMaximumWidth(560)
        bg = Colors.INFO if is_user else Colors.BG_CARD
        fg = "#ffffff" if is_user else Colors.TEXT_MAIN
        bubble.setStyleSheet(
            f"#Card {{ background-color: {bg}; border-radius: 12px; border: 1px solid {Colors.BORDER}; }}"
        )

        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(14, 10, 14, 10)

        if is_user:
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {fg};")
            inner.addWidget(label)
        else:
            # フレーム番号をクリック可能リンクに変換
            html = FRAME_REF_RE.sub(
                lambda m: f'<a href="frame:{m.group(1)}" style="color:{Colors.ACCENT};">{m.group(0)}</a>',
                text,
            )
            label = QLabel(html)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setOpenExternalLinks(False)
            label.setStyleSheet(f"color: {fg};")
            label.linkActivated.connect(self._on_link)
            inner.addWidget(label)

            if has_reasoning:
                btn = QPushButton("推論過程を見る")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(self.reasoningRequested.emit)
                inner.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)

        if is_user:
            outer.addStretch()
            outer.addWidget(bubble)
        else:
            outer.addWidget(bubble)
            outer.addStretch()

    def _on_link(self, href: str):
        if href.startswith("frame:"):
            self.frameLinkClicked.emit(int(href.split(":", 1)[1]))
