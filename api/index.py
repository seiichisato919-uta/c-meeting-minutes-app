"""
英文会議文字起こし → 日本語議事録 変換Webアプリ
Vercel Serverless Function版
"""

import os
import json
import base64
from http.server import BaseHTTPRequestHandler

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

# HTMLテンプレート
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>英文会議 → 日本語議事録 変換システム</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header { text-align: center; color: white; margin-bottom: 30px; }
        header h1 { font-size: 2rem; margin-bottom: 10px; }
        header p { opacity: 0.9; }
        .main-content { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 900px) { .main-content { grid-template-columns: 1fr; } }
        .panel {
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            overflow: hidden;
        }
        .panel-header {
            background: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 1px solid #e9ecef;
        }
        .panel-header h2 { font-size: 1.1rem; color: #495057; }
        .panel-body { padding: 20px; }
        textarea {
            width: 100%;
            height: 400px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            font-size: 14px;
            line-height: 1.6;
            resize: vertical;
            font-family: inherit;
            transition: border-color 0.3s;
        }
        textarea:focus { outline: none; border-color: #667eea; }
        .btn-container { text-align: center; margin: 20px 0; }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 50px;
            font-size: 1.1rem;
            border-radius: 30px;
            cursor: pointer;
            transition: transform 0.3s, box-shadow 0.3s;
            font-weight: bold;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .btn-copy { background: #28a745; padding: 10px 25px; font-size: 0.9rem; margin-top: 10px; }
        .output-area {
            background: #f8f9fa;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            height: 400px;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        .loading { display: none; text-align: center; padding: 20px; }
        .loading.active { display: block; }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px; margin-top: 10px; }
        .success-badge {
            display: inline-block;
            background: #d4edda;
            color: #155724;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-bottom: 10px;
        }
        .info-box {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            font-size: 0.9rem;
            color: #856404;
        }
        .info-box h3 { margin-bottom: 10px; }
        .info-box ul { margin-left: 20px; }
        .tabs { display: flex; border-bottom: 2px solid #e9ecef; margin-bottom: 15px; }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            transition: all 0.3s;
        }
        .tab:hover { background: #f8f9fa; }
        .tab.active { border-bottom-color: #667eea; color: #667eea; font-weight: bold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>英文会議 → 日本語議事録 変換システム</h1>
            <p>英語の会議文字起こしを入力すると、日本語の議事録形式に変換します</p>
        </header>
        <div class="main-content">
            <div class="panel">
                <div class="panel-header"><h2>入力：英文会議の文字起こし</h2></div>
                <div class="panel-body">
                    <textarea id="inputText" placeholder="ここに英語の会議文字起こしを貼り付けてください..."></textarea>
                    <div class="btn-container">
                        <button class="btn" id="translateBtn" onclick="translateText()">翻訳して議事録を作成</button>
                    </div>
                    <div class="loading" id="loading">
                        <div class="spinner"></div>
                        <p>議事録を作成中です。しばらくお待ちください...</p>
                    </div>
                    <div id="errorContainer"></div>
                </div>
            </div>
            <div class="panel">
                <div class="panel-header"><h2>出力：日本語議事録</h2></div>
                <div class="panel-body">
                    <div class="tabs">
                        <div class="tab active" onclick="switchTab('minutes')">議事録</div>
                        <div class="tab" onclick="switchTab('translation')">翻訳のみ</div>
                    </div>
                    <div id="minutesTab" class="tab-content active">
                        <div id="minutesOutput" class="output-area">ここに議事録が表示されます...</div>
                        <button class="btn btn-copy" onclick="copyToClipboard('minutesOutput')">議事録をコピー</button>
                    </div>
                    <div id="translationTab" class="tab-content">
                        <div id="translationOutput" class="output-area">ここに翻訳結果が表示されます...</div>
                        <button class="btn btn-copy" onclick="copyToClipboard('translationOutput')">翻訳をコピー</button>
                    </div>
                    <div id="detectedLang" style="display: none; margin-top: 10px;">
                        <span class="success-badge">検出言語: <span id="langCode"></span></span>
                    </div>
                </div>
            </div>
        </div>
        <div class="info-box">
            <h3>議事録作成時の注意事項</h3>
            <ul>
                <li><strong>数字・日付</strong>: 必ず単位付きで確認。日付は「3月4日（原文: 3/4）」のように補足</li>
                <li><strong>否定表現</strong>: not/no/unlessによる意味反転に注意</li>
                <li><strong>主語の明確化</strong>: we/they/youは会社名・担当者名に置換</li>
                <li><strong>不明箇所</strong>: 「（聞き取り不明瞭）」「（固有名詞不明）」「（詳細要確認）」で明示</li>
            </ul>
        </div>
    </div>
    <script>
        async function translateText() {
            const inputText = document.getElementById('inputText').value;
            const translateBtn = document.getElementById('translateBtn');
            const loading = document.getElementById('loading');
            const errorContainer = document.getElementById('errorContainer');
            if (!inputText.trim()) { showError('テキストを入力してください'); return; }
            translateBtn.disabled = true;
            loading.classList.add('active');
            errorContainer.innerHTML = '';
            try {
                const response = await fetch('/api/translate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: inputText })
                });
                const data = await response.json();
                if (data.error) { showError(data.error); return; }
                document.getElementById('minutesOutput').textContent = data.minutes;
                document.getElementById('translationOutput').textContent = data.translated;
                document.getElementById('langCode').textContent = data.detected_language.toUpperCase();
                document.getElementById('detectedLang').style.display = 'block';
            } catch (error) {
                showError('通信エラーが発生しました: ' + error.message);
            } finally {
                translateBtn.disabled = false;
                loading.classList.remove('active');
            }
        }
        function showError(message) {
            document.getElementById('errorContainer').innerHTML = '<div class="error">' + message + '</div>';
        }
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            if (tabName === 'minutes') {
                document.querySelector('.tab:first-child').classList.add('active');
                document.getElementById('minutesTab').classList.add('active');
            } else {
                document.querySelector('.tab:last-child').classList.add('active');
                document.getElementById('translationTab').classList.add('active');
            }
        }
        function copyToClipboard(elementId) {
            const text = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(text).then(() => alert('クリップボードにコピーしました'));
        }
    </script>
</body>
</html>"""


def get_google_credentials():
    """環境変数からGoogle認証情報を取得"""
    from google.oauth2 import service_account

    creds_base64 = os.environ.get('GOOGLE_CREDENTIALS_BASE64')
    if creds_base64:
        creds_json = base64.b64decode(creds_base64).decode('utf-8')
        creds_dict = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        return credentials
    return None


def translate_text(text: str) -> dict:
    """Google Translate APIで翻訳"""
    from google.cloud import translate_v2 as translate

    credentials = get_google_credentials()
    if credentials:
        client = translate.Client(credentials=credentials)
    else:
        client = translate.Client()

    result = client.translate(text, target_language='ja')
    return {
        "translated": result["translatedText"],
        "detected_language": result.get("detectedSourceLanguage", "unknown")
    }


def create_minutes_with_claude(original_text: str, translated_text: str) -> str:
    """Claude APIで議事録を作成"""
    from anthropic import Anthropic

    client = Anthropic()

    user_message = f"""以下は英語の会議文字起こしとその日本語翻訳です。
これを基に、指示に従って日本語の議事録を作成してください。

## 原文（英語）
{original_text}

## 翻訳（日本語・参考）
{translated_text}

上記の内容から、議事録を作成してください。
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=MINUTES_CREATION_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    return message.content[0].text


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/translate':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            text = data.get('text', '')

            if not text.strip():
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "テキストが入力されていません"}).encode())
                return

            try:
                # 翻訳
                result = translate_text(text)

                # 議事録作成
                minutes = create_minutes_with_claude(text, result["translated"])

                response = {
                    "success": True,
                    "original": text,
                    "translated": result["translated"],
                    "detected_language": result["detected_language"],
                    "minutes": minutes
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"エラー: {str(e)}"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
