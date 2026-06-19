# 製造業向け生産ライン品質検査・異常検知システム MVP 開発プロンプト

> **本ドキュメントの位置づけ**: 本ドキュメントは、DIVE (Deep-search Iterative Video Exploration) の技術基盤をベースに、製造業の生産ライン品質検査・異常検知システムの MVP を開発するための包括的な開発指示書である。AI コーディングエージェントに本ドキュメントをそのまま渡すことで、開発を即座に開始できるレベルの具体性を備える。

---

## 1. プロジェクト概要

### 1.1 目的

生産ライン映像からの品質検査・異常検知を、自然言語クエリで実行できるシステムを構築する。作業員は「溶接ビードに外観異常はないか」「組立手順は正しいか」「安全装備は着用されているか」といった自然言語の質問を入力するだけで、映像 AI が自動的に検査・判定を行い、エビデンス付きの検査レポートを生成する。

### 1.2 DIVE 技術基盤の活用方針

| 技術要素 | そのまま活用 | 製造業向けカスタマイズ |
|---|---|---|
| LangGraph ステートマシン (`main.py` L37-61) | ワークフローのノード構成・遷移制御 | ノード追加（異常分類・重大度判定） |
| `AgentState` TypedDict (`main.py` L19-33) | 基本フィールド構造 | 製造業固有フィールドの拡張 |
| `infer_question_intent` (`nodes.py` L30-66) | 意図推定の基本ロジック | システムプロンプトを製造業コンテキストに変更 |
| `split_question` (`nodes.py` L69-111) | サブ質問分解メカニズム | 検査観点に基づく分解戦略に改修 |
| `answer_question` (`nodes.py` L114-213) | マルチモデルエージェント構造 | 製造業特化のシステムプロンプト・ツール使い分け |
| `should_continue` (`nodes.py` L289-370) | 反復継続判定ロジック | 検査完了基準の明確化 |
| `finalize_answer` (`nodes.py` L373-432) | 最終回答生成 | 構造化検査レポート形式に拡張 |
| Gemini 2.5 Pro ツール (`tools/analyze_video_gemini.py` L91-129) | GCS 映像取得・Vertex AI 連携 | 作業手順時系列検証に特化 |
| GPT-4.1 ビジョンツール (`tools/vision_tool_fixed_input.py` L75-142) | フレーム選択・詳細分析 | 製品外観の微細欠陥検出に特化 |
| Grounding DINO 物体検出 (`generate_video_summary.py` L43-104) | ゼロショット物体検出パイプライン | 部品・製品・工具・保護具の検出に特化 |
| 推論過程ログ (`main.py` L84-92) | `log_thinking` 構造 | 監査ログ・検査根拠記録として拡張 |

---

## 2. MVP 機能要件

### 2.1 必須機能（Phase 1 スコープ）

#### 2.1.1 映像入力 [優先度: 最高]

- **バッチアップロード**: 生産ラインカメラで撮影済みの映像ファイル（MP4, AVI）のアップロード
- **GCS 連携**: 既存の DIVE と同じく Google Cloud Storage バケットへの映像格納（`tools/analyze_video_gemini.py` L104-108 の GCS URI 構築ロジックを流用）
- **フレーム抽出**: `extract_video_frames.py` のフレーム抽出ロジックをそのまま利用
- **メタデータ取得**: `utils.py` L101-133 の `get_video_metadata()` を利用し、映像の解像度・フレーム数・FPS を自動取得

#### 2.1.2 製造業特化クエリテンプレート [優先度: 高]

プリセット質問テンプレートを提供し、非技術者でも品質検査クエリを容易に実行できるようにする。

```python
INSPECTION_TEMPLATES = {
    "appearance": [
        "製品の外観に傷、へこみ、変色などの異常はないか",
        "溶接ビードに割れ、ブローホール、アンダーカットなどの欠陥はないか",
        "塗装面にムラ、垂れ、剥がれはないか",
        "組立後の部品に位置ずれや隙間はないか",
    ],
    "procedure": [
        "作業手順は規定通りに実行されているか",
        "組立の順序は正しいか（手順書との照合）",
        "締め付けトルクの確認動作は行われているか",
        "検査工程が省略されていないか",
    ],
    "safety": [
        "作業員は安全装備（ヘルメット、保護メガネ、手袋）を着用しているか",
        "危険区域への不正侵入はないか",
        "機械の安全カバーは閉じた状態で稼働しているか",
        "非常停止装置は視認可能な位置にあるか",
    ],
    "equipment": [
        "使用工具は正しいものが選択されているか",
        "計測器の校正状態は適切か",
        "治具のセット位置は正しいか",
        "消耗品（ドリルビット、砥石等）の摩耗状態は許容範囲内か",
    ],
}
```

