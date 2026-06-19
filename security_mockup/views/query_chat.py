"""自然言語クエリ画面（チャットUI + 推論過程展開）。"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from security_mockup.common import MOCK_VIDEOS, Colors, load_query_history
from security_mockup.widgets.chat_bubble import ChatBubble

PRESET_QUERIES = [
    "人物の出入り回数は？",
    "不審な行動はあったか？",
    "車両の出入り状況を教えて",
]


class ReasoningPanel(QFrame):
    """推論過程の展開表示（インテント・サブ質問・ツール・継続判断）。"""

    def __init__(self, reasoning: dict, tools: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet(
            f"#Card {{ background-color: {Colors.BG_SIDEBAR}; border: 1px solid {Colors.ACCENT}; border-radius: 10px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # ツールバッジ
        badge_row = QHBoxLayout()
        badge_row.addWidget(self._mk_label("使用ツール:", bold=True))
        for t in tools:
            b = QLabel(t)
            b.setStyleSheet(
                f"background-color: {Colors.INFO}; color: #fff; border-radius: 8px; padding: 2px 10px; font-size: 11px;"
            )
            badge_row.addWidget(b)
        badge_row.addStretch()
        lay.addLayout(badge_row)

        # インテント
        lay.addWidget(self._mk_label("インテント推定", bold=True, color=Colors.ACCENT))
        lay.addWidget(self._mk_label(reasoning.get("question_intent", ""), wrap=True, color=Colors.TEXT_SUB))

        # サブ質問とQA（ステッパー風）
        lay.addWidget(self._mk_label("サブ質問と回答", bold=True, color=Colors.ACCENT))
        qa = reasoning.get("qa_results", [])
        for i, item in enumerate(qa, 1):
            step = QFrame()
            step.setStyleSheet(
                f"background-color: {Colors.BG_CARD}; border-radius: 8px; border: 1px solid {Colors.BORDER};"
            )
            sl = QVBoxLayout(step)
            sl.setContentsMargins(10, 8, 10, 8)
            sl.addWidget(self._mk_label(f"STEP {i}  Q: {item['Q']}", bold=True))
            sl.addWidget(self._mk_label("A: " + item["A"], wrap=True, color=Colors.TEXT_SUB))
            lay.addWidget(step)

        # 継続/停止判断
        reasons = reasoning.get("continue_reasons", [])
        if reasons:
            lay.addWidget(self._mk_label("継続 / 停止の判断", bold=True, color=Colors.ACCENT))
            for i, r in enumerate(reasons, 1):
                lay.addWidget(self._mk_label(f"イテレーション{i}: {r}", wrap=True, color=Colors.TEXT_SUB))

    def _mk_label(self, text: str, bold=False, wrap=False, color=None) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(wrap)
        style = ""
        if bold:
            style += "font-weight: bold;"
        if color:
            style += f"color: {color};"
        lbl.setStyleSheet(style)
        return lbl


class QueryChatView(QWidget):
    frameRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = load_query_history()
        self._by_question = {q["question"]: q for q in self.history}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel("自然言語クエリ")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        # 映像選択
        sel = QHBoxLayout()
        sel.addWidget(QLabel("対象映像:"))
        self.video_box = QComboBox()
        self.video_box.addItems(MOCK_VIDEOS)
        sel.addWidget(self.video_box)
        sel.addStretch()
        root.addLayout(sel)

        # チャットエリア
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.chat_host = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_host)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.chat_host)
        root.addWidget(self.scroll, 1)

        # プリセット
        preset = QHBoxLayout()
        preset.addWidget(QLabel("クイック:"))
        for q in PRESET_QUERIES:
            b = QPushButton(q)
            b.clicked.connect(lambda _=False, text=q: self._submit(text))
            preset.addWidget(b)
        preset.addStretch()
        root.addLayout(preset)

        # 入力
        inp = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("映像について質問を入力... (Enterで送信)")
        self.input.returnPressed.connect(self._on_enter)
        send = QPushButton("送信")
        send.setObjectName("PrimaryButton")
        send.clicked.connect(self._on_enter)
        inp.addWidget(self.input)
        inp.addWidget(send)
        root.addLayout(inp)

        self._add_ai_message(
            "こんにちは。映像に関する質問を入力してください。下のクイックボタンも利用できます。",
            None,
            None,
        )

    # ----- メッセージ追加 -----
    def _add_user_message(self, text: str):
        bubble = ChatBubble(text, is_user=True)
        self.chat_layout.addWidget(bubble)
        self._scroll_bottom()

    def _add_ai_message(self, text: str, reasoning: dict | None, tools: list[str] | None):
        bubble = ChatBubble(text, is_user=False, has_reasoning=reasoning is not None)
        bubble.frameLinkClicked.connect(self.frameRequested.emit)
        if reasoning is not None:
            panel = ReasoningPanel(reasoning, tools or [])
            panel.setVisible(False)
            bubble.reasoningRequested.connect(lambda p=panel: p.setVisible(not p.isVisible()))
            self.chat_layout.addWidget(bubble)
            self.chat_layout.addWidget(panel)
        else:
            self.chat_layout.addWidget(bubble)
        self._scroll_bottom()

    def _add_loading(self) -> QLabel:
        lbl = QLabel("AI が推論中" + " ●●●")
        lbl.setStyleSheet(f"color: {Colors.TEXT_SUB}; padding: 8px;")
        self.chat_layout.addWidget(lbl)
        self._scroll_bottom()
        return lbl

    def _scroll_bottom(self):
        QTimer.singleShot(
            50, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
        )

    # ----- 送信処理 -----
    def _on_enter(self):
        text = self.input.text().strip()
        if text:
            self._submit(text)

    def _submit(self, text: str):
        self.input.clear()
        self._add_user_message(text)
        loading = self._add_loading()
        QTimer.singleShot(2000, lambda: self._respond(text, loading))

    def _respond(self, question: str, loading: QLabel):
        loading.setParent(None)
        loading.deleteLater()

        match = self._match_query(question)
        if match:
            self._add_ai_message(match["answer"], match["reasoning"], match.get("tools"))
        else:
            self._add_ai_message(
                "ご質問に対応する分析結果が見つかりませんでした。モックでは "
                "query_history.json に登録された質問に詳細な回答を返します。"
                "プリセットボタンや「バッグを持っていた人物はどこに向かったか？」をお試しください。",
                None,
                None,
            )

    def _match_query(self, question: str) -> dict | None:
        if question in self._by_question:
            return self._by_question[question]
        # 部分一致 / キーワード一致
        keymap = {
            "人物の出入り": "Q-001",
            "出入り": "Q-001",
            "何人": "Q-001",
            "バッグ": "Q-002",
            "不審": "Q-002",
            "車両": "Q-003",
            "車": "Q-003",
        }
        for kw, qid in keymap.items():
            if kw in question:
                for q in self.history:
                    if q["id"] == qid:
                        return q
        return None
