"""
図面検索モジュール（本番対応版）
- 共通image_processingモジュール使用
- 複数ページPDF対応
- Config/Logger統合
"""
import streamlit as st
import os
import hashlib
import numpy as np
import pickle
import tempfile

from modules.config import Config
from modules.logger import get_logger
from modules.database import (
    init_db, get_all_drawings, search_by_name,
    get_drawing_by_path, get_drawing_count,
)
from modules.vector_index import VectorIndex
from modules.thumbnail_cache import get_thumbnail
from modules.ocr_extractor import extract_attributes
from modules.image_processing import (
    pdf_to_image, extract_clip_embedding,
    extract_sift_features, extract_contour_features,
)

logger = get_logger('drawing_search')


# ============================================================
# キャッシュ付きリソースロード
# ============================================================

@st.cache_resource
def load_clip_model():
    """CLIPモデルをStreamlitキャッシュ付きで読み込む"""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(Config.CLIP_MODEL_NAME)
    except Exception:
        return None


@st.cache_resource
def load_faiss_index():
    """FAISSインデックスをStreamlitキャッシュ付きで読み込む"""
    vi = VectorIndex()
    if vi.load():
        return vi
    return None


# ============================================================
# 類似度計算
# ============================================================

def calculate_contour_similarity(hu1, hu2):
    """Hu Momentsによる輪郭類似度を計算する"""
    if hu1 is None or hu2 is None:
        return 0.0
    try:
        diff = np.abs(hu1 - hu2)
        weights = [1.0, 0.8, 0.6, 0.5, 0.3, 0.2, 0.1]
        weighted_diff = sum(w * d for w, d in zip(weights, diff))
        similarity = max(0, 1.0 - weighted_diff / 15.0)
        return similarity * 100.0
    except Exception:
        return 0.0


def calculate_sift_similarity(feat1, feat2):
    """SIFT特徴量による類似度を計算する"""
    import cv2
    des1 = feat1.get("des")
    des2 = feat2.get("des")
    kp1 = feat1.get("kp", [])
    kp2 = feat2.get("kp", [])

    if des1 is None or des2 is None or len(kp1) < 5 or len(kp2) < 5:
        return 0.0

    try:
        index_params = dict(algorithm=1, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)

        good = [m for m, n in matches if m.distance < Config.SIFT_MATCH_RATIO * n.distance]

        if len(good) >= 4:
            src = np.float32([kp1[m.queryIdx][0] for m in good]).reshape(-1, 1, 2)
            dst = np.float32([kp2[m.trainIdx][0] for m in good]).reshape(-1, 1, 2)
            _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
            if mask is not None:
                inliers = np.sum(mask)
                ratio = inliers / len(good)
                return min(100.0, (inliers / 80.0) * 50 + (ratio * 50))
    except Exception as e:
        logger.warning(f"SIFT比較エラー: {e}")
    return 0.0


def calculate_clip_similarity(emb1, emb2):
    """CLIP特徴量による類似度を計算する"""
    if emb1 is None or emb2 is None:
        return 0.0
    try:
        cosine_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return max(0, (cosine_sim - 0.65) / 0.35) * 100.0
    except Exception:
        return 0.0


def calculate_final_score(contour_score, clip_score, sift_score, attr_bonus):
    """最終スコアを計算する（Configの重みを使用）"""
    return min(100.0,
               contour_score * Config.WEIGHT_CONTOUR +
               clip_score * Config.WEIGHT_CLIP +
               sift_score * Config.WEIGHT_SIFT +
               attr_bonus * Config.WEIGHT_ATTR)


# ============================================================
# キャッシュ読み込み
# ============================================================

def load_cached_features(drawing_path):
    """キャッシュから特徴量を読み込む"""
    rel_path = os.path.relpath(drawing_path, Config.DRAWING_DIR)
    cache_path = os.path.join(Config.CACHE_DIR, rel_path + ".pkl")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return None