#### 2.1.3 物体検出の製造業カスタマイズ [優先度: 高]

DIVE の Grounding DINO パイプライン（`generate_video_summary.py` L43-104）を活用し、以下の製造業固有オブジェクトを検出対象とする。

```python
MANUFACTURING_TARGET_CLASSES = [
    # 作業員・保護具
    "person", "helmet", "safety_glasses", "gloves", "safety_vest",
    # 製品・部品
    "product", "component", "PCB", "connector", "screw", "bolt", "nut",
    # 工具・装置
    "screwdriver", "wrench", "soldering_iron", "welding_torch",
    "measuring_instrument", "caliper", "multimeter",
    # 設備
    "conveyor_belt", "robotic_arm", "press_machine", "inspection_station",
    # 異常兆候
    "crack", "scratch", "dent", "discoloration", "leak", "spark",
]
```

既存の `_generate_target_objects()` (`generate_video_summary.py` L386-449) では GPT-4.1 がフレームから動的にオブジェクトリストを生成するが、製造業版では上記の静的クラスリストと動的生成を組み合わせる。

#### 2.1.4 異常検知ロジック [優先度: 最高]

`answer_question` ノード（`nodes.py` L114-213）のシステムプロンプトを製造業コンテキストに特化させる。

**改修対象**: `nodes.py` L138-148 のシステムプロンプト

```python
# 現行 DIVE のシステムプロンプト（nodes.py L138-148）:
system_message = textwrap.dedent("""
    You are an AI assistant that analyzes video frames and answers questions
    based on the visual content. ...
""")

# 製造業版に改修:
system_message = textwrap.dedent("""
    あなたは製造業の品質検査エキスパートAIです。生産ライン映像を分析し、
    品質異常の有無を判定します。

    判定基準:
    - 正常 (OK): 規定の外観基準・作業手順・安全基準を満たしている
    - 異常 (NG): 明確な欠陥・手順逸脱・安全違反が確認される
    - 要確認 (WARN): 異常の可能性があるが確信度が低い、追加検査推奨

    回答には必ず以下を含めてください:
    1. 判定結果 (OK / NG / WARN)
    2. 検出された異常の具体的内容と映像内の位置（フレーム番号、画面座標）
    3. 判定の根拠となるエビデンス
    4. 推奨アクション（異常の場合）
    5. 確信度スコア (0.0 - 1.0)

    利用可能なツール:
    - Gemini 2.5 Pro: 作業手順の時系列検証、動作の連続性確認に使用
    - GPT-4.1 Vision: 製品外観の微細欠陥検出、寸法精度の視覚的評価に使用
""")
```

#### 2.1.5 検査レポート自動生成 [優先度: 高]

`finalize_answer` ノード（`nodes.py` L373-432）を拡張し、構造化された検査レポートを出力する。

**改修対象**: `nodes.py` L399 のシステムプロンプト、および出力形式

```python
# 検査レポートの構造化出力スキーマ
class InspectionReport(BaseModel):
    inspection_id: str = Field(..., description="検査ID (自動生成)")
    production_line_id: str = Field(..., description="生産ラインID")
    inspection_type: str = Field(..., description="検査種別: appearance/procedure/safety/equipment")
    timestamp: str = Field(..., description="検査実施日時")
    overall_judgment: str = Field(..., description="総合判定: OK / NG / WARN")
    confidence_score: float = Field(..., description="判定確信度 0.0-1.0")
    defects: List[DefectDetail] = Field(default_factory=list, description="検出された異常リスト")
    evidence_summary: str = Field(..., description="判定根拠の要約")
    recommended_actions: List[str] = Field(default_factory=list, description="推奨アクション")
    sub_inspection_results: List[Dict[str, str]] = Field(..., description="サブ検査結果一覧")

class DefectDetail(BaseModel):
    defect_type: str = Field(..., description="異常種別")
    severity: str = Field(..., description="重大度: critical/major/minor")
    location: str = Field(..., description="異常箇所（フレーム番号・座標）")
    description: str = Field(..., description="異常の詳細説明")
    evidence_frames: List[int] = Field(..., description="エビデンスとなるフレーム番号リスト")
```

#### 2.1.6 推論過程の監査ログ [優先度: 中]

