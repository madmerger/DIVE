"""アラートルール設定画面。"""
from __future__ import annotations

from PyQt6.QtCore import QTime, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from security_mockup.common import Colors, load_rules, save_rules

CONDITION_LABELS = {
    "count_exceeds": "人数超過",
    "appears_in_zone": "ゾーン内出現",
    "absence_detected": "不在検知",
}
CONDITION_KEYS = list(CONDITION_LABELS.keys())


class TagEditor(QWidget):
    """対象オブジェクトをタグ形式で表示・追加・削除する。"""

    def __init__(self, classes: list[str], parent=None):
        super().__init__(parent)
        self.classes = list(classes)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        self._rebuild()

    def _rebuild(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for cls in self.classes:
            tag = QPushButton(f"{cls} ✕")
            tag.setStyleSheet(
                f"background-color: {Colors.INFO}; color: #fff; border-radius: 10px; padding: 2px 10px;"
            )
            tag.setCursor(Qt.CursorShape.PointingHandCursor)
            tag.clicked.connect(lambda _=False, c=cls: self._remove(c))
            self.layout.addWidget(tag)
        add = QPushButton("＋")
        add.setFixedWidth(32)
        add.clicked.connect(self._add)
        self.layout.addWidget(add)
        self.layout.addStretch()

    def _remove(self, cls: str):
        self.classes.remove(cls)
        self._rebuild()

    def _add(self):
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(self, "オブジェクト追加", "対象クラス名:")
        if ok and text.strip():
            self.classes.append(text.strip())
            self._rebuild()


class RuleCard(QFrame):
    def __init__(self, rule: dict, on_delete, parent=None):
        super().__init__(parent)
        self.rule = rule
        self.on_delete = on_delete
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # ヘッダー: 名前 + 有効トグル + 削除
        head = QHBoxLayout()
        self.name_edit = QLineEdit(rule["name"])
        self.name_edit.setStyleSheet("font-size: 15px; font-weight: bold;")
        head.addWidget(self.name_edit, 1)

        self.toggle = QPushButton("有効" if rule["enabled"] else "無効")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(rule["enabled"])
        self._style_toggle()
        self.toggle.clicked.connect(self._on_toggle)
        head.addWidget(self.toggle)

        del_btn = QPushButton("削除")
        del_btn.setObjectName("DangerButton")
        del_btn.clicked.connect(self._confirm_delete)
        head.addWidget(del_btn)
        lay.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # 対象オブジェクト
        grid.addWidget(self._lbl("対象オブジェクト:"), 0, 0)
        self.tags = TagEditor(rule.get("target_classes", []))
        grid.addWidget(self.tags, 0, 1, 1, 3)

        # 条件
        from PyQt6.QtWidgets import QComboBox

        grid.addWidget(self._lbl("条件:"), 1, 0)
        self.cond_box = QComboBox()
        self.cond_box.addItems([CONDITION_LABELS[k] for k in CONDITION_KEYS])
        cur = rule.get("condition", "count_exceeds")
        if cur in CONDITION_KEYS:
            self.cond_box.setCurrentIndex(CONDITION_KEYS.index(cur))
        grid.addWidget(self.cond_box, 1, 1)

        # 閾値
        grid.addWidget(self._lbl("閾値:"), 1, 2)
        self.threshold = QSpinBox()
        self.threshold.setRange(0, 100)
        self.threshold.setValue(rule.get("threshold", 0))
        grid.addWidget(self.threshold, 1, 3)

        # 時間帯
        grid.addWidget(self._lbl("時間帯:"), 2, 0)
        tw_widget = QWidget()
        tw = QHBoxLayout(tw_widget)
        tw.setContentsMargins(0, 0, 0, 0)
        self.always_chk = QPushButton("常時")
        self.always_chk.setCheckable(True)
        self.start_time = QTimeEdit()
        self.end_time = QTimeEdit()
        window = rule.get("time_window")
        if window:
            s, e = window.split("-")
            self.start_time.setTime(QTime.fromString(s, "HH:mm"))
            self.end_time.setTime(QTime.fromString(e, "HH:mm"))
        else:
            self.always_chk.setChecked(True)
            self._set_time_enabled(False)
        self.always_chk.clicked.connect(
            lambda: self._set_time_enabled(not self.always_chk.isChecked())
        )
        tw.addWidget(self.always_chk)
        tw.addWidget(self.start_time)
        tw.addWidget(QLabel("〜"))
        tw.addWidget(self.end_time)
        tw.addStretch()
        grid.addWidget(tw_widget, 2, 1, 1, 3)

        # 監視ゾーン
        grid.addWidget(self._lbl("監視ゾーン:"), 3, 0)
        zone_widget = QWidget()
        zl = QHBoxLayout(zone_widget)
        zl.setContentsMargins(0, 0, 0, 0)
        self.zone_name = QLineEdit(rule.get("zone_name", ""))
        self.zone_name.setPlaceholderText("ゾーン名")
        z = rule.get("zone", {})
        self.zx1 = self._coord(z.get("x1", 0))
        self.zy1 = self._coord(z.get("y1", 0))
        self.zx2 = self._coord(z.get("x2", 0))
        self.zy2 = self._coord(z.get("y2", 0))
        zl.addWidget(self.zone_name)
        for w in (QLabel("x1"), self.zx1, QLabel("y1"), self.zy1, QLabel("x2"), self.zx2, QLabel("y2"), self.zy2):
            zl.addWidget(w)
        grid.addWidget(zone_widget, 3, 1, 1, 3)

        # 重要度
        grid.addWidget(self._lbl("重要度:"), 4, 0)
        sev_widget = QWidget()
        sv = QHBoxLayout(sev_widget)
        sv.setContentsMargins(0, 0, 0, 0)
        self.sev_group = QButtonGroup(self)
        self.sev_buttons = {}
        for sev, text, color in [
            ("info", "info", Colors.INFO),
            ("warning", "warning", Colors.WARNING),
            ("critical", "critical", Colors.DANGER),
        ]:
            rb = QRadioButton(text)
            rb.setStyleSheet(f"color: {color};")
            if rule.get("severity") == sev:
                rb.setChecked(True)
            self.sev_group.addButton(rb)
            self.sev_buttons[sev] = rb
            sv.addWidget(rb)
        sv.addStretch()
        grid.addWidget(sev_widget, 4, 1, 1, 3)

        lay.addLayout(grid)

    def _lbl(self, t: str) -> QLabel:
        lbl = QLabel(t)
        lbl.setStyleSheet(f"color: {Colors.TEXT_SUB};")
        return lbl

    def _coord(self, val: int) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(0, 4000)
        sp.setValue(val)
        sp.setFixedWidth(70)
        return sp

    def _set_time_enabled(self, enabled: bool):
        self.start_time.setEnabled(enabled)
        self.end_time.setEnabled(enabled)

    def _style_toggle(self):
        if self.toggle.isChecked():
            self.toggle.setStyleSheet(
                f"background-color: {Colors.SUCCESS}; color: #1a1a2e; font-weight: bold;"
            )
        else:
            self.toggle.setStyleSheet(f"background-color: {Colors.BORDER}; color: {Colors.TEXT_SUB};")

    def _on_toggle(self):
        self.toggle.setText("有効" if self.toggle.isChecked() else "無効")
        self._style_toggle()

    def _confirm_delete(self):
        reply = QMessageBox.question(
            self,
            "ルール削除",
            f"ルール「{self.name_edit.text()}」を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.on_delete(self)

    def to_dict(self) -> dict:
        idx = self.cond_box.currentIndex()
        if self.always_chk.isChecked():
            window = None
        else:
            window = (
                self.start_time.time().toString("HH:mm")
                + "-"
                + self.end_time.time().toString("HH:mm")
            )
        return {
            "id": self.rule["id"],
            "name": self.name_edit.text(),
            "enabled": self.toggle.isChecked(),
            "target_classes": self.tags.classes,
            "condition": CONDITION_KEYS[idx],
            "threshold": self.threshold.value(),
            "time_window": window,
            "zone": {
                "x1": self.zx1.value(),
                "y1": self.zy1.value(),
                "x2": self.zx2.value(),
                "y2": self.zy2.value(),
            },
            "zone_name": self.zone_name.text(),
            "severity": next(
                (s for s, rb in self.sev_buttons.items() if rb.isChecked()), "info"
            ),
        }


class AlertRulesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = load_rules()
        self.cards: list[RuleCard] = []
        self._id_counter = len(self.rules)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("アラートルール設定")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        head.addWidget(title)
        head.addStretch()
        add_btn = QPushButton("＋ ルールを追加")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_rule)
        head.addWidget(add_btn)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        head.addWidget(save_btn)
        root.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.host = QWidget()
        self.card_layout = QVBoxLayout(self.host)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(14)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, 1)

        for r in self.rules:
            self._add_card(r)

    def _add_card(self, rule: dict):
        card = RuleCard(rule, on_delete=self._delete_card)
        self.cards.append(card)
        self.card_layout.addWidget(card)

    def _delete_card(self, card: RuleCard):
        self.cards.remove(card)
        card.setParent(None)
        card.deleteLater()

    def _add_rule(self):
        self._id_counter += 1
        new_id = f"RULE-{self._id_counter:03d}"
        rule = {
            "id": new_id,
            "name": "新しいルール",
            "enabled": True,
            "target_classes": ["person"],
            "condition": "count_exceeds",
            "threshold": 1,
            "time_window": "22:00-06:00",
            "zone": {"x1": 50, "y1": 50, "x2": 400, "y2": 500},
            "zone_name": "新規ゾーン",
            "severity": "warning",
        }
        self._add_card(rule)

    def _save(self):
        data = [c.to_dict() for c in self.cards]
        save_rules(data)
        QMessageBox.information(self, "保存完了", f"{len(data)} 件のルールを保存しました。")
