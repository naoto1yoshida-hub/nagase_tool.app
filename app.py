import streamlit as st
import os
from PIL import Image

from modules.config import Config
from modules.logger import get_logger

logger = get_logger('app')

# ページ設定
_LOGO_PATH = os.path.join(Config.APP_DIR, "assets", "logo.png")
_logo_icon = Image.open(_LOGO_PATH) if os.path.exists(_LOGO_PATH) else "N"
st.set_page_config(
    page_title="Nagase 図面検索ツール",
    page_icon=_logo_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========================================
# カスタムCSS（ホワイトベース＋ブルーアクセント）
# ========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;600;700&display=swap');
    :root {
        --primary: #2563eb; --primary-light: #3b82f6; --primary-lighter: #93c5fd;
        --primary-lightest: #dbeafe; --primary-dark: #1d4ed8; --accent: #0ea5e9;
        --bg-main: #f8fafc; --bg-card: #ffffff;
        --bg-sidebar: linear-gradient(180deg, #1e3a5f 0%, #1e40af 100%);
        --text-primary: #1e293b; --text-secondary: #64748b; --text-muted: #94a3b8;
        --border: #e2e8f0; --border-light: #f1f5f9;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.04);
        --shadow-lg: 0 10px 30px rgba(0,0,0,0.08), 0 4px 8px rgba(0,0,0,0.04);
        --radius: 12px; --radius-sm: 8px;
        --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stApp { font-family: 'Noto Sans JP', -apple-system, sans-serif !important;
        background-color: var(--bg-main) !important; color: var(--text-primary) !important; }
    .main .block-container { padding: 2rem 3rem !important; max-width: 1200px !important; }
    @keyframes fadeInUp { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
    @keyframes fadeIn { from{opacity:0} to{opacity:1} }
    section[data-testid="stSidebar"] { background: var(--bg-sidebar) !important;
        border-right: none !important; box-shadow: 4px 0 20px rgba(0,0,0,0.08) !important; }
    section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 { color: #ffffff !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }
    section[data-testid="stSidebar"] [data-testid="stAlert"] {
        background: rgba(255,255,255,0.1) !important; border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: var(--radius-sm) !important; backdrop-filter: blur(8px) !important; }
    .stMarkdown h1 { color: var(--text-primary) !important; font-weight: 700 !important; }
    .stMarkdown h2 { color: var(--text-primary) !important; font-weight: 600 !important; }
    .stMarkdown h3 { color: var(--primary) !important; font-weight: 600 !important; }
    .hero-section { background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 50%, #38bdf8 100%);
        border-radius: 16px; padding: 2.5rem; margin-bottom: 2rem; color: white;
        position: relative; overflow: hidden; box-shadow: 0 8px 32px rgba(37,99,235,0.2);
        animation: fadeInUp 0.6s ease-out; }
    .hero-section::before { content:''; position:absolute; top:-50%; right:-20%; width:400px;
        height:400px; background:radial-gradient(circle,rgba(255,255,255,0.12) 0%,transparent 70%);
        border-radius:50%; }
    .hero-title { font-size:1.75rem; font-weight:700; margin:0 0 0.5rem 0;
        position:relative; z-index:1; }
    .hero-subtitle { font-size:0.95rem; opacity:0.9; margin:0; font-weight:300;
        position:relative; z-index:1; line-height:1.6; }
    .card { background:var(--bg-card); border:1px solid var(--border); border-radius:var(--radius);
        padding:1.5rem; margin-bottom:1rem; box-shadow:var(--shadow-sm);
        transition:var(--transition); animation:fadeInUp 0.5s ease-out; }
    .card:hover { box-shadow:var(--shadow-md); border-color:var(--primary-lighter); transform:translateY(-2px); }
    .upload-area { background:linear-gradient(135deg,var(--primary-lightest) 0%,#f0f7ff 100%);
        border:2px dashed var(--primary-lighter); border-radius:var(--radius);
        padding:2rem; text-align:center; transition:var(--transition); margin-bottom:1.5rem; }
    .upload-area:hover { border-color:var(--primary); }
    [data-testid="stFileUploader"] { animation:fadeIn 0.4s ease-out; }
    [data-testid="stFileUploader"] > div { padding:0 !important; }
    .stButton > button { background:linear-gradient(135deg,var(--primary) 0%,var(--primary-light) 100%) !important;
        color:white !important; border:none !important; border-radius:var(--radius-sm) !important;
        padding:0.6rem 1.5rem !important; font-weight:600 !important; font-size:0.9rem !important;
        transition:var(--transition) !important; box-shadow:0 2px 8px rgba(37,99,235,0.25) !important;
        font-family:'Noto Sans JP',sans-serif !important; width:100%; }
    .stButton > button:hover { background:linear-gradient(135deg,var(--primary-dark) 0%,var(--primary) 100%) !important;
        box-shadow:0 4px 16px rgba(37,99,235,0.35) !important; transform:translateY(-1px) !important; }
    .stDownloadButton > button { background:var(--bg-card) !important; color:var(--primary) !important;
        border:1.5px solid var(--primary-lighter) !important; border-radius:var(--radius-sm) !important;
        font-weight:500 !important; font-size:0.82rem !important; box-shadow:none !important; }
    .stDownloadButton > button:hover { background:var(--primary-lightest) !important;
        border-color:var(--primary) !important; }
    .stProgress > div > div > div { background:linear-gradient(90deg,var(--primary) 0%,var(--accent) 100%) !important;
        border-radius:8px !important; }
    .stTextInput > div > div > input { border:1.5px solid var(--border) !important;
        border-radius:var(--radius-sm) !important; padding:0.65rem 1rem !important;
        font-family:'Noto Sans JP',sans-serif !important; background:var(--bg-card) !important; }
    .stTextInput > div > div > input:focus { border-color:var(--primary) !important;
        box-shadow:0 0 0 3px rgba(37,99,235,0.1) !important; }
    .result-card { background:var(--bg-card); border:1px solid var(--border); border-radius:var(--radius);
        padding:1.25rem 1.5rem; margin:0.8rem 0; box-shadow:var(--shadow-sm);
        transition:var(--transition); animation:fadeInUp 0.4s ease-out; position:relative; overflow:hidden; }
    .result-card:hover { box-shadow:var(--shadow-md); border-color:var(--primary-lighter); }
    .result-card.rank-1 { border-left:4px solid #f59e0b; background:linear-gradient(90deg,#fffbeb 0%,var(--bg-card) 8%); }
    .result-card.rank-2 { border-left:4px solid #94a3b8; background:linear-gradient(90deg,#f8fafc 0%,var(--bg-card) 8%); }
    .result-card.rank-3 { border-left:4px solid #d97706; background:linear-gradient(90deg,#fffbeb 0%,var(--bg-card) 8%); }
    .badge { display:inline-block; padding:0.2rem 0.7rem; border-radius:50px; font-size:0.75rem; font-weight:600; }
    .badge-primary { background:var(--primary-lightest); color:var(--primary); }
    .badge-success { background:#dcfce7; color:#16a34a; }
    .badge-warning { background:#fef3c7; color:#d97706; }
    .badge-info { background:#e0f2fe; color:#0284c7; }
    .similarity-bar-container { background:var(--border-light); border-radius:20px; height:10px;
        width:100%; overflow:hidden; margin:0.3rem 0; }
    .similarity-bar { height:100%; border-radius:20px; transition:width 1s ease-out; }
    .similarity-bar.high { background:linear-gradient(90deg,#22c55e,#16a34a); }
    .similarity-bar.medium { background:linear-gradient(90deg,#3b82f6,#2563eb); }
    .similarity-bar.low { background:linear-gradient(90deg,#f59e0b,#d97706); }
    .similarity-bar.very-low { background:linear-gradient(90deg,#94a3b8,#64748b); }
    .rank-badge { display:inline-flex; align-items:center; justify-content:center;
        width:36px; height:36px; border-radius:50%; font-weight:700; font-size:0.9rem; margin-right:0.75rem; }
    .rank-badge.gold { background:linear-gradient(135deg,#fbbf24,#f59e0b); color:white;
        box-shadow:0 2px 8px rgba(245,158,11,0.3); }
    .rank-badge.silver { background:linear-gradient(135deg,#cbd5e1,#94a3b8); color:white; }
    .rank-badge.bronze { background:linear-gradient(135deg,#fdba74,#f97316); color:white; }
    .rank-badge.default { background:linear-gradient(135deg,#e2e8f0,#cbd5e1); color:var(--text-secondary); }
    .section-header { display:flex; align-items:center; gap:0.6rem; margin-bottom:1rem;
        padding-bottom:0.75rem; border-bottom:2px solid var(--primary-lightest); }
    .section-header h2 { margin:0; font-size:1.3rem; font-weight:600; }
    .metric-box { background:var(--bg-card); border:1px solid var(--border); border-radius:var(--radius-sm);
        padding:1rem 1.2rem; text-align:center; box-shadow:var(--shadow-sm); }
    .metric-value { font-size:1.8rem; font-weight:700; color:var(--primary); line-height:1.2; }
    .metric-label { font-size:0.8rem; color:var(--text-secondary); margin-top:0.25rem; }
    .empty-state { text-align:center; padding:3rem 2rem; color:var(--text-muted); }
    .empty-state-icon { font-size:1.2rem; font-weight:500; color:var(--text-secondary); margin-bottom:0.75rem; }
    .sidebar-brand { text-align:center; padding:0.5rem 1rem 1rem; }
    .sidebar-brand-title { font-size:1.2rem; font-weight:700; color:white !important; margin:0; }
    .sidebar-brand-sub { font-size:0.72rem; color:rgba(255,255,255,0.55) !important; margin:0.25rem 0 0; font-weight:300; }
    .sidebar-nav-item { display:flex; align-items:center; gap:0.6rem; padding:0.5rem 0.75rem;
        border-radius:var(--radius-sm); background:rgba(255,255,255,0.1); margin:0.3rem 0; font-size:0.85rem; }
    .sidebar-footer { padding:1rem; border-top:1px solid rgba(255,255,255,0.1);
        text-align:center; font-size:0.7rem; color:rgba(255,255,255,0.4) !important; }
    .health-ok { color: #22c55e !important; }
    .health-ng { color: #ef4444 !important; }
</style>
""", unsafe_allow_html=True)

# ========================================
# 起動時自動同期（差分インデクシング）
# ========================================
if "auto_sync_done" not in st.session_state:
    from modules.indexer import auto_sync
    with st.spinner("新規図面をチェック中…"):
        try:
            new_count = auto_sync()
            if new_count > 0:
                st.toast(f"✅ {new_count}件の新規図面を自動登録しました")
                # FAISSキャッシュをクリア（新しいインデックスを読み込むため）
                from modules.drawing_search import load_faiss_index
                load_faiss_index.clear()
                logger.info(f"起動時自動同期: {new_count}件を処理")
        except Exception as e:
            logger.error(f"自動同期エラー: {e}", exc_info=True)
    st.session_state["auto_sync_done"] = True

# ========================================
# サイドバー
# ========================================
with st.sidebar:
    if os.path.exists(_LOGO_PATH):
        st.image(_LOGO_PATH, width=100)
    st.markdown("""
    <div class="sidebar-brand">
        <div class="sidebar-brand-title">Nagase Tool</div>
        <div class="sidebar-brand-sub">Drawing Search Platform</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("""
    <div class="sidebar-nav-item">類似図面検索</div>
    <div class="sidebar-nav-item">図番・ファイル名検索</div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("#### ご利用方法")
    st.info("図面PDFをアップロードすると、登録済みの図面から形状が似ているものを自動検索します。")

    st.markdown("""
    <div style="margin-top: 0.5rem;">
        <div class="sidebar-nav-item">対応形式 ― PDF</div>
        <div class="sidebar-nav-item">AI ― CLIP + SIFT</div>
    </div>
    """, unsafe_allow_html=True)

    # ヘルスチェック表示
    st.divider()
    st.markdown("#### システム状態")
    from modules.health_check import run_all_checks
    checks = run_all_checks()
    for key, info in checks.items():
        icon = "✅" if info['ok'] else "❌"
        st.markdown(f"{icon} {info['name']}")

    # フッター
    st.markdown("---")
    st.markdown("""
    <div class="sidebar-footer">
        Nagase Tool v3.0<br>
        Powered by AI Vision
    </div>
    """, unsafe_allow_html=True)

# ========================================
# ヒーローセクション
# ========================================
st.markdown("""
<div class="hero-section">
    <div class="hero-title">Nagase 図面検索ツール</div>
    <div class="hero-subtitle">
        図面PDFをアップロードして、過去の類似図面（形状・材質・寸法）をAIで高速検索。<br>
        SIFT特徴量 + CLIP AIモデルによるハイブリッド検索で高精度な結果をお届けします。
    </div>
</div>
""", unsafe_allow_html=True)

# ========================================
# メインコンテンツ
# ========================================
from modules.drawing_search import render_drawing_search, render_drawing_list_search
render_drawing_search()
render_drawing_list_search()
