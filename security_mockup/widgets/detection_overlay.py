"""バウンディングボックス描画ヘルパー。"""
from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QPainter, QPen

from security_mockup.common import label_color


def draw_detections(
    painter: QPainter,
    detections: list[dict],
    scale_x: float,
    scale_y: float,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> None:
    """与えられた検出結果のバウンディングボックスとラベルを描画する。

    座標は元映像（640x480等）基準。scale/offset で表示領域に合わせて変換する。
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Segoe UI", 9)
    font.setBold(True)
    painter.setFont(font)

    for det in detections:
        x1, y1, x2, y2 = det["box"]
        color = QColor(label_color(det["label"]))

        rx1 = offset_x + x1 * scale_x
        ry1 = offset_y + y1 * scale_y
        rw = (x2 - x1) * scale_x
        rh = (y2 - y1) * scale_y

        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(int(rx1), int(ry1), int(rw), int(rh))

        # ラベル背景
        text = f"{det['label']} {det['score']:.2f}"
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(text) + 8
        th = metrics.height() + 2
        label_y = int(ry1) - th
        if label_y < 0:
            label_y = int(ry1)
        painter.fillRect(int(rx1), label_y, tw, th, color)
        painter.setPen(QColor("#1a1a2e"))
        painter.drawText(int(rx1) + 4, label_y + metrics.ascent(), text)