既存の `log_thinking` 構造（`main.py` L84-92）を活用し、検査根拠を完全に記録する。

```python
# 現行 DIVE の log_thinking（main.py L84-92）:
log_thinking = {
    "sub_questions": agents_result["sub_questions"],
    "qa_results": agents_result["qa_results"],
    "continue_reasons": agents_result["continue_reasons"],
    "tool_results": agents_result.get("tool_results", []),
    "question_intent": agents_result.get("question_intent", "")
}

# 製造業版に拡張:
audit_log = {
    # 既存フィールド（そのまま継承）
    "sub_questions": agents_result["sub_questions"],
    "qa_results": agents_result["qa_results"],
    "continue_reasons": agents_result["continue_reasons"],
    "tool_results": agents_result.get("tool_results", []),
    "question_intent": agents_result.get("question_intent", ""),
    # 製造業固有フィールド
    "inspection_type": agents_result.get("inspection_type", ""),
    "production_line_id": agents_result.get("production_line_id", ""),
    "defect_categories": agents_result.get("defect_categories", []),
    "severity_levels": agents_result.get("severity_levels", []),
    "judgment_history": agents_result.get("judgment_history", []),
    "evidence_frames": agents_result.get("evidence_frames", []),
    "operator_id": agents_result.get("operator_id", ""),
    "lot_number": agents_result.get("lot_number", ""),
}
```

---

## 3. アーキテクチャ設計

### 3.1 LangGraph ワークフロー（製造業版）

DIVE の `StateGraph`（`main.py` L37-61）をベースに、製造業固有ノードを追加する。

```
[映像入力・前処理]
        │
        ▼
[infer_inspection_intent]  ← nodes.py L30-66 を改修
        │
        ▼
[classify_inspection_type]  ← 新規ノード: 検査種別の自動分類
        │
        ▼
[split_inspection_points]  ← nodes.py L69-111 を改修
        │
        ▼
[analyze_inspection_point]  ← nodes.py L114-213 を改修
        │
        ▼
[assess_defect_severity]  ← 新規ノード: 異常重大度の判定
        │
        ▼
[refine_inspection_points]  ← nodes.py L216-286 を改修
        │
        ▼
[should_continue_inspection]  ← nodes.py L289-370 を改修
        │
   ┌────┴────┐
   ▼         ▼
[続行]   [generate_inspection_report]  ← nodes.py L373-432 を改修
   │         │
   └─→ [analyze_inspection_point]      ▼
                                 [output_report]  ← 新規ノード: レポート出力
```

### 3.2 `AgentState` の拡張

**改修対象**: `main.py` L19-33

```python
class ManufacturingAgentState(TypedDict):
    # === DIVE 既存フィールド（継承） ===
    video_id: str
    original_question: str
    question_intent: str
    image_path: str
    video_path: str
    video_metadata: Optional[Dict[str, int | float | str]]
    sub_questions: Dict[int, List[str]]
    qa_results: List[Dict[str, str]]
    tool_results: List[Dict[str, str]]
    iter: int
    max_iter: int
    continue_flag: bool
    continue_reasons: List[str]
    final_answer: Optional[str]

    # === 製造業固有フィールド（新規） ===
    inspection_type: str                        # 検査種別: appearance/procedure/safety/equipment
    production_line_id: str                     # 生産ラインID
    lot_number: Optional[str]                   # ロット番号
    operator_id: Optional[str]                  # 作業者ID
    defect_categories: List[str]                # 検出された異常カテゴリ
    severity_level: Optional[str]               # 最大重大度: critical/major/minor
    judgment: Optional[str]                     # 総合判定: OK/NG/WARN
    confidence_score: Optional[float]           # 判定確信度 (0.0-1.0)
    inspection_report: Optional[Dict]           # 構造化検査レポート
    reference_standards: Optional[List[str]]    # 参照する検査基準書
    detected_objects: Optional[List[Dict]]      # 検出されたオブジェクト情報
    judgment_history: List[Dict[str, str]]      # 各イテレーションの判定履歴
```

### 3.3 各ノードの製造業向けプロンプト改修方針

#### 3.3.1 `infer_question_intent` → `infer_inspection_intent`

**改修対象**: `nodes.py` L30-66

- **改修内容**: システムプロンプト（L44）を製造業品質検査の文脈に変更
- **変更点**:
  - 検査意図の分類（外観検査 / 作業手順検証 / 安全確認 / 設備点検）
  - 検査基準への参照（JIS, ISO 規格等）
  - ポカヨケ（誤り防止）の観点を含める

