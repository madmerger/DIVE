"""映像再生画面（検出オーバーレイ + タイムライン）。"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from security_mockup.common import (
    Colors,
    label_color,
    load_alerts,
    load_detections_csv,
    load_video_summary,
)
from security_mockup.widgets.detection_overlay import draw_detections
from security_mockup.widgets.timeline_widget import TimelineWidget

try:
    import cv2

    HAS_CV2 = True
except Exception:  # pragma: no cover - 環境依存
    HAS_CV2 = False

VIDEO_W, VIDEO_H = 640, 480


class VideoCanvas(QLabel):
    """グレーのモックフレーム or 実映像フレームに検出ボックスを重ねて描画する。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(VIDEO_W, VIDEO_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_idx = 0
        self.detections: list[dict] = []
        self.base_pixmap: QPixmap | None = None  # 実映像フレーム

    def set_frame(self, frame_idx: int, detections: list[dict], pixmap: QPixmap | None):
        self.frame_idx = frame_idx
        self.detections = detections
        self.base_pixmap = pixmap
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        w, h = self.width(), self.height()

        # 表示領域内で 4:3 を維持
        disp_w = w
        disp_h = int(w * VIDEO_H / VIDEO_W)
        if disp_h > h:
            disp_h = h
            disp_w = int(h * VIDEO_W / VIDEO_H)
        off_x = (w - disp_w) // 2
        off_y = (h - disp_h) // 2

        if self.base_pixmap is not None:
            scaled = self.base_pixmap.scaled(
                disp_w,
                disp_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(off_x, off_y, scaled)
        else:
            painter.fillRect(off_x, off_y, disp_w, disp_h, QColor("#2b2b3d"))
            painter.setPen(QColor(Colors.TEXT_SUB))
            painter.setFont(QFont("Consolas", 22, QFont.Weight.Bold))
            painter.drawText(
                off_x,
                off_y,
                disp_w,
                disp_h,
                Qt.AlignmentFlag.AlignCenter,
                f"MOCK FRAME\n#{self.frame_idx}",
            )

        sx = disp_w / VIDEO_W
        sy = disp_h / VIDEO_H
        draw_detections(painter, self.detections, sx, sy, off_x, off_y)

    # ---- ドラッグ&ドロップ ----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        player = self._find_player()
        if player is None:
            return
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                player.load_video_file(path)
                break

    def _find_player(self) -> "VideoPlayerView | None":
        w = self.parent()
        while w is not None:
            if isinstance(w, VideoPlayerView):
                return w
            w = w.parent()
        return None


class VideoPlayerView(QWidget):
    frameChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames = load_detections_csv()
        self.alerts = load_alerts()
        self.alert_frames = {a["frame_idx"] for a in self.alerts}
        self.frame_keys = sorted(self.frames.keys())
        self.current_frame = self.frame_keys[0] if self.frame_keys else 0
        self.summary_text = load_video_summary()

        self.cap = None
        self.video_total = 0
        self.csv_for_video: dict[int, list[dict]] | None = None

        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance)
        self.speed = 1.0

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)
        root.addWidget(self._build_left(), 7)
        root.addWidget(self._build_right(), 3)

        self._refresh()

    # ----- 左側: 映像 + コントロール + タイムライン -----
    def _build_left(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.canvas = VideoCanvas()
        canvas_frame = QFrame()
        canvas_frame.setObjectName("Card")
        cf = QVBoxLayout(canvas_frame)
        cf.setContentsMargins(8, 8, 8, 8)
        cf.addWidget(self.canvas)
        hint = QLabel("ヒント: .mp4 ファイルをここにドラッグ&ドロップで実映像を再生")
        hint.setStyleSheet(f"color: {Colors.TEXT_SUB}; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cf.addWidget(hint)
        lay.addWidget(canvas_frame, 1)

        # 再生コントロール
        ctrl = QHBoxLayout()
        self.btn_prev = QPushButton("⏮ 前")
        self.btn_play = QPushButton("▶ 再生")
        self.btn_play.setObjectName("PrimaryButton")
        self.btn_next = QPushButton("次 ⏭")
        self.speed_box = QComboBox()
        self.speed_box.addItems(["0.5x", "1x", "2x"])
        self.speed_box.setCurrentText("1x")
        self.frame_label = QLabel()
        self.frame_label.setStyleSheet(f"color: {Colors.TEXT_SUB};")

        self.btn_prev.clicked.connect(self.prev_frame)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.next_frame)
        self.speed_box.currentTextChanged.connect(self._on_speed)

        ctrl.addWidget(self.btn_prev)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_next)
        ctrl.addWidget(QLabel("速度:"))
        ctrl.addWidget(self.speed_box)
        ctrl.addStretch()
        ctrl.addWidget(self.frame_label)
        lay.addLayout(ctrl)

        # タイムライン
        tl_frame = QFrame()
        tl_frame.setObjectName("Card")
        tlf = QVBoxLayout(tl_frame)
        tlf.setContentsMargins(10, 8, 10, 8)
        tlt = QLabel("タイムライン")
        tlt.setObjectName("SectionTitle")
        tlf.addWidget(tlt)
        self.timeline = TimelineWidget()
        self.timeline.set_data(self.frames, self.alert_frames)
        self.timeline.frameSeeked.connect(self.seek_to_frame)
        tlf.addWidget(self.timeline)
        lay.addWidget(tl_frame)
        return wrap

    # ----- 右側: 検出結果パネル -----
    def _build_right(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("Card")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(14, 12, 14, 14)

        title = QLabel("検出結果")
        title.setObjectName("SectionTitle")
        lay.addWidget(title)

        self.summary_count = QLabel()
        self.summary_count.setStyleSheet(f"color: {Colors.TEXT_SUB};")
        lay.addWidget(self.summary_count)

        self.det_list = QTextEdit()
        self.det_list.setReadOnly(True)
        self.det_list.setMaximumHeight(260)
        lay.addWidget(self.det_list)

        # 折りたたみ可能な映像サマリー
        self.summary_btn = QPushButton("▼ 映像サマリー")
        self.summary_btn.setCheckable(True)
        self.summary_btn.setChecked(True)
        self.summary_btn.clicked.connect(self._toggle_summary)
        lay.addWidget(self.summary_btn)

        self.summary_view = QTextEdit()
        self.summary_view.setReadOnly(True)
        self.summary_view.setPlainText(self.summary_text)
        lay.addWidget(self.summary_view, 1)
        return wrap

    def _toggle_summary(self):
        self.summary_view.setVisible(self.summary_btn.isChecked())
        self.summary_btn.setText(
            "▼ 映像サマリー" if self.summary_btn.isChecked() else "▶ 映像サマリー"
        )

    # ----- 再生制御 -----
    def _on_speed(self, text: str):
        self.speed = float(text.replace("x", ""))
        if self.play_timer.isActive():
            self.play_timer.start(int(150 / self.speed))

    def toggle_play(self):
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.btn_play.setText("▶ 再生")
        else:
            self.play_timer.start(int(150 / self.speed))
            self.btn_play.setText("⏸ 一時停止")

    def _advance(self):
        if self.cap is not None:
            nxt = self.current_frame + 1
            if nxt >= self.video_total:
                nxt = 0
            self.seek_to_frame(nxt)
        else:
            self.next_frame()

    def next_frame(self):
        if self.cap is not None:
            self.seek_to_frame(min(self.current_frame + 1, self.video_total - 1))
            return
        keys = self.frame_keys
        idx = keys.index(self.current_frame) if self.current_frame in keys else 0
        self.seek_to_frame(keys[min(idx + 1, len(keys) - 1)])

    def prev_frame(self):
        if self.cap is not None:
            self.seek_to_frame(max(self.current_frame - 1, 0))
            return
        keys = self.frame_keys
        idx = keys.index(self.current_frame) if self.current_frame in keys else 0
        self.seek_to_frame(keys[max(idx - 1, 0)])

    def seek_to_frame(self, frame_idx: int):
        self.current_frame = frame_idx
        self.timeline.set_current_frame(frame_idx)
        self._refresh()
        self.frameChanged.emit(frame_idx)

    def _detections_for(self, frame_idx: int) -> list[dict]:
        source = self.csv_for_video if self.csv_for_video is not None else self.frames
        if frame_idx in source:
            return source[frame_idx]
        # 実映像では最も近い既知フレームの検出を流用
        if source:
            nearest = min(source.keys(), key=lambda k: abs(k - frame_idx))
            if abs(nearest - frame_idx) <= 7:
                return source[nearest]
        return []

    def _frame_pixmap(self, frame_idx: int) -> QPixmap | None:
        if self.cap is None or not HAS_CV2:
            return None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = self.cap.read()
        if not ok:
            return None
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        img = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(img.copy())

    def _refresh(self):
        dets = self._detections_for(self.current_frame)
        pix = self._frame_pixmap(self.current_frame)
        self.canvas.set_frame(self.current_frame, dets, pix)

        total = self.video_total if self.cap is not None else (
            self.frame_keys[-1] if self.frame_keys else 0
        )
        self.frame_label.setText(f"フレーム {self.current_frame} / {total}")

        counts: dict[str, int] = {}
        for d in dets:
            counts[d["label"]] = counts.get(d["label"], 0) + 1
        self.summary_count.setText(
            "検出オブジェクト数: " + (", ".join(f"{k}×{v}" for k, v in counts.items()) or "なし")
        )

        rows = []
        for d in dets:
            color = label_color(d["label"])
            box = d["box"]
            rows.append(
                f'<div style="margin-bottom:6px;">'
                f'<span style="color:{color};font-weight:bold;">● {d["label"]}</span> '
                f'<span style="color:{Colors.TEXT_SUB};">score={d["score"]:.2f}</span><br>'
                f'<span style="color:{Colors.TEXT_SUB};font-size:11px;">box=[{box[0]}, {box[1]}, {box[2]}, {box[3]}]</span>'
                f"</div>"
            )
        self.det_list.setHtml(
            "".join(rows) or f'<span style="color:{Colors.TEXT_SUB};">このフレームに検出はありません</span>'
        )

    # ----- 実映像ロード -----
    def load_video_file(self, path: str):
        if not HAS_CV2:
            return
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return
        if self.cap is not None:
            self.cap.release()
        self.cap = cap
        self.video_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        # 同ディレクトリに detection_results.csv があれば読み込む
        csv_path = os.path.join(os.path.dirname(path), "detection_results.csv")
        if os.path.exists(csv_path):
            self.csv_for_video = load_detections_csv(csv_path)
        else:
            self.csv_for_video = {}

        alert_frames = set(self.alert_frames) if self.csv_for_video else set()
        self.timeline.set_data(self.csv_for_video or {}, alert_frames)
        self.timeline._max_frame = max(self.timeline._max_frame, self.video_total)
        self.seek_to_frame(0)