def load_clip_vector(drawing_path, page_number=1):
    """キャッシュからCLIPベクトルを読み込む"""
    key = f"{drawing_path}::p{page_number}"
    h = hashlib.md5(key.encode()).hexdigest()
    vec_path = os.path.join(Config.CACHE_DIR, "clip_vectors", f"{h}.npy")
    if os.path.exists(vec_path):
        return np.load(vec_path)
    # フォールバック: 旧形式（page_numberなし）
    h_old = hashlib.md5(drawing_path.encode()).hexdigest()
    vec_old = os.path.join(Config.CACHE_DIR, "clip_vectors", f"{h_old}.npy")
    if os.path.exists(vec_old):
        return np.load(vec_old)
    return None


def get_display_image(drawing_path, page_number=1):
    """表示用画像を取得する"""
    thumb = get_thumbnail(drawing_path, page_number)
    if thumb is not None:
        return thumb
    return pdf_to_image(drawing_path, page=page_number)


# ============================================================
# UI レンダリング
# ============================================================

def render_drawing_search():
    init_db()

    st.markdown("""
    <div class="section-header">
        <h2>類似図面検索</h2>
    </div>
    """, unsafe_allow_html=True)

    count = get_drawing_count()
    if count == 0:
        st.warning("登録図面がありません。run_indexer.bat を実行するか、図面フォルダにPDFを追加してアプリを再起動してください。")

    st.markdown("""
    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap;">
        <span class="badge badge-primary">Step 1</span>
        <span style="color: #64748b; font-size: 0.85rem;">図面PDFをアップロード</span>
        <span style="color: #cbd5e1; margin: 0 0.25rem;">→</span>
        <span class="badge badge-info">Step 2</span>
        <span style="color: #64748b; font-size: 0.85rem;">AI解析・検索</span>
        <span style="color: #cbd5e1; margin: 0 0.25rem;">→</span>
        <span class="badge badge-success">Step 3</span>
        <span style="color: #64748b; font-size: 0.85rem;">類似図面を確認</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="upload-area">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "比較したい図面PDFをドラッグ＆ドロップ、またはクリックしてアップロード",
        type="pdf",
        help="対応形式: PDF（1ページ目を解析します）",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_file:
        tmp_path = None
        try:
            with st.spinner("図面を解析しています…"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    tmp_path = tmp.name

                target_image = pdf_to_image(tmp_path)

            if target_image is not None:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                col_preview, col_info = st.columns([1, 1])
                with col_preview:
                    st.image(target_image, caption="アップロードされた図面", width=380)
                with col_info:
                    st.markdown("#### アップロード完了")
                    st.markdown(f"""
                    <div style="margin-top: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            <span class="badge badge-primary">ファイル名</span>
                            <span style="font-size: 0.85rem; color: #1e293b;">{uploaded_file.name}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            <span class="badge badge-info">サイズ</span>
                            <span style="font-size: 0.85rem; color: #1e293b;">{uploaded_file.size / 1024:.1f} KB</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("類似図面を検索する", use_container_width=True):
                        search_and_display(target_image, tmp_path, uploaded_file.name)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.error("PDFの画像変換に失敗しました。Popplerがインストールされているか確認してください。")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


def search_and_display(target_image, target_pdf_path, uploaded_filename=""):
    st.markdown("---")
    st.markdown("""
    <div class="section-header"><h2>検索結果</h2></div>
    """, unsafe_allow_html=True)

    status = st.empty()
    status.caption("特徴量を抽出中…")

    target_clip = extract_clip_embedding(target_image)
    target_sift = extract_sift_features(target_image)
    target_contour = extract_contour_features(target_image)
    target_attrs = extract_attributes(target_pdf_path)

    status.caption("類似候補を検索中…")
    vi = load_faiss_index()

    candidates = []
    if vi and target_clip is not None:
        faiss_results = vi.search_similar(target_clip)
        for path_key, clip_sim in faiss_results:
            # path_key は "drawing_path::pN" 形式
            if "::p" in path_key:
                path, page_str = path_key.rsplit("::p", 1)
                page = int(page_str)
            else:
                path, page = path_key, 1
            candidates.append({"path": path, "page": page, "clip_raw_sim": clip_sim})
    else:
        all_drawings = get_all_drawings()
        for d in all_drawings:
            candidates.append({
                "path": d["drawing_path"],
                "page": d.get("page_number", 1),
                "clip_raw_sim": 0.0,
            })

    if not candidates:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">登録図面なし</div>
            <p style="font-size: 0.85rem;">図面フォルダにPDFを追加してアプリを再起動してください</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── 詳細比較（リランキング）──
    status.caption("詳細比較中…")
    progress_bar = st.progress(0)
    results = []

    for i, cand in enumerate(candidates):
        progress_bar.progress((i + 1) / len(candidates))
        drawing_path = cand["path"]
        page = cand["page"]

        cached = load_cached_features(drawing_path)
        if cached is None:
            continue

        db_info = get_drawing_by_path(drawing_path, page)

        ref_clip = load_clip_vector(drawing_path, page)
        clip_score = calculate_clip_similarity(target_clip, ref_clip)
        sift_score = calculate_sift_similarity(target_sift, cached)

        ref_hu = cached.get("hu_moments")
        contour_score = calculate_contour_similarity(target_contour["hu_moments"], ref_hu)

        attr_bonus = 0.0
        ref_mat = db_info.get("material") if db_info else cached.get("attrs", {}).get("material")
        ref_thick = db_info.get("thickness") if db_info else cached.get("attrs", {}).get("thickness")
        if target_attrs["material"] and ref_mat and target_attrs["material"] == ref_mat:
            attr_bonus += 50.0
        if target_attrs["thickness"] and ref_thick and target_attrs["thickness"] == ref_thick:
            attr_bonus += 50.0

        final_score = calculate_final_score(contour_score, clip_score, sift_score, attr_bonus)

        # 完全一致検出: アップロードファイルと同じファイル名なら100%
        if uploaded_filename and os.path.basename(drawing_path) == uploaded_filename:
            final_score = 100.0

        results.append({
            "path": drawing_path,
            "page": page,
            "score": final_score,
            "name": os.path.basename(drawing_path),
            "material": ref_mat or "不明",
            "thickness": ref_thick or "不明",
            "process_path": db_info.get("process_path") if db_info else None,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    progress_bar.empty()
    status.empty()

    # ── サマリーメトリクス ──
    top_results = results[:Config.DISPLAY_TOP_K]
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value">{len(results)}</div>
            <div class="metric-label">検索対象図面</div>
        </div>""", unsafe_allow_html=True)
    with col_m2:
        high_match = len([r for r in results if r["score"] > 60])
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value">{high_match}</div>
            <div class="metric-label">類似度60%以上</div>
        </div>""", unsafe_allow_html=True)
    with col_m3:
        best_score = results[0]["score"] if results else 0
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value">{best_score:.1f}%</div>
            <div class="metric-label">最高類似度</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # ── 結果カード ──
    for rank, res in enumerate(top_results):
        _render_result_card(rank, res)


def _render_result_card(rank, res):
    """検索結果1件を描画する"""
    if rank == 0:
        rank_class, card_class = "gold", "rank-1"
    elif rank == 1:
        rank_class, card_class = "silver", "rank-2"
    elif rank == 2:
        rank_class, card_class = "bronze", "rank-3"
    else:
        rank_class, card_class = "default", ""

    score = res["score"]
    bar_class = "high" if score > 80 else "medium" if score > 60 else "low" if score > 40 else "very-low"
    page = res.get("page", 1)
    page_label = f" (p.{page})" if page > 1 else ""

    with st.container(border=True):
        col1, col2 = st.columns([2, 3])

        with col1:
            display_img = get_display_image(res["path"], page)
            if display_img is not None:
                st.image(display_img, caption=f"No.{rank + 1}{page_label}", use_container_width=True)

        with col2:
            sc = '#16a34a' if score > 80 else '#2563eb' if score > 60 else '#d97706' if score > 40 else '#64748b'
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <span class="rank-badge {rank_class}">{rank + 1}</span>
                <div>
                    <div style="font-size: 1.1rem; font-weight: 600; color: #1e293b;">{res['name']}{page_label}</div>
                    <div style="font-size: 0.8rem; color: #64748b;">類似度スコア</div>
                </div>
                <div style="margin-left: auto; text-align: right;">
                    <div style="font-size: 1.5rem; font-weight: 700; color: {sc};">{score:.1f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="similarity-bar-container">
                <div class="similarity-bar {bar_class}" style="width: {score}%;"></div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div style="display: flex; gap: 0.5rem; margin: 0.75rem 0; flex-wrap: wrap;">
                <span class="badge badge-primary">材質: {res['material']}</span>
                <span class="badge badge-info">板厚: {res['thickness']}</span>
            </div>
            """, unsafe_allow_html=True)

            if score > 95:
                st.success("線描写がほぼ完全に一致しています")
            elif score > 80:
                st.success("形状が非常に似ています")
            elif score > 60:
                st.info("形状が似ています")
            else:
                st.caption("参考図面")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if os.path.exists(res["path"]):
                    with open(res["path"], "rb") as f:
                        st.download_button("図面をダウンロード", f,
                                           file_name=res['name'], key=f"dr_dl_{rank}",
                                           use_container_width=True)
            with col_btn2:
                if res["process_path"] and os.path.exists(res["process_path"]):
                    with open(res["process_path"], "rb") as f:
                        st.download_button("工程表をダウンロード", f,
                                           file_name=os.path.basename(res["process_path"]),
                                           key=f"dl_{rank}",
                                           use_container_width=True)
                else:
                    st.caption("工程表なし")




# ============================================================
# 図番・ファイル名検索
# ============================================================

def render_drawing_list_search():
    st.markdown("---")
    st.markdown("""
    <div class="section-header"><h2>図番・ファイル名で検索</h2></div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    search_query = st.text_input(
        "図番またはファイル名を入力",
        placeholder="例: A-123, SUS304...",
        help="ファイル名の一部でも検索できます",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if not search_query:
        return

    matched = search_by_name(search_query)

    if matched:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 0.5rem; margin: 1rem 0;">
            <span class="badge badge-success">{len(matched)} 件</span>
            <span style="color: #64748b; font-size: 0.9rem;">「{search_query}」に一致する図面</span>
        </div>
        """, unsafe_allow_html=True)

        for i, d in enumerate(matched):
            file_name = d["file_name"]
            drawing_path = d["drawing_path"]
            process_path = d.get("process_path")
            page = d.get("page_number", 1)
            page_label = f" (p.{page})" if page > 1 else ""

            st.markdown('<div class="result-card">', unsafe_allow_html=True)
            col1, col2 = st.columns([1, 2])

            with col1:
                display_img = get_display_image(drawing_path, page)
                if display_img is not None:
                    st.image(display_img, width=220)

            with col2:
                st.markdown(f"""
                <div style="margin-bottom: 0.5rem;">
                    <div style="font-size: 1rem; font-weight: 600;">{file_name}{page_label}</div>
                </div>
                """, unsafe_allow_html=True)

                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    if os.path.exists(drawing_path):
                        with open(drawing_path, "rb") as f:
                            st.download_button("図面をダウンロード", f,
                                               file_name=file_name,
                                               key=f"q_drawing_dl_{i}",
                                               use_container_width=True)
                with col_dl2:
                    if process_path and os.path.exists(process_path):
                        with open(process_path, "rb") as f:
                            st.download_button("工程表をダウンロード", f,
                                               file_name=os.path.basename(process_path),
                                               key=f"q_dl_{i}",
                                               use_container_width=True)
                    else:
                        st.caption("工程表なし")

            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="empty-state">
            <div class="empty-state-icon">該当なし</div>
            <p>「{search_query}」に一致する図面は見つかりませんでした</p>
            <p style="font-size: 0.8rem; color: #94a3b8;">キーワードを変えてお試しください</p>
        </div>
        """, unsafe_allow_html=True)