```python
system_message = (
    "あなたは製造業の品質管理エキスパートです。"
    "生産ライン映像に関する検査クエリの真の意図を推定してください。"
    "意図は以下のカテゴリに分類してください: "
    "外観検査(appearance), 作業手順検証(procedure), "
    "安全確認(safety), 設備点検(equipment)。"
    "工程管理、ポカヨケ、不良品率の観点を考慮し、"
    "検査の目的と必要なエビデンスを明確にしてください。"
)
```

#### 3.3.2 `split_question` → `split_inspection_points`

**改修対象**: `nodes.py` L69-111

- **改修内容**: サブ質問の分解を検査観点ベースに変更
- **変更点**:
  - 検査チェックリスト形式での分解
  - 各検査項目に対応する判定基準の明示
  - 4M（Man/Machine/Material/Method）の観点での分解

```python
system_message = (
    "あなたは品質管理のアシスタントです。"
    "生産ライン映像の検査クエリを、4M（Man, Machine, Material, Method）の"
    "観点からサブ検査項目に分解してください。"
    "各サブ検査項目には、明確な判定基準（合格/不合格の境界）を含めてください。"
    "サブ検査項目のリスト形式で回答してください。"
)
```

#### 3.3.3 `answer_question` → `analyze_inspection_point`

**改修対象**: `nodes.py` L114-213

- **改修内容**: エージェントのシステムプロンプトとツール選択戦略を製造業に特化
- **変更点**:
  - 正常 / 異常 / 要確認の3段階判定
  - 異常検出時のフレーム番号・座標の記録
  - ツール使い分け指示の明確化

#### 3.3.4 `should_continue` → `should_continue_inspection`

**改修対象**: `nodes.py` L289-370

- **改修内容**: 検査完了の判定基準を製造業向けに変更
- **変更点**:
  - すべての検査項目が判定済みかの確認
  - 異常検出時は関連する追加検査項目を自動生成
  - 最大イテレーション数の調整（`main.py` L77 の `max_iter: 25` → 製造業では `10` 程度に削減）

#### 3.3.5 `finalize_answer` → `generate_inspection_report`

**改修対象**: `nodes.py` L373-432

- **改修内容**: 最終回答を構造化検査レポート形式に変更
- **変更点**:
  - `InspectionReport` スキーマに準拠した構造化出力
  - 異常箇所のフレーム番号・座標を含むエビデンス集約
  - 推奨アクション（再検査、ライン停止、メンテナンス要請等）の生成

### 3.4 マルチモデル戦略

DIVE の既存マルチモデル構成（`nodes.py` L183）を踏襲しつつ、製造業での使い分けを明確化する。

| モデル | ツール関数 | 製造業での用途 | 根拠 |
|---|---|---|---|
| Gemini 2.5 Pro | `analyze_video_gemini()` (`tools/analyze_video_gemini.py` L91-129) | 作業手順の時系列検証、動作の正確性確認、音声情報（異音検出）の活用 | 1秒1フレーム＋音声分析（L94-98）により、作業の連続的な流れを時系列で追跡可能 |
| GPT-4.1 Vision | `analyze_video_openai_with_frame_selection()` (`tools/vision_tool_fixed_input.py` L75-142) | 製品外観の微細欠陥検出（傷、へこみ、変色）、寸法精度の視覚的評価 | フレーム選択機能（L104）と高精細画像分析により、特定箇所の詳細な視覚検査が可能 |
| Grounding DINO | `process_video()` (`generate_video_summary.py` L43-104) | 部品・製品・保護具のゼロショット物体検出、位置トラッキング | バウンディングボックス付き検出結果（CSV出力）により、定量的な位置・存在判定が可能 |

---

## 4. 技術スタック・開発環境

### 4.1 既存 DIVE 依存関係の継承

`docker/requirements.txt` をベースに、以下をそのまま継承する:

```
# AI/ML コア
langchain==0.3.25
langchain-openai==0.3.16
langgraph==0.4.3
openai==1.78.0
google-genai==1.16.1

# 映像処理
opencv-python-headless==4.11.0.86
ffmpeg-python==0.2.0
numpy>=1.21.0

# 物体検出
torch>=2.0.0
torchvision>=0.15.0
transformers>=4.30.0
timm>=0.9.0
accelerate>=0.20.0

# ユーティリティ
pydantic>=2.0.0
filelock==3.18.0
pandas==2.2.3
tqdm>=4.64.0
google-cloud-storage==3.1.0
```

### 4.2 追加コンポーネント

