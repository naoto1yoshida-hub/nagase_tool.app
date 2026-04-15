"""
ログ管理モジュール
ファイル出力（日次ローテーション・7日保持）+ コンソール出力
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from modules.config import Config

_LOG_INITIALIZED = False


def setup_logging():
    """ログの初期設定（アプリ起動時に一度だけ呼ばれる）"""
    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return

    os.makedirs(Config.LOG_DIR, exist_ok=True)

    root = logging.getLogger('nagase_tool')
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        '%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # ファイルハンドラ
    fh = TimedRotatingFileHandler(
        os.path.join(Config.LOG_DIR, 'nagase_tool.log'),
        when='midnight',
        backupCount=Config.LOG_RETENTION_DAYS,
        encoding='utf-8',
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # コンソールハンドラ
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
    ch.setFormatter(fmt)
    root.addHandler(ch)

    _LOG_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """モジュール用ロガーを取得する"""
    setup_logging()
    return logging.getLogger(f'nagase_tool.{name}')
