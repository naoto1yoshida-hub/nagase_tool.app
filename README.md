# Nagase 社内支援ツール v3.0

現場の「探す」を支援する図面検索ツールです。
形状が似ている図面をPDFから検索し、関連する工程表を表示します。

## 主な機能

| 機能 | 説明 |
|------|------|
| **類似図面検索** | CLIP + SIFT + Hu Moments のハイブリッドAI検索 |
| **図番・ファイル名検索** | 部分一致によるキーワード検索 |
| **複数ページPDF対応** | 全ページを自動インデクシング |
| **差分自動登録** | 起動時に新規図面を自動検出・登録 |
| **工程表紐付け** | 図面と同名の工程表PDFを自動リンク |

## 動作環境

- Windows 10/11
- Python 3.8 以上
- **Poppler** (PDF処理用) がインストールされていること

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example` を `.env` にコピーして設定を記入してください。

```bash
copy .env.example ..\.env
```

主な設定項目:

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `OPENAI_API_KEY` | OpenAI APIキー（議事録機能用） | なし |
| `DRAWING_DIR` | 図面フォルダのパス | `図面一覧` |
| `PROCESS_DIR` | 工程フォルダのパス | `工程一覧` |

### 3. Popplerのインストール (Windows)

[Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases/) から最新版をダウンロードし、解凍した `bin` フォルダを環境変数 `PATH` に追加してください。

## 使い方

### アプリの起動

```bash
streamlit run app.py
```

または `run_app.bat` をダブルクリックしてください。

### 図面の登録

**方法1（自動）**: `DRAWING_DIR` に設定したフォルダにPDFを配置してアプリを起動すると、新規図面が自動で登録されます。

**方法2（手動）**: `run_indexer.bat` を実行して全図面を一括インデクシングします。

### フォルダ構成

```
DRAWING_DIR（図面一覧）/
├── subfolder/
│   ├── drawing1.pdf
│   └── drawing2.pdf
└── drawing3.pdf

PROCESS_DIR（工程一覧）/
└── drawing1.pdf  ← 図面と同じファイル名で自動紐付け
```

## トラブルシューティング

| 症状 | 対処法 |
|------|--------|
| PDF変換エラー | Popplerがインストール済みか確認（`pdftoppm --version`） |
| CLIP検索が動かない | `pip install sentence-transformers torch torchvision` を再実行 |
| 登録図面が0件 | 図面フォルダのパスを `.env` で確認。`run_indexer.bat` を実行 |
| サイドバーにエラー表示 | ヘルスチェック結果を確認し、該当コンポーネントを修正 |

## ログ

ログファイルは `logs/nagase_tool.log` に出力されます（日次ローテーション、7日保持）。
問題発生時はログファイルを確認してください。