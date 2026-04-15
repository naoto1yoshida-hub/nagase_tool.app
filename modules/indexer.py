"""
バッチインデクサー & 自動同期モジュール
- run_indexer(): フルバッチインデクシング（run_indexer.bat用）
- auto_sync():   差分インデクシング（アプリ起動時用）

使用方法（バッチ）:
    python -m modules.indexer
"""
import os
import sys
import glob
import hashlib
import numpy as np
import pickle

# パス設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from modules.config import Config
from modules.logger import get_logger
from modules.image_processing import (
    pdf_to_image, pdf_to_images, pdf_page_count,
    extract_sift_features, extract_contour_features, extract_clip_embedding,
)
from modules.database import (
    init_db, upsert_drawing, batch_upsert_drawings, update_process_path,
    get_all_drawings, get_registered_paths, is_registered,
    update_attributes, update_features_flags,
)
from modules.vector_index import VectorIndex
from modules.thumbnail_cache import save_thumbnail, has_thumbnail
from modules.ocr_extractor import extract_attributes

logger = get_logger('indexer')

os.makedirs(Config.CACHE_DIR, exist_ok=True)


# ============================================================
# 共通ヘルパー
# ============================================================

def _scan_pdf_files(directory):
    """フォルダ内のPDFファイルを再帰的に検索する"""
    if not os.path.exists(directory):
        logger.warning(f"フォルダが見つかりません: {directory}")
        return []
    return glob.glob(os.path.join(directory, "**", "*.pdf"), recursive=True)


def _build_process_map():
    """工程フォルダをスキャンしてファイル名→パスのマップを作成する"""
    process_map = {}
    if os.path.exists(Config.PROCESS_DIR):
        for pf in _scan_pdf_files(Config.PROCESS_DIR):
            process_map[os.path.basename(pf)] = pf
    return process_map


def _save_feature_cache(drawing_path, features):
    """特徴量をpickleキャッシュに保存する"""
    rel_path = os.path.relpath(drawing_path, Config.DRAWING_DIR)
    cache_path = os.path.join(Config.CACHE_DIR, rel_path + ".pkl")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(features, f)


def _save_clip_vector(drawing_path, embedding, page_number=1):
    """CLIPベクトルを保存する"""
    clip_dir = os.path.join(Config.CACHE_DIR, "clip_vectors")
    os.makedirs(clip_dir, exist_ok=True)
    key = f"{drawing_path}::p{page_number}"
    h = hashlib.md5(key.encode()).hexdigest()
    np.save(os.path.join(clip_dir, f"{h}.npy"), embedding)


def _process_drawing(drawing_path, page_number, img, process_path=None):
    """1件の図面（1ページ）を処理する（特徴量抽出・サムネイル・DB更新）"""
    fname = os.path.basename(drawing_path)

    # サムネイル保存
    if not has_thumbnail(drawing_path, page_number):
        save_thumbnail(drawing_path, img, page_number)

    # SIFT + 輪郭
    sift_feat = extract_sift_features(img)
    contour_feat = extract_contour_features(img)

    features = {
        "kp": sift_feat["kp"],
        "des": sift_feat["des"],
        "hu_moments": contour_feat["hu_moments"],
        "contour_area_ratio": contour_feat["contour_area_ratio"],
        "img_shape": img.shape,
        "page_number": page_number,
    }
    _save_feature_cache(drawing_path, features)
    update_features_flags(drawing_path, page_number, has_sift=1, has_contour=1)

    # CLIP
    emb = extract_clip_embedding(img)
    if emb is not None:
        _save_clip_vector(drawing_path, emb, page_number)
        update_features_flags(drawing_path, page_number, has_clip=1)

    return True


def _rebuild_faiss_index():
    """FAISSインデックスを全件から再構築する"""
    all_drawings = get_all_drawings()
    clip_dir = os.path.join(Config.CACHE_DIR, "clip_vectors")
    vectors, paths = [], []

    for d in all_drawings:
        page = d.get("page_number", 1)
        key = f"{d['drawing_path']}::p{page}"
        h = hashlib.md5(key.encode()).hexdigest()
        vec_path = os.path.join(clip_dir, f"{h}.npy")
        if os.path.exists(vec_path):
            vectors.append(np.load(vec_path))
            paths.append(f"{d['drawing_path']}::p{page}")

    if vectors:
        vi = VectorIndex()
        vi.build_index(np.array(vectors), paths)
        vi.save()
        logger.info(f"FAISSインデックス再構築完了: {len(vectors)}件")
    else:
        logger.warning("ベクトルなし — FAISSインデックス未構築")


# ============================================================
# 自動同期（差分インデクシング）— アプリ起動時用
# ============================================================

