import streamlit as st
import os
import openai
import tempfile
from datetime import datetime

# プロンプト定義
SYSTEM_PROMPT = """
あなたは優秀な会議の書記です。提供された会議の文字起こしテキストをもとに、以下のフォーマットで議事録を作成してください。
話されている内容を詳細に分析し、漏れがないようにしてください。

# フォーマット
## 1. 会議概要
- 日時: {date} (推定)
- 参加者: (テキストから推測できれば記述、不明なら省略)

## 2. 決定事項
- (決定されたことを箇条書きで)

## 3. ToDo (アクションアイテム)
- [ ] 担当: (人名) / 期限: (日付) / 内容: (詳細)

## 4. 未決定事項・論点
- (決まらなかったこと、議論が割れたポイント)

## 5. 次回アジェンダ
- (次回話すべきこと)

## 6. 詳細要約 (話題別)
### [話題1のタイトル]
(内容の詳細要約。3-7行程度で具体的かつ詳細に記述)
### [話題2のタイトル]
(内容の詳細要約)
...
"""

def transcribe_audio(audio_file_path):
    """OpenAI Whisper APIを使って音声をテキスト化する(分割対応)"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        st.error("OpenAI API Keyが設定されていません。サイドバーから設定してください。")
        return None

    client = openai.OpenAI(api_key=api_key)

    try:
        from pydub import AudioSegment
        import math
        
        st.info("💡 約30分ごとに音声を分割して処理します...")
        audio = AudioSegment.from_file(audio_file_path)
        
        chunk_length_ms = 30 * 60 * 1000  # 30分
        chunks = [audio[i:i+chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        
        full_transcript = ""
        my_bar = st.progress(0, text="文字起こし準備中...")
        
        for i, chunk in enumerate(chunks):
            # 一時ファイルにチャンクを書き出す
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as chunk_file:
                chunk.export(chunk_file.name, format="mp3")
                chunk_path = chunk_file.name
                
            with open(chunk_path, "rb") as f:
                transcript_chunk = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=f,
                    response_format="text"
                )
                full_transcript += transcript_chunk + "\n"
                
            os.unlink(chunk_path)
            my_bar.progress((i + 1) / len(chunks), text=f"文字起こし進行中... ({i+1}/{len(chunks)} チャンク完了)")

        return full_transcript
    except ImportError:
        st.error("pydubライブラリがインストールされていません。")
        return None
    except Exception as e:
        if "ffmpeg" in str(e).lower() or "ffprobe" in str(e).lower():
            st.error("エラー: 音声ファイルの分割に必要な「FFmpeg」がシステムに見つかりません。FFmpegをインストールするか、25MB以下のファイルをアップロードしてください。")
        else:
            st.error(f"文字起こしエラー: {e}")
        return None

def generate_minutes(transcript_text):
    """GPT-4oを使って議事録を生成する（長文分割・Rate Limit対応）"""
    api_key = os.environ.get("OPENAI_API_KEY")
    client = openai.OpenAI(api_key=api_key)

    current_date = datetime.now().strftime("%Y/%m/%d")
    
    # トークン制限（約30000TPM）を回避するため、文字数で大まかに分割（約8000文字ごと）
    chunk_size = 10000 
    text_chunks = [transcript_text[i:i+chunk_size] for i in range(0, len(transcript_text), chunk_size)]
    
    # 複数チャンクがある場合は、まず各チャンクから要素を抽出
    all_extracted_points = ""
    
    if len(text_chunks) > 1:
        my_bar = st.progress(0, text="長文データのため、内容を分割して要約中...")
        for i, chunk in enumerate(text_chunks):
            try:
                # 中間要約には安価で高速な gpt-4o-mini を使用
                extract_prompt = f"以下の会議の文字起こしの一部から、重要な発言、決定事項、ToDo、論点を箇条書きで漏れなく抽出してください。\n\n{chunk}"
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": extract_prompt}
                    ],
                    temperature=0.3
                )
                all_extracted_points += f"\n--- パート {i+1} ---\n" + response.choices[0].message.content + "\n"
                my_bar.progress((i + 1) / len(text_chunks), text=f"内容を分割して要約中... ({i+1}/{len(text_chunks)} 完了)")
            except Exception as e:
                st.error(f"要約エラー (パート {i+1}): {e}")
                return None
        
        # 最終的な構成プロンプトの入力には抽出結果を渡す
        target_text = all_extracted_points
        final_prompt_sys = SYSTEM_PROMPT.replace("{date}", current_date) + "\n\n以下のテキストは長時間の会議を時系列に沿って要約したメモです。これらを統合し、指定されたフォーマットの1つの議事録として完璧に清書してください。"
    else:
        target_text = transcript_text
        final_prompt_sys = SYSTEM_PROMPT.replace("{date}", current_date)

    st.write("🤖 最終的な議事録を構成中...")
    try:
        # 最終構成は高精度な gpt-4o を使用
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": final_prompt_sys},
                {"role": "user", "content": f"以下のデータをもとに議事録を作成してください。\n\n{target_text}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"最終議事録生成エラー: {e}")
        return None

def render_minutes_generator():
    st.header("📝 議事録作成")

    # サイドバーで機能説明
    with st.sidebar:
        st.info("💡 使い方: 会議の録音データ（mp3, m4a, wavなど）をアップロードすると、AIが文字起こしと議事録作成を自動で行います。OpenAI API Keyが必要です。")
        st.info("💵 文字起こし費用を節約するため、一度作成した文字起こしテキスト（.txt）をアップロードして議事録のみを作成することも可能です。")

    # APIキー確認
    if not os.environ.get("OPENAI_API_KEY"):
        st.warning("⚠️ 左のサイドバーで OpenAI API Key を設定してください。")
        return

    # 入力方法の選択
    input_mode = st.radio(
        "入力データを選択してください:", 
        ["音声ファイルから作成（新規）", "文字起こしテキストから作成（節約）"], 
        horizontal=True
    )

    if "edited_transcript" not in st.session_state:
        st.session_state["edited_transcript"] = ""
    if "final_minutes" not in st.session_state:
        st.session_state["final_minutes"] = ""

    if input_mode == "音声ファイルから作成（新規）":
        # 音声ファイルアップロード
        audio_file = st.file_uploader("会議の録音ファイルをアップロード", type=["mp3", "m4a", "wav", "mp4"])

        if audio_file:
            st.audio(audio_file, format="audio/mp3")

            if st.button("1. 文字起こしを開始する", type="primary"):
                # 新しいファイルがアップロードされたら状態をリセット
                st.session_state["final_minutes"] = ""
                
                with st.spinner("音声を処理中... (これには時間がかかる場合があります)"):
                    # 一時ファイル保存
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_file.name.split('.')[-1]}") as tmp_file:
                        tmp_file.write(audio_file.getbuffer())
                        tmp_path = tmp_file.name
                    
                    # 1. 文字起こし
                    st.write("🔄 文字起こしを実行中...")
                    transcript = transcribe_audio(tmp_path)
                    
                    # 後始末
                    os.unlink(tmp_path)

                    if transcript:
                        st.session_state["current_transcript"] = transcript
                        st.session_state["edited_transcript"] = transcript # 編集用初期値
                        st.success("✅ 文字起こしが完了しました！内容を確認・修正してください。")

    else:
        # テキストファイルアップロード（節約モード）
        text_file = st.file_uploader("保存済みの文字起こしテキスト (.txt) をアップロード", type=["txt"])
        
        if text_file:
            transcript = text_file.getvalue().decode("utf-8")
            if st.button("1. テキストを読み込む", type="primary"):
                st.session_state["current_transcript"] = transcript
                st.session_state["edited_transcript"] = transcript
                st.session_state["final_minutes"] = ""
                st.success("✅ テキストの読み込みが完了しました！内容を確認・修正してください。")

    # --- Step 1: 文字起こしの確認と手動修正 ---
    if "current_transcript" in st.session_state and st.session_state["current_transcript"]:
        st.divider()
        st.subheader("📝 Step 1: 文字起こしの確認・修正")
        st.write("AIの変換ミスなどがあれば、ここで直接テキストを修正できます。")
        
        # ユーザーが編集可能なテキストエリア
        st.session_state["edited_transcript"] = st.text_area(
            "文字起こしデータ (直接編集可能)", 
            value=st.session_state["edited_transcript"], 
            height=300
        )
        
        # 修正版のダウンロードボタン
        st.download_button(
            label="💾 現在の文字起こしテキストを保存する (.txt)",
            data=st.session_state["edited_transcript"],
            file_name=f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            help="次回再要約する際、このテキストをアップロードすることで文字起こしの費用を節約できます。"
        )
        
        if st.button("2. この内容で議事録を作成する (要約)", type="primary"):
            with st.spinner("🤖 AIが議事録を構成中..."):
                minutes = generate_minutes(st.session_state["edited_transcript"])
                if minutes:
                    st.session_state["final_minutes"] = minutes
                    st.success("✅ 議事録（要約）の生成が完了しました！")

    # --- Step 2: 議事録の確認と手動修正 ---
    if "final_minutes" in st.session_state and st.session_state["final_minutes"]:
        st.divider()
        st.subheader("🎉 Step 2: 議事録の最終調整")
        st.write("出力された議事録を最終確認し、必要に応じて手直ししてください。")
        
        # ユーザーが編集可能な要約テキストエリア
        st.session_state["final_minutes"] = st.text_area(
            "生成された議事録 (直接編集可能)", 
            value=st.session_state["final_minutes"], 
            height=400
        )
        
        # 最終版のダウンロードボタン
        st.download_button(
            label="📄 完成した議事録をダウンロード (.md)",
            data=st.session_state["final_minutes"],
            file_name=f"minutes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )
