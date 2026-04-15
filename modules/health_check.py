"""
ヘルスチェックモジュール
アプリ起動時に外部依存の正常性を確認する
"""
import os
import shutil

from modules.config import Config
from modules.logger import get_logger

logger = get_logger('health_check')


def check_poppler():
    """Popplerの利用可能性を確認"""
    return shutil.which('pdftoppm') is not None


def check_tesseract():
    """Tesseractの利用可能性を確認"""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def check_database():
    """SQLiteデータベースの接続・件数を確認"""
    try:
        from modules.database import get_drawing_count
        count = get_drawing_count()
        return True, count
    except Exception as e:
        logger.error(f"DB接続エラー: {e}")
        return False, 0


def check_faiss_index():
    """FAISSインデックスの存在を確認"""
    idx = os.path.join(Config.CACHE_DIR, 'faiss_index.bin')
    idm = os.path.join(Config.CACHE_DIR, 'faiss_id_map.npy')
    return os.path.exists(idx) and os.path.exists(idm)


def check_drawing_folder():
    """図面フォルダの存在を確認"""
    return os.path.exists(Config.DRAWING_DIR)


def check_process_folder():
    """工程フォルダの存在を確認"""
    return os.path.exists(Config.PROCESS_DIR)


def run_all_checks():
    """全チェックを実行して結果辞書を返す"""
    db_ok, db_count = check_database()
    return {
        'poppler':        {'name': 'Poppler (PDF処理)',   'ok': check_poppler()},
        'tesseract':      {'name': 'Tesseract (OCR)',     'ok': check_tesseract()},
        'database':       {'name': f'データベース ({db_count}件)', 'ok': db_ok},
        'faiss':          {'name': 'FAISSインデックス',   'ok': check_faiss_index()},
        'drawing_folder': {'name': '図面フォルダ',        'ok': check_drawing_folder()},
        'process_folder': {'name': '工程フォルダ',        'ok': check_process_folder()},
    }
