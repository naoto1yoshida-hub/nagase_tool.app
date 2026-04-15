"""
OCR材質・板厚抽出モジュール
CAD出力PDFはPyMuPDFでテキスト抽出、スキャンPDFはTesseract OCRにフォールバック
"""
import re
import fitz  # PyMuPDF

from modules.logger import get_logger

logger = get_logger('ocr_extractor')

# Tesseractの遅延インポート
_tesseract_available = None


def _check_tesseract():
    """Tesseractが利用可能か確認する"""
    global _tesseract_available
    if _tesseract_available is None:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            _tesseract_available = True
        except Exception:
            _tesseract_available = False
            logger.info("Tesseract未検出 — OCRフォールバック無効")
    return _tesseract_available


# ── 材質パターン ──
MATERIAL_PATTERNS = [
    r"SUS\s*\d{3}[A-Z]*",
    r"SS\s*400",
    r"S\d{2}C",
    r"S[KS]?\d{2,3}C?",
    r"SPCC", r"SPHC", r"SPCD", r"SPCE",
    r"SGCC", r"SECC", r"SGHC",
    r"A\d{4}[A-Z]?(?:\s*-\s*[A-Z]\d*)?",
    r"C\d{4}[A-Z]?",
]

# ── 板厚パターン ──
THICKNESS_PATTERNS = [
    r"[tT]\s*[=＝]?\s*(\d+\.?\d*)",
    r"(\d+\.?\d*)\s*[tT](?:\s|$|[,、])",
    r"板厚\s*[：:=＝]?\s*(\d+\.?\d*)",
    r"(?:厚さ|厚)\s*[：:=＝]?\s*(\d+\.?\d*)",
]


def extract_text_from_pdf(pdf_path):
    """PDFからテキストを抽出する"""
    text = ""

    # Step 1: PyMuPDF（CAD出力PDF向け）
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        logger.warning(f"PyMuPDFテキスト抽出エラー ({pdf_path}): {e}")

    clean_text = re.sub(r"\s+", "", text)
    if len(clean_text) > 50:
        return text

    # Step 2: Tesseract OCR（スキャンPDF向け）
    if not _check_tesseract():
        return text

    try:
        import pytesseract
        from PIL import Image
        import pdf2image

        images = pdf2image.convert_from_path(pdf_path, first_page=1, last_page=1, dpi=300)
        if images:
            ocr_text = pytesseract.image_to_string(images[0], lang="jpn+eng")
            if ocr_text:
                text = ocr_text
    except Exception as e:
        logger.warning(f"Tesseract OCRエラー ({pdf_path}): {e}")

    return text


def extract_material(text):
    """テキストから材質を抽出する"""
    if not text:
        return None
    for pattern in MATERIAL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).upper().replace(" ", "")
    return None


def extract_thickness(text):
    """テキストから板厚を抽出する"""
    if not text:
        return None
    for pattern in THICKNESS_PATTERNS:
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            try:
                num = float(value)
                if 0.1 <= num <= 100:
                    return value
            except ValueError:
                continue
    return None


def extract_attributes(pdf_path):
    """PDFから材質・板厚を抽出する（メイン関数）"""
    text = extract_text_from_pdf(pdf_path)
    result = {
        "material": extract_material(text),
        "thickness": extract_thickness(text),
    }
    if result["material"] or result["thickness"]:
        logger.debug(f"属性抽出: {pdf_path} → 材質:{result['material']} 板厚:{result['thickness']}")
    return result