```
# Web フレームワーク（ダッシュボード・API）
fastapi>=0.115.0
uvicorn>=0.34.0
python-multipart>=0.0.18     # ファイルアップロード

# データベース（検査結果永続化）
sqlalchemy>=2.0.0
alembic>=1.15.0              # マイグレーション管理
aiosqlite>=0.21.0            # 非同期 SQLite（MVP 段階）

# フロントエンド（Phase 3）
jinja2>=3.1.0                # テンプレートエンジン

# 映像ストリーミング（Phase 2）
aiortc>=1.9.0                # WebRTC
```

### 4.3 開発環境セットアップ

```bash
# 1. リポジトリクローン
git clone https://github.com/madmerger/DIVE.git
cd DIVE

# 2. Python 仮想環境
python3 -m venv .venv
source .venv/bin/activate

# 3. 依存関係インストール
pip install -r docker/requirements.txt
pip install fastapi uvicorn python-multipart sqlalchemy alembic aiosqlite

# 4. 環境変数設定
export GOOGLE_CLOUD_PROJECT=your_project_id
export GOOGLE_CLOUD_LOCATION=your_region
export GOOGLE_CLOUD_BUCKET_NAME=your_bucket
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
export OPENAI_API_KEY=your_openai_api_key

# 5. Docker 環境（GPU 利用時）
cd docker
docker compose build
```

---

## 5. MVP 開発フェーズ分割

### Phase 1: バッチ映像分析（既存 DIVE 機能の製造業特化）

**期間目安**: 2-3 週間
**ゴール**: 録画済み映像をアップロードし、品質検査レポートを生成できる

| 機能 | 概要 | ベースとなる DIVE コード |
|---|---|---|
| 映像アップロード API | REST API で映像ファイルを受け付け、GCS にアップロード | `tools/analyze_video_gemini.py` L104-108 |
| `ManufacturingAgentState` 定義 | 製造業固有フィールドを含む状態管理 | `main.py` L19-33 |
| 検査意図推定 | クエリから検査種別を自動分類 | `nodes.py` L30-66 |
| 検査項目分解 | 検査クエリを 4M 観点でサブ項目に分解 | `nodes.py` L69-111 |
| マルチモデル映像分析 | Gemini + GPT-4.1 による検査実行 | `nodes.py` L114-213 |
| 異常判定・重大度分類 | OK/NG/WARN 判定と severity 分類 | 新規実装 |
| 検査レポート生成 | 構造化レポート (JSON) の自動生成 | `nodes.py` L373-432 |
| 監査ログ保存 | 推論過程の完全記録 | `main.py` L84-92 |
| クエリテンプレート | 製造業特化のプリセット質問 | 新規実装 |
| 物体検出カスタマイズ | 製造業向けターゲットクラスの設定 | `generate_video_summary.py` L43-104 |

### Phase 2: リアルタイム監視・アラート

**期間目安**: 3-4 週間
**ゴール**: 生産ラインカメラのリアルタイム映像を監視し、異常検出時にアラートを発報

| 機能 | 概要 |
|---|---|
| 映像ストリーミング取り込み | RTSP/WebRTC による生産ラインカメラ映像のリアルタイム取得 |
| セグメント分割処理 | 映像を一定間隔（例: 30秒）のセグメントに分割し、逐次分析 |
| 閾値ベースアラート | 確信度スコアが閾値を超えた場合のリアルタイム通知 |
| アラート通知 | Slack/メール/ダッシュボードへのアラート送信 |
| 連続異常検知 | 同一異常の連続検出による重大度エスカレーション |

### Phase 3: ダッシュボード・レポーティング

**期間目安**: 2-3 週間
**ゴール**: Web ダッシュボードで検査結果の可視化・分析・帳票出力が可能

| 機能 | 概要 |
|---|---|
| Web ダッシュボード | FastAPI + Jinja2 による検査結果一覧・詳細表示 |
| 統計分析 | 不良品率の推移、異常種別の分布、ライン別比較 |
| 検査レポート帳票出力 | PDF/Excel 形式での検査レポートダウンロード |
| トレンド可視化 | Chart.js による時系列グラフ（不良品率、検出数推移） |
| 検索・フィルタ | 日時・ライン・検査種別・判定結果によるフィルタリング |

---

## 6. 具体的な開発タスクリスト

### Phase 1 タスク詳細

#### タスク 1.1: プロジェクト構造の構築

**対象ファイル**: 新規作成

