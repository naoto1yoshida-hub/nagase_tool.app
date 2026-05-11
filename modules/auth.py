"""
パスワードゲート（共有パスワード方式）

要件:
- アプリ起動時にパスワードを要求し、正解までは本体を一切表示しない
- 正解後はセッション中再入力不要（st.session_state で保持）
- パスワードは .env (APP_PASSWORD) または .streamlit/secrets.toml から取得
- タイミング攻撃対策として hmac.compare_digest を使用
- 未設定時は明確なエラーで停止
"""

from __future__ import annotations

import hmac
import os

import streamlit as st


_PASSWORD_ENV_KEY = "APP_PASSWORD"
_SESSION_FLAG = "password_correct"
_INPUT_KEY = "__password_input"


def _load_expected_password() -> str | None:
    """期待値となる共有パスワードを取得する。

    優先順位:
    1. 環境変数 / .env (APP_PASSWORD)
    2. .streamlit/secrets.toml の APP_PASSWORD

    どちらにも存在しない／空文字の場合は None を返す。
    """
    # 1) 環境変数 / .env (modules.config 経由で読み込み済み想定)
    env_val = os.environ.get(_PASSWORD_ENV_KEY)
    if env_val:
        return env_val

    # 2) Streamlit secrets（存在しない場合の例外を握りつぶす）
    try:
        secret_val = st.secrets.get(_PASSWORD_ENV_KEY)  # type: ignore[attr-defined]
        if secret_val:
            return str(secret_val)
    except (FileNotFoundError, KeyError, AttributeError):
        # secrets.toml が無いケースは正常系として扱う
        pass
    except Exception:
        # 想定外の secrets 読み込みエラーは黙殺し、未設定として扱う
        pass

    return None


def _render_login_form(expected: str) -> None:
    """ログインフォームを描画し、入力検証を行う。"""
    st.markdown(
        """
        <div style="max-width: 420px; margin: 4rem auto 1rem;">
            <h2 style="margin-bottom: 0.25rem;">Nagase Tool</h2>
            <p style="color:#64748b; margin: 0 0 1.5rem;">
                ご利用にはパスワードが必要です。社内で共有されたパスワードを入力してください。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("password_gate_form", clear_on_submit=False):
        entered = st.text_input(
            "パスワード",
            type="password",
            key=_INPUT_KEY,
            placeholder="共有パスワードを入力",
        )
        submitted = st.form_submit_button("ログイン")

    if submitted:
        # タイミング攻撃対策: 文字列比較は hmac.compare_digest を使う
        if hmac.compare_digest(entered or "", expected):
            st.session_state[_SESSION_FLAG] = True
            # 入力値をセッションに残さない
            if _INPUT_KEY in st.session_state:
                del st.session_state[_INPUT_KEY]
            st.rerun()
        else:
            st.error("Incorrect password")


def check_password() -> bool:
    """パスワード検証を行うエントリポイント。

    戻り値:
        True  : 認証済み（呼び出し元は処理を継続してよい）
        False : 未認証（このとき内部で st.stop() を呼ぶため、呼び出し元には返らない）

    呼び出し例:
        from modules.auth import check_password
        check_password()  # 通過するまで以降の本体は実行されない
    """
    # すでに認証済みならスキップ
    if st.session_state.get(_SESSION_FLAG) is True:
        return True

    expected = _load_expected_password()
    if not expected:
        st.error(
            "APP_PASSWORD が設定されていません。\n\n"
            "プロジェクトルートの `.env` または `.streamlit/secrets.toml` に "
            "`APP_PASSWORD` を設定してから再起動してください。"
        )
        st.stop()

    _render_login_form(expected)

    # 認証が通っていなければここで停止し、本体を描画させない
    if not st.session_state.get(_SESSION_FLAG):
        st.stop()

    return True
