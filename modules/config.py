"""
設定管理モジュール
環境変数 → .env → デフォルト値 の優先度で設定を読み込む
"""
import os
from dotenv import load_dotenv

# ── パス定数 ──
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(_MODULE_DIR)
_PROJECT_ROOT = os.path.dirname(_APP_DIR)

# .env の読み込み（プロジェクトルートから）
load_dotenv(os.path.join(_PROJECT_ROOT, '.env'))


def _resolve_folder(env_key, default_name, fallback_name):
    """フォルダパスを解決する（環境変数 → デフォルト → フォールバック）"""
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val if os.path.isabs(env_val) else os.path.join(_APP_DIR, env_val)
    default = os.path.join(_APP_DIR, default_name)
    if os.path.exists(default):
        return default
    fallback = os.path.join(_APP_DIR, fallback_name)
    if os.path.exists(fallback):
        return fallback
    return default


class Config:
    """アプリケーション設定"""

    # ── パス ──
    PROJECT_ROOT = _PROJECT_ROOT
    APP_DIR = _APP_DIR
    MODULE_DIR = _MODULE_DIR
    CACHE_DIR = os.path.join(_MODULE_DIR, 'cache')
    LOG_DIR = os.path.join(_APP_DIR, 'logs')
    DB_PATH = os.path.join(_MODULE_DIR, 'cache', 'drawings.db')

    DRAWING_DIR = _resolve_folder(
        'DRAWING_DIR', '図面一覧', 'ナガセ　類似図面検索テスト用　図面'
    )
    PROCESS_DIR = _resolve_folder(
        'PROCESS_DIR', '工程一覧', 'ナガセ　類似図面検索テスト用　工程'
    )

    # ── 検索重み ──
    WEIGHT_CONTOUR = float(os.environ.get('WEIGHT_CONTOUR', '0.30'))
    WEIGHT_CLIP = float(os.environ.get('WEIGHT_CLIP', '0.35'))
    WEIGHT_SIFT = float(os.environ.get('WEIGHT_SIFT', '0.25'))
    WEIGHT_ATTR = float(os.environ.get('WEIGHT_ATTR', '0.10'))

    # ── FAISS ──
    FAISS_TOP_K = int(os.environ.get('FAISS_TOP_K', '50'))
    DISPLAY_TOP_K = int(os.environ.get('DISPLAY_TOP_K', '10'))

    # ── サムネイル ──
    THUMB_MAX_WIDTH = int(os.environ.get('THUMB_MAX_WIDTH', '400'))
    THUMB_QUALITY = int(os.environ.get('THUMB_QUALITY', '85'))

    # ── CLIP モデル ──
    CLIP_MODEL_NAME = os.environ.get('CLIP_MODEL_NAME', 'clip-ViT-B-32')

    # ── SIFT ──
    SIFT_MATCH_RATIO = float(os.environ.get('SIFT_MATCH_RATIO', '0.75'))

    # ── ログ ──
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_RETENTION_DAYS = int(os.environ.get('LOG_RETENTION_DAYS', '7'))