```
DIVE/
├── manufacturing/                     # 製造業 MVP ルートディレクトリ
│   ├── __init__.py
│   ├── app.py                         # FastAPI アプリケーション
│   ├── config.py                      # 設定管理（環境変数、定数）
│   ├── models/
│   │   ├── __init__.py
│   │   ├── state.py                   # ManufacturingAgentState 定義
│   │   ├── schemas.py                 # InspectionReport, DefectDetail 等の Pydantic スキーマ
│   │   └── database.py               # SQLAlchemy モデル
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── infer_inspection_intent.py # 検査意図推定ノード
│   │   ├── classify_inspection.py     # 検査種別分類ノード（新規）
│   │   ├── split_inspection.py        # 検査項目分解ノード
│   │   ├── analyze_inspection.py      # 映像分析ノード
│   │   ├── assess_severity.py         # 重大度判定ノード（新規）
│   │   ├── refine_inspection.py       # 検査項目洗練ノード
│   │   ├── should_continue.py         # 継続判定ノード
│   │   └── generate_report.py         # レポート生成ノード
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── gemini_inspector.py        # Gemini 製造業特化ツール
│   │   ├── gpt4_inspector.py          # GPT-4.1 製造業特化ツール
│   │   └── object_detector.py         # Grounding DINO 製造業特化ラッパー
│   ├── workflow/
│   │   ├── __init__.py
│   │   └── graph.py                   # LangGraph ワークフロー定義
│   ├── templates/
│   │   └── query_templates.py         # 検査クエリテンプレート
│   └── utils/
│       ├── __init__.py
│       ├── video.py                   # 映像処理ユーティリティ
│       └── audit_log.py               # 監査ログユーティリティ
├── tests/
│   └── manufacturing/
│       ├── test_state.py
│       ├── test_nodes.py
│       └── test_workflow.py
```

#### タスク 1.2: `ManufacturingAgentState` の実装

**対象ファイル**: `manufacturing/models/state.py` (新規作成)
**参照**: `main.py` L19-33

- `AgentState` を継承し、製造業固有フィールドを追加（3.2 節参照）
- 初期値の設定（`max_iter` は `10` に設定）

#### タスク 1.3: 検査意図推定ノードの実装

**対象ファイル**: `manufacturing/nodes/infer_inspection_intent.py` (新規作成)
**参照**: `nodes.py` L30-66

- `infer_question_intent()` のロジックを流用
- システムプロンプトを製造業コンテキストに変更（3.3.1 節参照）
- `inspection_type` フィールドの自動設定ロジックを追加
- `load_video_summary_message()` (`utils.py` L276-300) をそのまま利用

#### タスク 1.4: 検査種別分類ノードの実装

**対象ファイル**: `manufacturing/nodes/classify_inspection.py` (新規作成)

- 新規ノード: 検査意図から検査種別（appearance/procedure/safety/equipment）を分類
- 検査種別に応じた後続処理パラメータの設定
- Pydantic の構造化出力で分類結果を返す

#### タスク 1.5: 検査項目分解ノードの実装

**対象ファイル**: `manufacturing/nodes/split_inspection.py` (新規作成)
**参照**: `nodes.py` L69-111

- `split_question()` のロジックを流用
- 4M 観点でのサブ検査項目分解に改修（3.3.2 節参照）
- `SplitQuestionSubQuestions` スキーマを `InspectionCheckItems` に置換

#### タスク 1.6: 映像分析ノードの実装

**対象ファイル**: `manufacturing/nodes/analyze_inspection.py` (新規作成)
**参照**: `nodes.py` L114-213

- `answer_question()` のエージェント構造を流用
- システムプロンプトを製造業品質検査に特化（2.1.4 節参照）
- ツール登録: `gemini_inspector` + `gpt4_inspector`
- エージェント実行のリトライロジック（L187-196）をそのまま継承
- 環境変数経由の状態受け渡し（L172-175）をそのまま継承

#### タスク 1.7: 異常重大度判定ノードの実装

**対象ファイル**: `manufacturing/nodes/assess_severity.py` (新規作成)

- 新規ノード: 検出された異常に対して重大度（critical/major/minor）を判定
- 重大度判定基準:
  - **critical**: 製品の安全性に影響、即時ライン停止が必要
  - **major**: 機能・外観に明確な不具合、後工程での修正不可
  - **minor**: 軽微な外観異常、許容範囲の判断が必要

#### タスク 1.8: Gemini 製造業特化ツールの実装

**対象ファイル**: `manufacturing/tools/gemini_inspector.py` (新規作成)
**参照**: `tools/analyze_video_gemini.py` L91-129

