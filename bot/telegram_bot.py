"""
Diet Analyze - Telegram Bot (Flask Webhook)

Flask + python-telegram-bot を使用したWebhookベースのTelegram Bot。
Render.com にデプロイして常時稼働。
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    calculate_daily_calories,
    calculate_bmr,
    ACTIVITY_MULTIPLIERS,
    DEFAULT_GENDER,
    DEFAULT_HEIGHT_CM,
    DEFAULT_WEIGHT_KG,
    DEFAULT_ACTIVITY_LEVEL,
)
from database import (
    get_user_profile,
    upsert_user_profile,
    save_meal,
    get_daily_summary,
    get_weekly_summary,
    get_recent_meals,
    get_meals_by_date,
)
from analyzer import analyze_meal, format_meal_result, analyze_daily_summary, format_daily_summary

# ===== ログ設定 =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== 日本時間 =====
JST = timezone(timedelta(hours=9))


def today_jst() -> str:
    """今日の日付を JST で YYYY-MM-DD 形式で返す"""
    return datetime.now(JST).strftime("%Y-%m-%d")


# =============================================================
# ユーティリティ
# =============================================================

def get_or_create_profile(telegram_user_id: int, username: str = "") -> dict:
    """ユーザープロファイルを取得、なければデフォルトで作成"""
    profile = get_user_profile(telegram_user_id)
    if not profile:
        target = calculate_daily_calories(
            DEFAULT_GENDER, DEFAULT_WEIGHT_KG, DEFAULT_HEIGHT_CM, DEFAULT_ACTIVITY_LEVEL
        )
        profile = upsert_user_profile(
            telegram_user_id,
            username=username,
            gender=DEFAULT_GENDER,
            height_cm=DEFAULT_HEIGHT_CM,
            weight_kg=DEFAULT_WEIGHT_KG,
            activity_level=DEFAULT_ACTIVITY_LEVEL,
            daily_calorie_target=target,
        )
    return profile


# =============================================================
# コマンドハンドラー
# =============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot起動 & 初期プロファイル設定"""
    user = update.effective_user
    profile = get_or_create_profile(user.id, user.username or user.first_name)
    target = profile.get("daily_calorie_target", 2200)

    text = (
        f"🥗 Diet Analyze へようこそ！\n"
        f"━━━━━━━━━━━━━━━\n"
        f"食べたものをテキストで送信するだけで\n"
        f"AIが栄養分析して記録します！\n\n"
        f"👤 プロファイル:\n"
        f"  性別: 男性 / 身長: {profile.get('height_cm', 168)}cm\n"
        f"  体重: {profile.get('weight_kg', 70)}kg\n"
        f"  活動量: {profile.get('activity_level', 'moderate')}\n"
        f"  目標カロリー: {target:,.0f} kcal/日\n\n"
        f"📝 使い方:\n"
        f"  テキスト送信 → 食事を記録\n"
        f"  例:「カツ丼を食べた」「コンビニのおにぎり2個」\n\n"
        f"📋 コマンド一覧:\n"
        f"  /today - 今日の記録\n"
        f"  /week - 週間サマリー\n"
        f"  /history - 直近の記録\n"
        f"  /weight 65 - 体重変更\n"
        f"  /activity 高 - 活動量変更\n"
        f"  /profile - プロファイル表示\n"
        f"  /help - ヘルプ"
    )
    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ヘルプメッセージ"""
    text = (
        "📖 Diet Analyze ヘルプ\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🍽️ 食事の記録方法:\n"
        "  テキストを送るだけ！\n"
        "  例: 「牛丼」「サラダとスープ」\n"
        "  例: 「朝ごはんにトースト2枚と目玉焼き」\n\n"
        "📊 データ確認:\n"
        "  /today - 今日の食事と合計\n"
        "  /week - 直近7日間のカロリー推移\n"
        "  /history - 直近10件の記録\n\n"
        "⚙️ 設定変更:\n"
        "  /weight 65 - 体重を65kgに変更\n"
        "  /activity 低 - 活動量を変更 (低/中/高)\n"
        "  /profile - 現在のプロファイル\n"
    )
    await update.message.reply_text(text)


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """今日の食事記録と合計"""
    user = update.effective_user
    profile = get_or_create_profile(user.id, user.username or "")
    date = today_jst()
    summary = get_daily_summary(user.id, date)
    meals = get_meals_by_date(user.id, date)
    target = profile.get("daily_calorie_target", 2200)

    if not meals:
        await update.message.reply_text(
            f"📅 {date}\n\nまだ今日の食事が記録されていません。\n"
            f"食べたものをテキストで送信してください！"
        )
        return

    lines = [f"📅 {date} の食事記録\n━━━━━━━━━━━━━━━\n"]

    for i, meal in enumerate(meals, 1):
        lines.append(
            f"{i}. {meal['food_name']} ({meal['calories']:,.0f} kcal)"
        )

    lines.append(f"\n📊 合計:")
    lines.append(f"  🔥 カロリー:    {summary['total_calories']:,.0f} / {target:,.0f} kcal")

    progress = min(summary["total_calories"] / target, 1.0) if target > 0 else 0
    bar_filled = int(progress * 15)
    bar_empty = 15 - bar_filled
    lines.append(f"  {'▓' * bar_filled}{'░' * bar_empty} {progress * 100:.0f}%")

    lines.append(f"\n  🥩 タンパク質:  {summary['total_protein']:,.1f} g")
    lines.append(f"  🧈 脂質:        {summary['total_fat']:,.1f} g")
    lines.append(f"  🍚 炭水化物:    {summary['total_carbs']:,.1f} g")
    lines.append(f"  🌿 食物繊維:    {summary['total_fiber']:,.1f} g")

    await update.message.reply_text("\n".join(lines))


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """直近7日間のサマリー"""
    user = update.effective_user
    profile = get_or_create_profile(user.id, user.username or "")
    target = profile.get("daily_calorie_target", 2200)
    summaries = get_weekly_summary(user.id)

    lines = ["📈 直近7日間のカロリー推移\n━━━━━━━━━━━━━━━\n"]

    total_week_cal = 0
    days_with_data = 0

    for s in summaries:
        cal = s["total_calories"]
        total_week_cal += cal
        if cal > 0:
            days_with_data += 1

        # ミニバーチャート
        bar_len = int(min(cal / target, 1.5) * 10) if target > 0 else 0
        bar = "█" * bar_len

        date_short = s["date"][5:]  # MM-DD
        if cal > 0:
            status = "🔴" if cal > target else "🟢"
            lines.append(f"{date_short} {bar} {cal:,.0f} kcal {status}")
        else:
            lines.append(f"{date_short} --- 記録なし")

    lines.append(f"\n📊 週間合計: {total_week_cal:,.0f} kcal")
    if days_with_data > 0:
        avg = total_week_cal / days_with_data
        lines.append(f"📊 平均: {avg:,.0f} kcal/日 (記録{days_with_data}日間)")
        lines.append(f"🎯 目標: {target:,.0f} kcal/日")

    await update.message.reply_text("\n".join(lines))


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """直近10件の食事記録"""
    user = update.effective_user
    meals = get_recent_meals(user.id, limit=10)

    if not meals:
        await update.message.reply_text("📋 まだ食事記録がありません。")
        return

    lines = ["📋 直近の食事記録\n━━━━━━━━━━━━━━━\n"]

    for meal in meals:
        date = meal.get("date", "")
        name = meal.get("food_name", "不明")
        cal = meal.get("calories", 0)
        lines.append(f"📅 {date} | {name} ({cal:,.0f} kcal)")

    await update.message.reply_text("\n".join(lines))


async def cmd_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """体重を更新"""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text("使い方: /weight 65\n（体重をkgで指定）")
        return

    try:
        weight = float(context.args[0])
        if weight < 20 or weight > 300:
            raise ValueError("範囲外")
    except (ValueError, IndexError):
        await update.message.reply_text("⚠️ 有効な体重を入力してください（例: /weight 65）")
        return

    profile = get_or_create_profile(user.id, user.username or "")
    gender = profile.get("gender", DEFAULT_GENDER)
    height = profile.get("height_cm", DEFAULT_HEIGHT_CM)
    activity = profile.get("activity_level", DEFAULT_ACTIVITY_LEVEL)
    new_target = calculate_daily_calories(gender, weight, height, activity)

    upsert_user_profile(
        user.id,
        weight_kg=weight,
        daily_calorie_target=new_target,
    )

    await update.message.reply_text(
        f"✅ 体重を {weight} kg に更新しました！\n"
        f"🎯 新しい目標カロリー: {new_target:,.0f} kcal/日"
    )


async def cmd_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """活動量を更新"""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "使い方: /activity 高\n"
            "選択肢: 低（デスクワーク）/ 中（軽い運動）/ 高（活発な運動）"
        )
        return

    level = context.args[0]
    if level not in ACTIVITY_MULTIPLIERS:
        await update.message.reply_text(
            f"⚠️ 「{level}」は無効です。\n選択肢: 低 / 中 / 高"
        )
        return

    profile = get_or_create_profile(user.id, user.username or "")
    gender = profile.get("gender", DEFAULT_GENDER)
    height = profile.get("height_cm", DEFAULT_HEIGHT_CM)
    weight = profile.get("weight_kg", DEFAULT_WEIGHT_KG)
    new_target = calculate_daily_calories(gender, weight, height, level)

    upsert_user_profile(
        user.id,
        activity_level=level,
        daily_calorie_target=new_target,
    )

    await update.message.reply_text(
        f"✅ 活動量を「{level}」に更新しました！\n"
        f"🎯 新しい目標カロリー: {new_target:,.0f} kcal/日"
    )


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """プロファイル表示"""
    user = update.effective_user
    profile = get_or_create_profile(user.id, user.username or "")

    gender = profile.get("gender", DEFAULT_GENDER)
    height = profile.get("height_cm", DEFAULT_HEIGHT_CM)
    weight = profile.get("weight_kg", DEFAULT_WEIGHT_KG)
    activity = profile.get("activity_level", DEFAULT_ACTIVITY_LEVEL)
    target = profile.get("daily_calorie_target", 2200)
    bmr = calculate_bmr(gender, weight, height)

    gender_jp = "男性" if gender == "male" else "女性"

    text = (
        f"👤 プロファイル\n"
        f"━━━━━━━━━━━━━━━\n"
        f"  性別:     {gender_jp}\n"
        f"  身長:     {height} cm\n"
        f"  体重:     {weight} kg\n"
        f"  活動量:   {activity}\n"
        f"  BMI:      {weight / (height / 100) ** 2:.1f}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"  基礎代謝(BMR):  {bmr:,.0f} kcal\n"
        f"  🎯 目標カロリー: {target:,.0f} kcal/日\n\n"
        f"変更コマンド:\n"
        f"  /weight 65 - 体重変更\n"
        f"  /activity 高 - 活動量変更"
    )
    await update.message.reply_text(text)


# =============================================================
# テキストメッセージハンドラー（食事記録）
# =============================================================

async def handle_meal_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """テキストメッセージを食事記録として処理する"""
    user = update.effective_user
    user_text = update.message.text.strip()

    if not user_text:
        return

    # 処理中メッセージ
    processing_msg = await update.message.reply_text("🔄 分析中...")

    try:
        # プロファイル取得
        profile = get_or_create_profile(user.id, user.username or "")
        target = profile.get("daily_calorie_target", 2200)

        # Gemini APIで分析
        analysis = analyze_meal(user_text)

        # 今日の日付（JST）
        date = today_jst()

        # 各食品をDBに保存（全栄養素をダイナミックに保存）
        for item in analysis.items:
            item_dict = item.model_dump()
            save_meal(
                telegram_user_id=user.id,
                date=date,
                original_text=user_text,
                food_name=item_dict.pop("food_name"),
                meal_type=item_dict.pop("meal_type"),
                confidence=item_dict.pop("confidence"),
                **item_dict,  # 残り全部が栄養素
            )

        # 今日の合計を取得
        daily = get_daily_summary(user.id, date)
        daily_total_before = daily["total_calories"] - analysis.total_calories

        # フォーマットして返信
        result_text = format_meal_result(analysis, daily_total_before, target)

        await processing_msg.edit_text(result_text)

    except Exception as e:
        logger.error(f"食事記録エラー: {e}", exc_info=True)
        await processing_msg.edit_text(
            f"⚠️ エラーが発生しました:\n{str(e)[:200]}\n\nもう一度お試しください。"
        )


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """今日の食事総評（1日の終わりに使用）"""
    user = update.effective_user
    profile = get_or_create_profile(user.id, user.username or "")
    target = profile.get("daily_calorie_target", 2200)
    date = today_jst()

    meals = get_meals_by_date(user.id, date)
    if not meals:
        await update.message.reply_text(
            f"📋 {date}\n\nまだ今日の食事が記録されていません。"
        )
        return

    processing_msg = await update.message.reply_text("🔄 総評を作成中...")

    try:
        summary = analyze_daily_summary(meals, target)
        result_text = format_daily_summary(summary, target)
        await processing_msg.edit_text(result_text)
    except Exception as e:
        logger.error(f"総評エラー: {e}", exc_info=True)
        await processing_msg.edit_text(f"⚠️ 総評エラー: {str(e)[:200]}")


# =============================================================
# Flask + Telegram Application
# =============================================================

app = Flask(__name__)

# Telegram Application をグローバルに初期化
telegram_app: Application | None = None


def get_telegram_app() -> Application:
    """Telegram Application を取得（シングルトン）"""
    global telegram_app
    if telegram_app is None:
        telegram_app = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )

        # コマンドハンドラーを登録
        telegram_app.add_handler(CommandHandler("start", cmd_start))
        telegram_app.add_handler(CommandHandler("help", cmd_help))
        telegram_app.add_handler(CommandHandler("today", cmd_today))
        telegram_app.add_handler(CommandHandler("week", cmd_week))
        telegram_app.add_handler(CommandHandler("history", cmd_history))
        telegram_app.add_handler(CommandHandler("weight", cmd_weight))
        telegram_app.add_handler(CommandHandler("activity", cmd_activity))
        telegram_app.add_handler(CommandHandler("profile", cmd_profile))
        telegram_app.add_handler(CommandHandler("summary", cmd_summary))

        # テキストメッセージ → 食事記録
        telegram_app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_meal_text)
        )

    return telegram_app


@app.route("/")
def index():
    """ヘルスチェック用エンドポイント"""
    return jsonify({"status": "ok", "service": "Diet Analyze Bot"})


@app.route("/health")
def health():
    """詳細ヘルスチェック"""
    has_token = bool(TELEGRAM_BOT_TOKEN)
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    has_supabase = bool(os.environ.get("SUPABASE_URL"))
    return jsonify({
        "status": "ok",
        "telegram_token": "set" if has_token else "MISSING",
        "gemini_key": "set" if has_gemini else "MISSING",
        "supabase_url": "set" if has_supabase else "MISSING",
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """Telegram Webhook エンドポイント"""
    try:
        tg_app = get_telegram_app()
        update = Update.de_json(request.get_json(force=True), tg_app.bot)

        # 非同期処理を同期的に実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def process():
            async with tg_app:
                await tg_app.process_update(update)

        loop.run_until_complete(process())
        loop.close()

        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Webhook エラー: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    """
    Webhook URLを設定する（デプロイ後に1回アクセス）

    使い方:
      https://YOUR-APP.onrender.com/set_webhook?url=https://YOUR-APP.onrender.com
    """
    # クエリパラメータ or 環境変数 or Requestヘッダーから URL を取得
    render_url = (
        request.args.get("url")
        or os.environ.get("RENDER_EXTERNAL_URL")
        or request.host_url.rstrip("/")
    )

    if not render_url or "localhost" in render_url:
        return jsonify({
            "error": "URLを指定してください",
            "usage": "GET /set_webhook?url=https://YOUR-APP.onrender.com",
        }), 400

    webhook_url = f"{render_url}/webhook"

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def setup():
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.set_webhook(url=webhook_url)
            info = await bot.get_webhook_info()
            return info.url

        result_url = loop.run_until_complete(setup())
        loop.close()

        return jsonify({"ok": True, "webhook_url": result_url})
    except Exception as e:
        logger.error(f"Webhook設定エラー: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================
# ローカル開発用（Polling モード）
# =============================================================

def run_polling():
    """ローカル開発用にPollingモードで実行する"""
    print("🤖 Diet Analyze Bot を Polling モードで起動します...")
    print("Ctrl+C で停止\n")

    tg_app = get_telegram_app()
    tg_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_polling()
