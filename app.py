"""
英文会議文字起こし → 日本語議事録 変換Webアプリ
Google Cloud Translation API + Claude API を使用
"""

import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from google.cloud import translate_v2 as translate
from anthropic import Anthropic
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

app = Flask(__name__)

# Google Translate クライアント
translate_client = None

# Claude クライアント
anthropic_client = None

# 議事録作成プロンプト（ルール）
MINUTES_CREATION_PROMPT = """# 役割
あなたは議事録作成の専門家であり、翻訳のプロです。
金型の専門用語を正確に翻訳できるプロでもあります。

# 前提
ユーザーが入力した文字起こしデータを日本語に翻訳し、議事録を作成してください。
各外国語特有の言語文化を考慮し、必ず日本語の議事録に沿うように変換してください。

# 指示
- 会議の趣旨をわかりやすく議事録にまとめてください。
- ビジネス文書として言葉を丁寧かつ簡潔に伝え、読む人を不快にさせないようにしてください。
- 5W1Hを明確に読み取って出力してください。
- 結論からわかりやすく書く。
- 外国語の会話を逐語訳ではなく、日本語の議事録としてわかりやすく作成してください。
- 翻訳が不完全な箇所は「（要確認）」と書いてください。

## 議事録に記載してほしいこと
- 会議の議題
- 会議が実施された場所
- 会議が実施された日時と時間帯
- 参加者の名前
- 会議の参加者の質問内容と、それに対する回答
- 決定事項
- タスクと責任（To Do）
- タスクの期限
- 未決事項

## 誤訳・事故防止ルール（必須）
### 数字・単位・日付
数字は必ず単位付きで書く（日付は誤読が起きやすいので、可能なら補足する）
- 例：3/4 → 「3月4日（表記は原文3/4）」
- million / billion の誤訳に注意する
- mm / cm / inch など単位の混同に注意する

### 否定表現
not / no / unless による意味反転に注意する。「not impossible」などは直訳せず、誤解のない表現に変換する
例：「不可能ではない」→「可能性がある」

### 主語の明確化
- we / they / you などの曖昧な主語は、可能な限り会社名・部署名・担当者に置換する
- 主語が特定できない場合は「（主語不明）」と明記する

### 不明箇所は推測しない
聞き取れない箇所を勝手に補完しない。
次の表現で明示する。
- 「（聞き取り不明瞭）」
- 「（固有名詞不明）」
- 「（詳細要確認）」
重要な不明点はToDoへ落とす

# 注意点
- 数字を間違いなく記載してください。会議中に話されていない数字を勝手に出力するのは厳禁です。
- 曖昧語を避けてください。（例：なるはや、適宜、いい感じ）
- 翻訳が不完全な箇所で推測の出力はNG
- ハルシネーションは絶対NG

# 出力フォーマット
以下の形式で議事録を出力してください：

---
# 議事録

## 基本情報
- **議題**: [会議の議題]
- **日時**: [日時（原文表記も補足）]
- **場所**: [場所]
- **参加者**: [参加者名をカンマ区切りで]

## 会議の要旨
[結論から簡潔に記載]

## 詳細内容
[会議の詳細をわかりやすく整理]

## 質疑応答
| 質問者 | 質問内容 | 回答者 | 回答内容 |
|--------|----------|--------|----------|
| [名前] | [質問] | [名前] | [回答] |

## 決定事項
- [決定事項1]
- [決定事項2]

## タスク・To Do
| 担当者 | タスク内容 | 期限 |
|--------|-----------|------|
| [名前] | [タスク] | [期限] |

## 未決事項
- [未決事項があれば記載]

---
"""


def get_translate_client():
    """Google Translate クライアントを取得（遅延初期化）"""
    global translate_client
    if translate_client is None:
        translate_client = translate.Client()
    return translate_client


def get_anthropic_client():
    """Anthropic クライアントを取得（遅延初期化）"""
    global anthropic_client
    if anthropic_client is None:
        anthropic_client = Anthropic()
    return anthropic_client


def translate_text(text: str, target_language: str = "ja") -> dict:
    """
    テキストを翻訳する

    Args:
        text: 翻訳するテキスト
        target_language: 翻訳先言語（デフォルト: 日本語）

    Returns:
        翻訳結果を含む辞書
    """
    client = get_translate_client()
    result = client.translate(text, target_language=target_language)
    return {
        "original": text,
        "translated": result["translatedText"],
        "detected_language": result.get("detectedSourceLanguage", "unknown")
    }


def create_minutes_with_claude(original_text: str, translated_text: str) -> str:
    """
    Claude APIを使って議事録を作成する

    Args:
        original_text: 原文（英語）
        translated_text: 翻訳済みテキスト（日本語）

    Returns:
        議事録形式の文字列
    """
    client = get_anthropic_client()

    user_message = f"""以下は英語の会議文字起こしとその日本語翻訳です。
これを基に、指示に従って日本語の議事録を作成してください。

## 原文（英語）
{original_text}

## 翻訳（日本語・参考）
{translated_text}

上記の内容から、議事録を作成してください。
翻訳は参考として提供していますが、原文を正確に理解して議事録を作成してください。
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=MINUTES_CREATION_PROMPT,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    return message.content[0].text


@app.route("/")
def index():
    """メインページを表示"""
    return render_template("index.html")


@app.route("/translate", methods=["POST"])
def translate_endpoint():
    """翻訳APIエンドポイント"""
    try:
        data = request.get_json()
        text = data.get("text", "")

        if not text.strip():
            return jsonify({"error": "テキストが入力されていません"}), 400

        # Google翻訳を実行（参考用）
        result = translate_text(text)

        # Claude APIで議事録を作成
        minutes = create_minutes_with_claude(text, result["translated"])

        return jsonify({
            "success": True,
            "original": result["original"],
            "translated": result["translated"],
            "detected_language": result["detected_language"],
            "minutes": minutes
        })

    except Exception as e:
        return jsonify({
            "error": f"エラー: {str(e)}"
        }), 500


@app.route("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # デバッグモードで起動（本番環境ではFalseに）
    # ポート5000はmacOSのAirPlay Receiverで使用されるため8080を使用
    app.run(debug=True, host="0.0.0.0", port=8080)
