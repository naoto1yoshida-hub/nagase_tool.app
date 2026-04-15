"""
画像処理モジュール（共通）
PDF変換、前処理、特徴量抽出を一元管理する
drawing_search.py と indexer.py の重複を解消
"""
import cv2
import numpy as np
import pdf2image
from PIL import Image

from modules.config import Config
from modules.logger import get_logger

logger = get_logger('image_processing')

# CLIPモデル（遅延ロード・シングルトン）
_clip_model = None


def get_clip_model():
    """CLIPモデルをロードする"""
    global _clip_model
    if _clip_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"CLIPモデル ({Config.CLIP_MODEL_NAME}) を読み込み中…")
            _clip_model = SentenceTransformer(Config.CLIP_MODEL_NAME)
            logger.info("CLIPモデル読み込み完了")
        except Exception as e:
            logger.error(f"CLIPモデル読み込み失敗: {e}", exc_info=True)
            return None
    return _clip_model


# ============================================================
# PDF → 画像変換
# ============================================================

def pdf_page_count(pdf_path):
    """PDFのページ数を取得する"""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception as e:
        logger.warning(f"ページ数取得失敗 ({pdf_path}): {e}")
        return 1


def pdf_to_image(pdf_path, page=1):
    """PDFの指定ページを画像に変換し、余白除去して返す"""
    try:
        images = pdf2image.convert_from_path(pdf_path, first_page=page, last_page=page)
        if images:
            img = np.array(images[0])
            return crop_drawing(img)
    except Exception as e:
        logger.error(f"PDF変換エラー ({pdf_path}, p.{page}): {e}")
    return None


def pdf_to_images(pdf_path):
    """PDFの全ページを画像に変換する

    Returns:
        list of (page_number, image_array)
    """
    results = []
    count = pdf_page_count(pdf_path)
    for page in range(1, count + 1):
        img = pdf_to_image(pdf_path, page=page)
        if img is not None:
            results.append((page, img))
    return results


# ============================================================
# 画像前処理
# ============================================================

def crop_drawing(img):
    """画像から余白を精密に除去して図面本体を抽出する"""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2,
        )
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            main = [c for c in contours if cv2.contourArea(c) > 100] or contours
            x, y, w, h = cv2.boundingRect(np.concatenate(main))
            mx, my = int(w * 0.02), int(h * 0.02)
            x, y = max(0, x - mx), max(0, y - my)
            w = min(img.shape[1] - x, w + 2 * mx)
            h = min(img.shape[0] - y, h + 2 * my)
            return img[y:y + h, x:x + w]
    except Exception as e:
        logger.warning(f"余白除去エラー: {e}")
    return img


def preprocess_image(img):
    """図面の線描写を際立たせるための前処理（スケルトン化）"""
    if img is None:
        return None
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2,
        )
        kernel = np.ones((2, 2), np.uint8)
        opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        skeleton = np.zeros(opening.shape, np.uint8)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        temp_img = opening.copy()
        size = np.size(opening)

        while True:
            eroded = cv2.erode(temp_img, element)
            temp = cv2.dilate(eroded, element)
            temp = cv2.subtract(temp_img, temp)
            skeleton = cv2.bitwise_or(skeleton, temp)
            temp_img = eroded.copy()
            if size - cv2.countNonZero(temp_img) == size:
                break
        return skeleton
    except Exception as e:
        logger.warning(f"前処理エラー: {e}")
        return img


# ============================================================
# 特徴量抽出
# ============================================================

def extract_sift_features(img):
    """SIFT特徴量を抽出する"""
    try:
        skeleton = preprocess_image(img)
        sift = cv2.SIFT_create()
        kp, des = sift.detectAndCompute(skeleton, None)
        kp_data = []
        if kp:
            for p in kp:
                kp_data.append((p.pt, p.size, p.angle, p.response, p.octave, p.class_id))
        return {"kp": kp_data, "des": des}
    except Exception as e:
        logger.error(f"SIFT抽出エラー: {e}")
        return {"kp": [], "des": None}


def extract_contour_features(img):
    """輪郭（Hu Moments）特徴量を抽出する"""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2,
        )
        kernel = np.ones((2, 2), np.uint8)
        clean = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return {"hu_moments": np.zeros(7), "contour_area_ratio": 0.0}

        largest = max(contours, key=cv2.contourArea)
        moments = cv2.moments(largest)
        hu = cv2.HuMoments(moments).flatten()
        hu = -np.sign(hu) * np.log10(np.abs(hu) + 1e-10)

        total_area = sum(cv2.contourArea(c) for c in contours)
        img_area = gray.shape[0] * gray.shape[1]
        area_ratio = total_area / img_area if img_area > 0 else 0
        return {"hu_moments": hu, "contour_area_ratio": area_ratio}
    except Exception as e:
        logger.error(f"輪郭特徴量抽出エラー: {e}")
        return {"hu_moments": np.zeros(7), "contour_area_ratio": 0.0}


def extract_clip_embedding(img):
    """CLIP特徴量を抽出する"""
    model = get_clip_model()
    if model is None:
        return None
    try:
        img_pil = Image.fromarray(img)
        return model.encode(img_pil)
    except Exception as e:
        logger.error(f"CLIP特徴量抽出エラー: {e}")
        return None
