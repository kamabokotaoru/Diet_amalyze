"""
Diet Analyze - データベースモジュール

Supabase PostgreSQL を使用して食事記録・ユーザープロファイルを管理する。
"""

import os
from datetime import datetime, timedelta
from supabase import create_client, Client

# Supabase クライアント初期化
_supabase_client: Client | None = None


def get_client() -> Client:
    """Supabase クライアントを取得する（シングルトン）"""
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            raise ValueError("SUPABASE_URL と SUPABASE_KEY を設定してください")
        _supabase_client = create_client(url, key)
    return _supabase_client


# =============================================================
# テーブル初期化用SQL（Supabase SQL Editorで手動実行）
# =============================================================
INIT_SQL = """
-- ユーザープロファイル
CREATE TABLE IF NOT EXISTS user_profiles (
    telegram_user_id BIGINT PRIMARY KEY,
    username TEXT,
    gender TEXT DEFAULT 'male',
    height_cm REAL DEFAULT 168,
    weight_kg REAL DEFAULT 70,
    activity_level TEXT DEFAULT 'moderate',
    daily_calorie_target REAL DEFAULT 2200,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 食事記録テーブル
CREATE TABLE IF NOT EXISTS meals (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    date TEXT NOT NULL,
    meal_type TEXT,
    original_text TEXT NOT NULL,
    food_name TEXT NOT NULL,
    calories REAL DEFAULT 0,
    protein REAL DEFAULT 0,
    fat REAL DEFAULT 0,
    carbohydrates REAL DEFAULT 0,
    fiber REAL DEFAULT 0,
    sugar REAL DEFAULT 0,
    sodium REAL DEFAULT 0,
    calcium REAL DEFAULT 0,
    iron REAL DEFAULT 0,
    vitamin_a REAL DEFAULT 0,
    vitamin_c REAL DEFAULT 0,
    confidence TEXT DEFAULT '中',
    telegram_user_id BIGINT REFERENCES user_profiles(telegram_user_id)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(date);
CREATE INDEX IF NOT EXISTS idx_meals_user ON meals(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(telegram_user_id, date);

-- RLS (Row Level Security) を無効化（個人利用のため）
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE meals ENABLE ROW LEVEL SECURITY;

-- 全アクセスを許可するポリシー（anon keyで操作するため）
CREATE POLICY "Allow all access to user_profiles"
    ON user_profiles FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all access to meals"
    ON meals FOR ALL
    USING (true)
    WITH CHECK (true);
"""


# =============================================================
# ユーザープロファイル操作
# =============================================================

def get_user_profile(telegram_user_id: int) -> dict | None:
    """ユーザープロファイルを取得する"""
    client = get_client()
    result = (
        client.table("user_profiles")
        .select("*")
        .eq("telegram_user_id", telegram_user_id)
        .execute()
    )
    if result.data:
        return result.data[0]
    return None


def upsert_user_profile(telegram_user_id: int, **kwargs) -> dict:
    """
    ユーザープロファイルを作成または更新する。

    kwargs: username, gender, height_cm, weight_kg, activity_level, daily_calorie_target
    """
    client = get_client()
    data = {"telegram_user_id": telegram_user_id, "updated_at": datetime.utcnow().isoformat()}
    data.update({k: v for k, v in kwargs.items() if v is not None})

    result = (
        client.table("user_profiles")
        .upsert(data, on_conflict="telegram_user_id")
        .execute()
    )
    return result.data[0] if result.data else data


# =============================================================
# 食事記録操作
# =============================================================