- `analyze_video_gemini()` のロジックを流用
- システムプロンプト（L110-118）を製造業向けに変更:
  - 作業手順の時系列検証に特化
  - 音声情報を活用した異音検出
  - 動作の正確性・速度・順序の評価

#### タスク 1.9: GPT-4.1 製造業特化ツールの実装

**対象ファイル**: `manufacturing/tools/gpt4_inspector.py` (新規作成)
**参照**: `tools/vision_tool_fixed_input.py` L75-142

- `analyze_video_openai_with_frame_selection()` のロジックを流用
- フレーム選択ロジック（`utils.py` L136-208 の `select_frames()`）を製造業向けに調整
- システムプロンプト（L106-113）を製造業向けに変更:
  - 微細欠陥（傷、へこみ、変色、異物混入）の検出に特化
  - 寸法精度の視覚的評価
  - 表面品質の定量的評価

#### タスク 1.10: 検査レポート生成ノードの実装

**対象ファイル**: `manufacturing/nodes/generate_report.py` (新規作成)
**参照**: `nodes.py` L373-432

- `finalize_answer()` のロジックを流用
- 出力を `InspectionReport` スキーマに準拠した構造化データに変更（2.1.5 節参照）
- エビデンスの集約（フレーム番号、検出座標、ツール出力の引用）

#### タスク 1.11: LangGraph ワークフローの構築

**対象ファイル**: `manufacturing/workflow/graph.py` (新規作成)
**参照**: `main.py` L37-61

- `StateGraph(ManufacturingAgentState)` の構築
- ノード追加・エッジ定義（3.1 節のフロー参照）
- 条件分岐（`should_continue_inspection` の判定結果に基づく）

```python
# main.py L37-61 を参照したワークフロー構築
workflow = StateGraph(ManufacturingAgentState)

workflow.add_node("infer_intent", infer_inspection_intent)
workflow.add_node("classify_type", classify_inspection_type)
workflow.add_node("split_inspection", split_inspection_points)
workflow.add_node("analyze_point", analyze_inspection_point)
workflow.add_node("assess_severity", assess_defect_severity)
workflow.add_node("refine_points", refine_inspection_points)
workflow.add_node("should_continue", should_continue_inspection)
workflow.add_node("generate_report", generate_inspection_report)

workflow.set_entry_point("infer_intent")
workflow.add_edge("infer_intent", "classify_type")
workflow.add_edge("classify_type", "split_inspection")
workflow.add_edge("split_inspection", "analyze_point")
workflow.add_edge("analyze_point", "assess_severity")
workflow.add_edge("assess_severity", "refine_points")
workflow.add_edge("refine_points", "should_continue")

workflow.add_conditional_edges(
    "should_continue",
    lambda state: "continue" if state["continue_flag"] else "finalize",
    {
        "continue": "analyze_point",
        "finalize": "generate_report",
    }
)
workflow.add_edge("generate_report", END)
```

#### タスク 1.12: FastAPI アプリケーションの構築

**対象ファイル**: `manufacturing/app.py` (新規作成)

```python
# API エンドポイント設計
POST /api/v1/inspect              # 映像アップロード＋検査実行
GET  /api/v1/inspect/{id}         # 検査結果取得
GET  /api/v1/inspect/{id}/report  # 検査レポート取得
GET  /api/v1/inspect/{id}/audit   # 監査ログ取得
GET  /api/v1/templates            # クエリテンプレート一覧
POST /api/v1/inspect/batch        # バッチ検査実行
```

#### タスク 1.13: 物体検出の製造業カスタマイズ

**対象ファイル**: `manufacturing/tools/object_detector.py` (新規作成)
**参照**: `generate_video_summary.py` L43-104, L386-449

- `process_video()` のロジックを流用
- `MANUFACTURING_TARGET_CLASSES` を静的ターゲットクラスとして設定
- 動的ターゲット生成（`_generate_target_objects()` L386-449）と静的リストのマージ
- Grounding DINO の閾値調整（製造業向け: `box_threshold=0.25`, `text_threshold=0.20` に変更し、欠陥検出の感度を向上）

#### タスク 1.14: データベーススキーマの設計・実装

**対象ファイル**: `manufacturing/models/database.py` (新規作成)

