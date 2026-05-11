"""
Tesseract のコマンドパスを自動解決する。

順序:
1. システム PATH に `tesseract` があればそれを使う（何もしない）
2. 環境変数 TESSERACT_CMD が指す実ファイルがあればそれを使う
3. Windows の標準インストール先を順番に探索

このモジュールは pytesseract を実際に呼ぶ箇所より前に `configure()` を実行する。
"""
import os
import shutil


_configured = False


def configure() -> None:
    """pytesseract.pytesseract.tesseract_cmd を必要に応じて設定する。"""
    global _configured
    if _configured:
        return
    _configured = True

    if shutil.which("tesseract"):
        return

    candidates = []
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd:
        candidates.append(env_cmd)
    candidates.extend([
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ])

    for path in candidates:
        if path and os.path.exists(path):
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = path
            except ImportError:
                pass
            return