def save_meal(
    telegram_user_id: int,
    date: str,
    original_text: str,
    food_name: str,
    meal_type: str = "不明",
    calories: float = 0,
    protein: float = 0,
    fat: float = 0,
    carbohydrates: float = 0,
    fiber: float = 0,
    sugar: float = 0,
    sodium: float = 0,
    calcium: float = 0,
    iron: float = 0,
    vitamin_a: float = 0,
    vitamin_c: float = 0,
    confidence: str = "中",
) -> dict:
    """食事記録を保存する"""
    client = get_client()
    data = {
        "telegram_user_id": telegram_user_id,
        "date": date,
        "original_text": original_text,
        "food_name": food_name,
        "meal_type": meal_type,
        "calories": calories,
        "protein": protein,
        "fat": fat,
        "carbohydrates": carbohydrates,
        "fiber": fiber,
        "sugar": sugar,
        "sodium": sodium,
        "calcium": calcium,
        "iron": iron,
        "vitamin_a": vitamin_a,
        "vitamin_c": vitamin_c,
        "confidence": confidence,
    }
    result = client.table("meals").insert(data).execute()
    return result.data[0] if result.data else data


def get_meals_by_date(telegram_user_id: int, date: str) -> list[dict]:
    """指定日の食事記録を取得する"""
    client = get_client()
    result = (
        client.table("meals")
        .select("*")
        .eq("telegram_user_id", telegram_user_id)
        .eq("date", date)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data


def get_daily_summary(telegram_user_id: int, date: str) -> dict:
    """指定日の合計栄養素を計算する"""
    meals = get_meals_by_date(telegram_user_id, date)

    summary = {
        "date": date,
        "meal_count": len(meals),
        "total_calories": 0,
        "total_protein": 0,
        "total_fat": 0,
        "total_carbs": 0,
        "total_fiber": 0,
        "total_sugar": 0,
        "total_sodium": 0,
        "total_calcium": 0,
        "total_iron": 0,
        "total_vitamin_a": 0,
        "total_vitamin_c": 0,
    }

    for meal in meals:
        summary["total_calories"] += meal.get("calories", 0) or 0
        summary["total_protein"] += meal.get("protein", 0) or 0
        summary["total_fat"] += meal.get("fat", 0) or 0
        summary["total_carbs"] += meal.get("carbohydrates", 0) or 0
        summary["total_fiber"] += meal.get("fiber", 0) or 0
        summary["total_sugar"] += meal.get("sugar", 0) or 0
        summary["total_sodium"] += meal.get("sodium", 0) or 0
        summary["total_calcium"] += meal.get("calcium", 0) or 0
        summary["total_iron"] += meal.get("iron", 0) or 0
        summary["total_vitamin_a"] += meal.get("vitamin_a", 0) or 0
        summary["total_vitamin_c"] += meal.get("vitamin_c", 0) or 0

    # 小数点1桁に丸める
    for key in summary:
        if key.startswith("total_"):
            summary[key] = round(summary[key], 1)

    return summary


def get_weekly_summary(telegram_user_id: int) -> list[dict]:
    """直近7日間のサマリーを取得する"""
    today = datetime.utcnow().date()
    summaries = []
    for i in range(6, -1, -1):
        date_str = (today - timedelta(days=i)).isoformat()
        summary = get_daily_summary(telegram_user_id, date_str)
        summaries.append(summary)
    return summaries


def get_recent_meals(telegram_user_id: int, limit: int = 10) -> list[dict]:
    """直近の食事記録を取得する"""
    client = get_client()
    result = (
        client.table("meals")
        .select("*")
        .eq("telegram_user_id", telegram_user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def get_all_meals_range(
    telegram_user_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """
    ダッシュボード用: 全ユーザーまたは特定ユーザーの食事記録を取得。
    日付範囲でフィルタ可能。
    """
    client = get_client()
    query = client.table("meals").select("*")

    if telegram_user_id:
        query = query.eq("telegram_user_id", telegram_user_id)
    if start_date:
        query = query.gte("date", start_date)
    if end_date:
        query = query.lte("date", end_date)

    result = query.order("created_at", desc=True).limit(1000).execute()
    return result.data


def get_all_user_profiles() -> list[dict]:
    """全ユーザープロファイルを取得する（ダッシュボード用）"""
    client = get_client()
    result = client.table("user_profiles").select("*").execute()
    return result.data
