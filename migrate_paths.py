import sqlite3
import os
import numpy as np
import hashlib
import glob

# パス設定
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_PATH, "modules", "cache")
DB_PATH = os.path.join(CACHE_DIR, "drawings.db")
ID_MAP_PATH = os.path.join(CACHE_DIR, "faiss_id_map.npy")
CLIP_CACHE_DIR = os.path.join(CACHE_DIR, "clip_vectors")

OLD_STR = "Pythonアプリ"
NEW_STR = "Python.app"

def migrate_db():
    print(f"--- データベース更新 ({DB_PATH}) ---")
    if not os.path.exists(DB_PATH):
        print("DBが見つかりません。スキップします。")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 現状確認
    cursor.execute("SELECT drawing_path FROM drawings LIMIT 1")
    row = cursor.fetchone()
    if not row:
        print("DBが空です。")
        return False
    
    first_path = row[0]
    print(f"サンプルパス: {first_path}")
    if OLD_STR not in first_path:
        print(f"警告: パスに '{OLD_STR}' が含まれていません。既に更新済みか、構成が異なります。")
        # 続行するが、置換が発生しないだけ
    
    # パスの更新
    cursor.execute(f"UPDATE drawings SET drawing_path = REPLACE(drawing_path, ?, ?)", (OLD_STR, NEW_STR))
    print(f"drawing_path を {cursor.rowcount} 件更新しました。")
    
    cursor.execute(f"UPDATE drawings SET process_path = REPLACE(process_path, ?, ?)", (OLD_STR, NEW_STR))
    print(f"process_path を {cursor.rowcount} 件更新しました。")

    conn.commit()
    conn.close()
    return True

def migrate_id_map():
    print(f"\n--- FAISS IDマップ更新 ({ID_MAP_PATH}) ---")
    if not os.path.exists(ID_MAP_PATH):
        print("IDマップが見つかりません。スキップします。")
        return

    id_map = np.load(ID_MAP_PATH, allow_pickle=True)
    new_id_map = [path.replace(OLD_STR, NEW_STR) for path in id_map]
    
    np.save(ID_MAP_PATH, np.array(new_id_map, dtype=object))
    print(f"{len(new_id_map)} 件のパスを更新しました。")

def migrate_clip_cache():
    print(f"\n--- CLIPベクトルキャッシュのリネーム ({CLIP_CACHE_DIR}) ---")
    if not os.path.exists(CLIP_CACHE_DIR):
        print("CLIPキャッシュフォルダが見つかりません。スキップします。")
        return

    # 全ての .npy ファイルを取得
    npy_files = glob.glob(os.path.join(CLIP_CACHE_DIR, "*.npy"))
    print(f"{len(npy_files)} 件のキャッシュファイルを検出。")

    # DBから新旧パスの対応を取得してリネーム
    if not os.path.exists(DB_PATH):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT drawing_path FROM drawings")
    rows = cursor.fetchall()
    conn.close()

    rename_count = 0
    for row in rows:
        new_path = row[0]
        old_path = new_path.replace(NEW_STR, OLD_STR)
        
        old_hash = hashlib.md5(old_path.encode()).hexdigest()
        new_hash = hashlib.md5(new_path.encode()).hexdigest()
        
        old_file = os.path.join(CLIP_CACHE_DIR, f"{old_hash}.npy")
        new_file = os.path.join(CLIP_CACHE_DIR, f"{new_hash}.npy")
        
        if os.path.exists(old_file) and old_hash != new_hash:
            if os.path.exists(new_file):
                os.remove(new_file) # 既存があれば削除
            os.rename(old_file, new_file)
            rename_count += 1

    print(f"{rename_count} 件のキャッシュファイルをリネームしました。")

if __name__ == "__main__":
    if migrate_db():
        migrate_id_map()
        migrate_clip_cache()
    print("\n移行作業が完了しました。")
