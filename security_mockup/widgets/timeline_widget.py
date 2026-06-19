"""タイムラインウィジェット: 検出イベントの可視化とシークバー。"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from security_mockup.common import Colors, label_color


class TimelineWidget(QWidget):
    """横軸=フレーム番号。検出イベントをカラードット、アラートを赤三角で表示。

    ドラッグ / クリックでフレームを移動でき、frameSeeked シグナルを発行する。
    """

    frameSeeked = pyqtSignal(int)

    PADDING = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.setMouseTracking(True)
        self._frames: dict[int, list[dict]] = {}
        self._alert_frames: set[int] = set()
        self._max_frame = 180
        self._current = 0
        self._dragging = False

    # ----- データ設定 -----
    def set_data(self, frames: dict[int, list[dict]], alert_frames: set[int]):
        self._frames = frames
        self._alert_frames = set(alert_frames)
        self._max_frame = max([*frames.keys(), *alert_frames, 1])
        self.update()

    def set_current_frame(self, frame: int):
        self._current = max(0, min(frame, self._max_frame))
        self.update()

    # ----- 座標変換 -----
    def _frame_to_x(self, frame: int) -> float:
        w = self.width() - 2 * self.PADDING
        if self._max_frame == 0:
            return self.PADDING
        return self.PADDING + (frame / self._max_frame) * w

    def _x_to_frame(self, x: float) -> int:
        w = self.width() - 2 * self.PADDING
        if w <= 0:
            return 0
        ratio = (x - self.PADDING) / w
        return int(round(max(0.0, min(1.0, ratio)) * self._max_frame))

    # ----- マウス操作 -----
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._seek_to(event.position().x())

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._seek_to(event.position().x())

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def _seek_to(self, x: float):
        frame = self._x_to_frame(x)
        if frame != self._current:
            self._current = frame
        self.frameSeeked.emit(frame)
        self.update()

    # ----- 描画 -----
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Colors.BG_CARD))

        track_y = self.height() // 2
        x_start = self.PADDING
        x_end = self.width() - self.PADDING

        # トラック線
        painter.setPen(QPen(QColor(Colors.BORDER), 2))
        painter.drawLine(x_start, track_y, x_end, track_y)

        # 目盛り
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor(Colors.TEXT_SUB))
        ticks = 6
        for i in range(ticks + 1):
            frame = int(self._max_frame * i / ticks)
            x = int(self._frame_to_x(frame))
            painter.drawLine(x, track_y - 4, x, track_y + 4)
            painter.drawText(x - 12, track_y + 22, f"F{frame}")

        # 検出ドット
        for frame, dets in self._frames.items():
            x = int(self._frame_to_x(frame))
            for j, det in enumerate(dets):
                color = QColor(label_color(det["label"]))
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                cy = track_y - 14 - (j % 3) * 9
                painter.drawEllipse(QPointF(x, cy), 4, 4)

        # アラート三角マーカー（赤）
        for frame in self._alert_frames:
            x = self._frame_to_x(frame)
            top = track_y + 14
            tri = QPolygonF(
                [
                    QPointF(x, top),
                    QPointF(x - 6, top + 12),
                    QPointF(x + 6, top + 12),
                ]
            )
            painter.setBrush(QColor(Colors.DANGER))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(tri)

        # 現在フレームの縦線 + ハンドル
        cx = int(self._frame_to_x(self._current))
        painter.setPen(QPen(QColor(Colors.ACCENT), 2))
        painter.drawLine(cx, 6, cx, self.height() - 6)
        painter.setBrush(QColor(Colors.ACCENT))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, track_y), 6, 6)
