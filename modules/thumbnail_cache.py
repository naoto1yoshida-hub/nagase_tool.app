"""
サムネイルキャッシュモジュール
PDF図面のサムネイル画像をJPEG形式でキャッシュ管理する
"""
import os
import hashlib
import cv2
import numpy as np
from PIL import Image

from modules.config import Config
from modules.logger import get_logger

logger = get_logger('thumbnail_cache')

CACHE_DIR = os.path.join(Config.CACHE_DIR, "thumbnails")
os.makedirs(CACHE_DIR, exist_ok=True)


def _get_cache_path(drawing_path, page_number=1):
    """図面パス+ページ番号からキャッシュファイルパスを生成する"""
    key = f"{drawing_path}::p{page_number}"
    path_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{path_hash}.jpg")


def has_thumbnail(drawing_path, page_number=1):
    """サムネイルがキャッシュ済みか確認する"""
    return os.path.exists(_get_cache_path(drawing_path, page_number))


def save_thumbnail(drawing_path, image_array, page_number=1):
    """サムネイルをキャッシュに保存する"""
    if image_array is None:
        return

    cache_path = _get_cache_path(drawing_path, page_number)

    h, w = image_array.shape[:2]
    if w > Config.THUMB_MAX_WIDTH:
        scale = Config.THUMB_MAX_WIDTH / w
        new_w = Config.THUMB_MAX_WIDTH
        new_h = int(h * scale)
        image_array = cv2.resize(image_array, (new_w, new_h), interpolation=cv2.INTER_AREA)

    if len(image_array.shape) == 3 and image_array.shape[2] == 3:
        bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
    else:
        bgr = image_array

    cv2.imwrite(cache_path, bgr, [cv2.IMWRITE_JPEG_QUALITY, Config.THUMB_QUALITY])


def get_thumbnail(drawing_path, page_number=1):
    """サムネイルをキャッシュから取得する（numpy RGB）"""
    cache_path = _get_cache_path(drawing_path, page_number)
    if not os.path.exists(cache_path):
        return None
    bgr = cv2.imread(cache_path)
    if bgr is None:
        return None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def get_thumbnail_pil(drawing_path, page_number=1):
    """サムネイルをPIL Imageで取得する"""
    cache_path = _get_cache_path(drawing_path, page_number)
    if not os.path.exists(cache_path):
        return None
    try:
        return Image.open(cache_path)
    except Exception:
        return None


def clear_cache():
    """サムネイルキャッシュを全削除する"""
    import shutil
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
    logger.info("サムネイルキャッシュをクリア")
