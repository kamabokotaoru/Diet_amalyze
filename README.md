# 🥗 Diet Analyze - 食事記録 & 栄養分析アプリ

Gemini AI でテキストから食事を分析し、カロリー・栄養素を自動記録するアプリ。
iPhoneのTelegramから送信可能。Streamlitダッシュボードでデータを可視化。

**すべて無料クラウドサービスで常時稼働。**

## 🏗️ アーキテクチャ

```
📱 iPhone/PC (Telegram) → 🤖 Telegram Bot (Render.com)
                                    ↓
                           🧠 Gemini 2.5 Flash (Google AI)
                                    ↓
                           💾 PostgreSQL (Supabase)
                                    ↓
                           📊 Dashboard (Streamlit Cloud)
```

## 📋 必要なアカウント（すべて無料）

| サービス | 用途 | 登録URL |
|:---------|:-----|:--------|
| Google AI Studio | Gemini API Key | https://aistudio.google.com/ |
| Telegram | Bot Token | アプリ内で @BotFather に /newbot |
| Supabase | データベース | https://supabase.com/ |
| GitHub | コードホスティング | https://github.com/ |
| Render.com | Bot デプロイ | https://render.com/ |
| Streamlit Cloud | ダッシュボード | https://share.streamlit.io/ |

## 🚀 セットアップ手順

### Step 1: APIキーの取得

1. **Gemini API Key**
   - [Google AI Studio](https://aistudio.google.com/) にログイン
   - 「Get API Key」→ キーを作成 → コピー

2. **Telegram Bot Token**
   - Telegramで [@BotFather](https://t.me/BotFather) を検索
   - `/newbot` コマンドで新しいBotを作成
   - Bot名を入力 → トークンが発行される → コピー

3. **Supabase**
   - [Supabase](https://supabase.com/) にGitHubアカウントでログイン
   - 「New Project」→ プロジェクト作成
   - **SQL Editor** → `init_supabase.sql` の内容をコピー&実行
   - **Settings → API** → `URL` と `anon public key` をコピー

### Step 2: ローカル開発（オプション）

```bash
# リポジトリのクローン
git clone https://github.com/kamabokotaoru/Diet_amalyze.git
cd Diet_amalyze

# 仮想環境を作成
python -m venv .venv
.venv\Scripts\activate  # Windows

# 依存パッケージをインストール
pip install -r requirements.txt

# .envファイルを作成
copy .env.example .env
# .env を編集してAPIキーを入力

# Telegram Bot をローカルで実行（Pollingモード）
python bot/telegram_bot.py

# ダッシュボードをローカルで実行（別ターミナル）
cd dashboard
streamlit run dashboard.py
```

### Step 3: Render.com にBotをデプロイ

1. このリポジトリをGitHubにプッシュ
2. [Render.com](https://render.com/) にGitHubでログイン
3. 「New Web Service」→ GitHubリポジトリを選択
4. 設定:
   - **Name**: `diet-analyze-bot`
   - **Root Directory**: `bot`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn telegram_bot:app --bind 0.0.0.0:$PORT --timeout 120`
   - **Instance Type**: `Free`
5. **Environment Variables** に以下を追加:
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
6. デプロイ完了後、ブラウザで以下にアクセスしてWebhookを設定:
   ```
   https://YOUR-APP.onrender.com/set_webhook
   ```

### Step 4: Streamlit Cloud にダッシュボードをデプロイ

1. [Streamlit Community Cloud](https://share.streamlit.io/) にGitHubでログイン
2. 「New app」→ リポジトリを選択
3. 設定:
   - **Main file path**: `dashboard/dashboard.py`
4. **Advanced settings → Secrets** に以下を追加:
   ```toml
   SUPABASE_URL = "https://xxxxx.supabase.co"
   SUPABASE_KEY = "your_supabase_anon_key"
   GEMINI_API_KEY = "your_gemini_api_key"
   ```
5. デプロイ！

## 📱 使い方

### Telegram Bot

テキストを送信するだけで食事を記録：
```
カツ丼を食べた
→ 🔥 893 kcal | P:32.5g F:35.2g C:98.3g

コンビニのおにぎり2個とお茶
→ 🔥 360 kcal | P:8.0g F:3.0g C:76.0g
```

### コマンド一覧

| コマンド | 説明 |
|:---------|:-----|
| `/start` | Bot起動 & 初期設定 |
| `/today` | 今日の記録 |
| `/week` | 週間サマリー |
| `/history` | 直近10件 |
| `/weight 65` | 体重を65kgに変更 |
| `/activity 高` | 活動量変更（低/中/高） |
| `/profile` | プロファイル表示 |
| `/help` | ヘルプ |

## ⚠️ 注意事項

- 栄養成分の値はAIによる推定値です。医療目的での使用は避けてください
- Render.com無料枠: 15分無操作でスリープ（初回応答に~30秒かかります）
- Supabase無料枠: 1週間無操作でDB一時停止（ダッシュボードから再開可能）

## 📁 プロジェクト構成

```
Diet_amalyze/
├── .env.example          # 環境変数テンプレート
├── .gitignore
├── requirements.txt      # 全依存パッケージ
├── render.yaml           # Render.com デプロイ設定
├── init_supabase.sql     # DB初期化SQL
├── README.md
├── config.py             # 設定管理 & BMR計算
├── database.py           # Supabase DB操作
├── analyzer.py           # Gemini AI 栄養分析
├── bot/
│   ├── telegram_bot.py   # Telegram Bot (Flask)
│   ├── requirements.txt
│   └── Procfile
└── dashboard/
    ├── dashboard.py      # Streamlit ダッシュボード
    ├── requirements.txt
    └── .streamlit/
        └── config.toml   # ダークテーマ設定
```
