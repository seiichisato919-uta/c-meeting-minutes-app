# 英文会議 → 日本語議事録 変換システム

英語の会議文字起こしを入力すると、Google Cloud Translation API + Claude APIで翻訳・整形し、日本語議事録形式に変換するWebアプリケーションです。

## Vercelでのデプロイ

### 1. 環境変数の準備

Vercelにデプロイする前に、以下の環境変数を準備してください：

| 環境変数名 | 内容 |
|-----------|------|
| `ANTHROPIC_API_KEY` | Claude APIキー（sk-ant-...） |
| `GOOGLE_CREDENTIALS_BASE64` | Google認証情報JSONをBase64エンコードした文字列 |

#### Google認証情報のBase64エンコード方法

```bash
base64 -i your-service-account-key.json
```

出力された文字列を`GOOGLE_CREDENTIALS_BASE64`に設定します。

### 2. Vercelでデプロイ

1. GitHubリポジトリをVercelに接続
2. 環境変数を設定
3. デプロイ

## ローカル開発

### セットアップ

```bash
cd webapp

# 仮想環境を作成
python3 -m venv venv
source venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements.txt

# 環境変数を設定
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
export ANTHROPIC_API_KEY=sk-ant-xxxxx

# アプリを起動
python app.py
```

ブラウザで http://localhost:8080 にアクセス

## 使い方

1. 英語の会議文字起こしを入力
2. 「翻訳して議事録を作成」をクリック
3. 右側に議事録が表示される
4. 「議事録をコピー」でクリップボードにコピー

## 議事録作成ルール

- 5W1Hを明確に
- 結論から書く
- 数字・日付は原文表記も補足
- 曖昧な主語は具体名に置換
- 不明箇所は推測せず明示

## 料金

- **Google Cloud Translation API**: 月50万文字まで無料、以降$20/100万文字
- **Claude API**: 従量課金（https://www.anthropic.com/pricing）