def auto_sync():
    """起動時の差分同期処理

    Returns:
        int: 新規処理した図面数
    """
    init_db()

    # 1. フォルダスキャン
    drawing_files = _scan_pdf_files(Config.DRAWING_DIR)
    if not drawing_files:
        logger.info("図面フォルダにファイルなし")
        return 0

    # 2. 登録済みパスを一括取得（高速な差分チェック）
    registered = get_registered_paths()

    # 3. 新規ファイルを特定
    new_files = [f for f in drawing_files if f not in registered]
    if not new_files:
        logger.info("新規図面なし — スキップ")
        return 0

    logger.info(f"{len(new_files)}件の新規図面を検出")

    # 4. 工程表マップ
    process_map = _build_process_map()

    # 5. 新規ファイルのみ処理
    processed = 0
    for i, df in enumerate(new_files):
        fname = os.path.basename(df)
        ppath = process_map.get(fname)
        logger.info(f"  [{i + 1}/{len(new_files)}] {fname}")

        # 複数ページ対応
        page_count = pdf_page_count(df)
        for page in range(1, page_count + 1):
            img = pdf_to_image(df, page=page)
            if img is None:
                logger.warning(f"    p.{page} — スキップ（画像変換失敗）")
                continue

            upsert_drawing(fname, df, page_number=page, process_path=ppath)
            _process_drawing(df, page, img, ppath)

        # OCR（材質・板厚）— 1ページ目から抽出
        attrs = extract_attributes(df)
        if attrs["material"] or attrs["thickness"]:
            update_attributes(df, attrs["material"], attrs["thickness"])

        processed += 1

    # 6. FAISSインデックス再構築
    if processed > 0:
        _rebuild_faiss_index()

    logger.info(f"自動同期完了: {processed}件を処理")
    return processed


# ============================================================
# フルバッチインデクシング — run_indexer.bat 用
# ============================================================

def run_indexer():
    """メインのフルインデクサー処理"""
    print("=" * 60)
    print("  Nagase 図面インデクサー")
    print("=" * 60)

    init_db()
    logger.info("データベース初期化完了")

    # Step 1: 図面フォルダスキャン
    logger.info("[Step 1/5] 図面フォルダをスキャン中…")
    drawing_files = _scan_pdf_files(Config.DRAWING_DIR)
    logger.info(f"  → {len(drawing_files)}件の図面PDFを検出")

    # Step 2: 工程フォルダスキャン＆紐付け
    logger.info("[Step 2/5] 工程フォルダをスキャン中…")
    process_map = _build_process_map()
    logger.info(f"  → {len(process_map)}件の工程表PDFを検出")

    # DB登録
    new_count = 0
    for df in drawing_files:
        fname = os.path.basename(df)
        ppath = process_map.get(fname)
        page_count = pdf_page_count(df)

        for page in range(1, page_count + 1):
            if not is_registered(df):
                upsert_drawing(fname, df, page_number=page, process_path=ppath)
                new_count += 1
            elif ppath:
                update_process_path(df, ppath)

    logger.info(f"  → 新規 {new_count}件をDB登録")

    # Step 3: 特徴量抽出
    logger.info("[Step 3/5] 特徴量を抽出中…")
    all_drawings = get_all_drawings()

    for i, d in enumerate(all_drawings):
        drawing_path = d["drawing_path"]
        page = d.get("page_number", 1)
        fname = d["file_name"]

        if d["has_sift"] and d["has_contour"] and d["has_clip"]:
            logger.info(f"  [{i + 1}/{len(all_drawings)}] {fname} p.{page} — キャッシュ済み")
            continue

        img = pdf_to_image(drawing_path, page=page)
        if img is None:
            logger.warning(f"  [{i + 1}/{len(all_drawings)}] {fname} p.{page} — スキップ")
            continue

        _process_drawing(drawing_path, page, img)
        logger.info(f"  [{i + 1}/{len(all_drawings)}] {fname} p.{page} — 完了")

    # Step 4: OCR
    logger.info("[Step 4/5] 材質・板厚を抽出中…")
    all_drawings = get_all_drawings()
    ocr_count = 0
    processed_paths = set()
    for d in all_drawings:
        dp = d["drawing_path"]
        if dp in processed_paths:
            continue
        if d["material"] is None and d["thickness"] is None:
            attrs = extract_attributes(dp)
            if attrs["material"] or attrs["thickness"]:
                update_attributes(dp, attrs["material"], attrs["thickness"])
                ocr_count += 1
        processed_paths.add(dp)
    logger.info(f"  → {ocr_count}件の属性を新たに抽出")

    # Step 5: FAISSインデックス構築
    logger.info("[Step 5/5] FAISSインデックスを構築中…")
    _rebuild_faiss_index()

    # 完了サマリー
    all_drawings = get_all_drawings()
    linked = sum(1 for d in all_drawings if d.get("process_path"))
    with_mat = sum(1 for d in all_drawings if d.get("material"))
    logger.info(f"インデクシング完了 — 登録:{len(all_drawings)}件 工程紐付け:{linked}件 材質取得:{with_mat}件")
    print(f"\n{'=' * 60}")
    print(f"  完了 — {len(all_drawings)}件")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_indexer()