```python
# 主要テーブル
class Inspection(Base):
    """検査結果テーブル"""
    id: str                    # 検査ID
    production_line_id: str    # 生産ラインID
    inspection_type: str       # 検査種別
    video_path: str            # 映像パス
    query: str                 # 検査クエリ
    judgment: str              # 判定結果 (OK/NG/WARN)
    confidence_score: float    # 確信度
    report_json: str           # 構造化レポート (JSON)
    audit_log_json: str        # 監査ログ (JSON)
    created_at: datetime       # 検査実施日時

class Defect(Base):
    """異常検出テーブル"""
    id: str                    # 異常ID
    inspection_id: str         # 検査ID (FK)
    defect_type: str           # 異常種別
    severity: str              # 重大度
    location: str              # 異常箇所
    description: str           # 異常詳細
    evidence_frames: str       # エビデンスフレーム (JSON)
```

#### タスク 1.15: 監査ログユーティリティの実装

**対象ファイル**: `manufacturing/utils/audit_log.py` (新規作成)
**参照**: `main.py` L84-92

- `log_thinking` 構造を拡張（2.1.6 節参照）
- JSON 形式での永続化
- タイムスタンプ付きのイベントログ記録

---

## 付録 A: 用語集

| 用語 | 説明 |
|---|---|
| 不良品率 (Defect Rate) | 生産品のうち品質基準を満たさない割合 |
| 工程管理 (Process Control) | 製造工程の品質を一定に保つための管理活動 |
| ポカヨケ (Poka-yoke) | ヒューマンエラーを防止する仕組み |
| 4M | Man（人）, Machine（機械）, Material（材料）, Method（方法）の品質管理要素 |
| QC工程表 | 品質管理の工程と管理項目を定めた文書 |
| トレーサビリティ | 製品の生産履歴を追跡できる仕組み |
| SPC (統計的工程管理) | 統計手法を用いた工程の安定性管理 |
| CPK (工程能力指数) | 工程がどれだけ規格内に収まっているかの指標 |

## 付録 B: DIVE 既存コード参照マップ

| 製造業 MVP コンポーネント | DIVE 既存ファイル | 行番号 | 流用方法 |
|---|---|---|---|
| 状態管理 | `main.py` | L19-33 | `AgentState` を継承・拡張 |
| ワークフロー定義 | `main.py` | L37-61 | `StateGraph` 構築パターンを流用 |
| ワークフロー初期値 | `main.py` | L65-82 | `graph.invoke()` の引数パターンを流用 |
| 推論ログ出力 | `main.py` | L84-92 | `log_thinking` 構造を拡張 |
| 意図推定ノード | `nodes.py` | L30-66 | プロンプト改修、ロジックは流用 |
| 質問分解ノード | `nodes.py` | L69-111 | プロンプト改修、構造化出力は流用 |
| 映像分析ノード | `nodes.py` | L114-213 | エージェント構造を流用、プロンプト改修 |
| 質問洗練ノード | `nodes.py` | L216-286 | プロンプト改修、ロジックは流用 |
| 継続判定ノード | `nodes.py` | L289-370 | 判定基準を製造業向けに改修 |
| 最終回答ノード | `nodes.py` | L373-432 | 出力形式を構造化レポートに変更 |
| Gemini ツール | `tools/analyze_video_gemini.py` | L91-129 | GCS 連携を流用、プロンプト改修 |
| Gemini API 呼び出し | `tools/analyze_video_gemini.py` | L49-88 | `ask_gemini_vertex()` をそのまま流用 |
| GPT-4.1 ツール | `tools/vision_tool_fixed_input.py` | L75-142 | フレーム選択を流用、プロンプト改修 |
| フレーム選択 | `utils.py` | L136-208 | `select_frames()` を流用・調整 |
| フレームエンコード | `utils.py` | L57-98 | `encode_images()` をそのまま流用 |
| 映像メタデータ取得 | `utils.py` | L101-133 | `get_video_metadata()` をそのまま流用 |
| 映像サマリ読込 | `utils.py` | L276-300 | `load_video_summary_message()` をそのまま流用 |
| 物体検出パイプライン | `generate_video_summary.py` | L43-104 | `process_video()` を流用、ターゲットクラス変更 |
| ターゲットオブジェクト生成 | `generate_video_summary.py` | L386-449 | `_generate_target_objects()` を流用・拡張 |
| 映像要約生成 | `generate_video_summary.py` | L527-602 | `summarize_video()` を流用、プロンプト改修 |
| フレーム抽出 | `extract_video_frames.py` | 全体 | そのまま流用 |
| Docker 環境 | `docker/Dockerfile` | 全体 | ベースイメージとして流用 |
| 依存関係 | `docker/requirements.txt` | 全体 | 全依存関係を継承 |
