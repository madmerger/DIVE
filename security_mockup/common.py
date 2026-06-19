"""共通ユーティリティ: カラーパレット、モックデータの読み書き、ラベル色分け。"""
from __future__ import annotations

import csv
import json
import os
from typing import Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOCK_DATA_DIR = os.path.join(BASE_DIR, "mock_data")
RESOURCES_DIR = os.path.join(BASE_DIR, "resources")


# ===== ダークテーマ カラーパレット =====
class Colors:
    BG_MAIN = "#1a1a2e"
    BG_SIDEBAR = "#16213e"
    BG_CARD = "#0f3460"
    ACCENT = "#e94560"
    TEXT_MAIN = "#eaeaea"
    TEXT_SUB = "#a0a0b0"
    BORDER = "#2a2a4a"
    SUCCESS = "#00c853"
    WARNING = "#ffd600"
    DANGER = "#ff1744"
    INFO = "#2979ff"


# severity -> 表示色 / ラベル
SEVERITY_COLOR = {
    "info": Colors.INFO,
    "warning": Colors.WARNING,
    "critical": Colors.DANGER,
}
SEVERITY_LABEL = {
    "info": "情報",
    "warning": "警告",
    "critical": "危険",
}

# 検出ラベルごとのバウンディングボックス色
SUSPICIOUS_LABELS = {"bag", "backpack", "suitcase"}
VEHICLE_LABELS = {"car", "truck", "vehicle", "bus"}


def label_color(label: str) -> str:
    """検出ラベルに応じた色を返す。"""
    low = label.lower()
    if low == "person":
        return Colors.SUCCESS
    if low in VEHICLE_LABELS:
        return Colors.INFO
    if low in SUSPICIOUS_LABELS:
        return Colors.DANGER
    return Colors.WARNING


# ===== モックデータ読み込み =====
def _path(name: str) -> str:
    return os.path.join(MOCK_DATA_DIR, name)


def load_json(name: str) -> Any:
    with open(_path(name), encoding="utf-8") as f:
        return json.load(f)


def save_json(name: str, data: Any) -> None:
    with open(_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_text(name: str) -> str:
    with open(_path(name), encoding="utf-8") as f:
        return f.read()


def load_detections_csv(path: str | None = None) -> dict[int, list[dict]]:
    """CSV を frame_idx -> 検出リスト の辞書に変換する。"""
    path = path or _path("detection_results.csv")
    frames: dict[int, list[dict]] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = int(row["frame_idx"])
            frames.setdefault(idx, []).append(
                {
                    "label": row["label"],
                    "box": [
                        int(row["box_x1"]),
                        int(row["box_y1"]),
                        int(row["box_x2"]),
                        int(row["box_y2"]),
                    ],
                    "score": float(row["score"]),
                }
            )
    return frames


def load_alerts() -> list[dict]:
    return load_json("alerts.json")


def load_query_history() -> list[dict]:
    return load_json("query_history.json")


def load_rules() -> list[dict]:
    return load_json("rules.json")


def save_rules(rules: list[dict]) -> None:
    save_json("rules.json", rules)


def load_video_summary() -> str:
    return load_text("video_summary.txt")


# モック映像名リスト
MOCK_VIDEOS = [
    "裏口カメラ_20250618_2200.mp4",
    "正面カメラ_20250618_2200.mp4",
    "駐車場カメラ_20250618_2200.mp4",
    "搬入口カメラ_20250618_2200.mp4",
]
