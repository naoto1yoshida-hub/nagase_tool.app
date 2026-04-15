"""
SQLiteデータベース管理モジュール
図面と工程表の情報を一元管理する
- コンテキストマネージャによる安全な接続管理
- 複数ページPDF対応 (page_number)
- バッチトランザクション対応
"""
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

from modules.config import Config
from modules.logger import get_logger

logger = get_logger('database')


@contextmanager
def get_connection():
    """データベース接続をコンテキストマネージャで取得する"""
    os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """テーブルを作成し、必要に応じてスキーマ移行を行う"""
    with get_connection() as conn:
        # 既存テーブルの有無を確認
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drawings'"
        ).fetchone()

        if existing:
            _migrate_schema(conn)
        else:
            _create_table(conn)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_file_name ON drawings(file_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_drawing_path ON drawings(drawing_path)")
    logger.info("データベース初期化完了")


def _create_table(conn):
    """新規テーブルを作成する"""
    conn.execute("""
        CREATE TABLE drawings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name     TEXT NOT NULL,
            drawing_path  TEXT NOT NULL,
            page_number   INTEGER DEFAULT 1,
            process_path  TEXT,
            material      TEXT,
            thickness     TEXT,
            has_clip      INTEGER DEFAULT 0,
            has_sift      INTEGER DEFAULT 0,
            has_contour   INTEGER DEFAULT 0,
            registered_at TEXT,
            UNIQUE(drawing_path, page_number)
        )
    """)


def _migrate_schema(conn):
    """既存テーブルをv2スキーマに移行する"""
    cursor = conn.execute("PRAGMA table_info(drawings)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'page_number' in columns:
        return  # 移行済み

    logger.info("データベーススキーマをv2に移行中…")

    conn.execute("""
        CREATE TABLE drawings_v2 (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name     TEXT NOT NULL,
            drawing_path  TEXT NOT NULL,
            page_number   INTEGER DEFAULT 1,
            process_path  TEXT,
            material      TEXT,
            thickness     TEXT,
            has_clip      INTEGER DEFAULT 0,
            has_sift      INTEGER DEFAULT 0,
            has_contour   INTEGER DEFAULT 0,
            registered_at TEXT,
            UNIQUE(drawing_path, page_number)
        )
    """)

    conn.execute("""
        INSERT INTO drawings_v2 (
            file_name, drawing_path, page_number, process_path,
            material, thickness, has_clip, has_sift, has_contour, registered_at
        )
        SELECT file_name, drawing_path, 1, process_path,
               material, thickness, has_clip, has_sift, has_contour, registered_at
        FROM drawings
    """)

    conn.execute("DROP TABLE drawings")
    conn.execute("ALTER TABLE drawings_v2 RENAME TO drawings")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_file_name ON drawings(file_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drawing_path ON drawings(drawing_path)")
    logger.info("スキーマ移行完了")


# ============================================================
# CRUD 操作
# ============================================================

def upsert_drawing(file_name, drawing_path, page_number=1, process_path=None,
                   material=None, thickness=None,
                   has_clip=0, has_sift=0, has_contour=0):
    """図面情報を登録/更新する"""
    with get_connection() as conn:
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO drawings (
                file_name, drawing_path, page_number, process_path,
                material, thickness, has_clip, has_sift, has_contour, registered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(drawing_path, page_number) DO UPDATE SET
                process_path  = COALESCE(excluded.process_path, process_path),
                material      = COALESCE(excluded.material, material),
                thickness     = COALESCE(excluded.thickness, thickness),
                has_clip      = MAX(excluded.has_clip, has_clip),
                has_sift      = MAX(excluded.has_sift, has_sift),
                has_contour   = MAX(excluded.has_contour, has_contour),
                registered_at = excluded.registered_at
        """, (file_name, drawing_path, page_number, process_path,
              material, thickness, has_clip, has_sift, has_contour, now))


def batch_upsert_drawings(drawings_data):
    """複数の図面情報を一括登録する（1トランザクション）"""
    with get_connection() as conn:
        now = datetime.now().isoformat()
        for d in drawings_data:
            conn.execute("""
                INSERT INTO drawings (
                    file_name, drawing_path, page_number, process_path,
                    material, thickness, has_clip, has_sift, has_contour, registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
                ON CONFLICT(drawing_path, page_number) DO UPDATE SET
                    process_path  = COALESCE(excluded.process_path, process_path),
                    registered_at = excluded.registered_at
            """, (
                d['file_name'], d['drawing_path'], d.get('page_number', 1),
                d.get('process_path'), d.get('material'), d.get('thickness'), now,
            ))
    logger.info(f"{len(drawings_data)}件の図面を一括登録")


def update_process_path(drawing_path, process_path):
    """工程表パスを更新する"""
    with get_connection() as conn:
        conn.execute(
            "UPDATE drawings SET process_path = ? WHERE drawing_path = ?",
            (process_path, drawing_path),
        )


def update_features_flags(drawing_path, page_number=1,
                          has_clip=None, has_sift=None, has_contour=None):
    """特徴量フラグを更新する"""
    updates, params = [], []
    if has_clip is not None:
        updates.append("has_clip = ?"); params.append(has_clip)
    if has_sift is not None:
        updates.append("has_sift = ?"); params.append(has_sift)
    if has_contour is not None:
        updates.append("has_contour = ?"); params.append(has_contour)
    if not updates:
        return
    params.extend([drawing_path, page_number])
    with get_connection() as conn:
        conn.execute(
            f"UPDATE drawings SET {', '.join(updates)} "
            f"WHERE drawing_path = ? AND page_number = ?",
            params,
        )


def update_attributes(drawing_path, material=None, thickness=None):
    """材質・板厚を更新する（全ページ共通）"""
    with get_connection() as conn:
        conn.execute(
            "UPDATE drawings SET material = ?, thickness = ? WHERE drawing_path = ?",
            (material, thickness, drawing_path),
        )


# ============================================================
# 検索・取得
# ============================================================

def get_all_drawings():
    """全図面を取得する"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM drawings ORDER BY file_name, page_number"
        ).fetchall()
        return [dict(r) for r in rows]


def get_drawing_by_path(drawing_path, page_number=None):
    """パスで図面を取得する"""
    with get_connection() as conn:
        if page_number is not None:
            row = conn.execute(
                "SELECT * FROM drawings WHERE drawing_path = ? AND page_number = ?",
                (drawing_path, page_number),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM drawings WHERE drawing_path = ? ORDER BY page_number",
                (drawing_path,),
            ).fetchone()
        return dict(row) if row else None


def search_by_name(query):
    """ファイル名で検索する（部分一致）"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM drawings WHERE file_name LIKE ? ORDER BY file_name, page_number",
            (f"%{query}%",),
        ).fetchall()
        return [dict(r) for r in rows]


def get_unprocessed_drawings():
    """未処理の図面を取得する"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM drawings WHERE has_clip = 0 OR has_sift = 0 OR has_contour = 0"
        ).fetchall()
        return [dict(r) for r in rows]


def get_drawing_count():
    """登録図面数を取得する"""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM drawings").fetchone()
        return row["cnt"] if row else 0


def get_registered_paths():
    """登録済みの全図面パスを取得する（差分チェック用・高速）"""
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT drawing_path FROM drawings").fetchall()
        return set(row["drawing_path"] for row in rows)


def is_registered(drawing_path):
    """登録済みかどうか確認する"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM drawings WHERE drawing_path = ?",
            (drawing_path,),
        ).fetchone()
        return row is not None
