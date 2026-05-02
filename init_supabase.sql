-- ============================================================
-- Diet Analyze - Supabase テーブル初期化スクリプト
-- ============================================================
-- 使い方: Supabase Dashboard → SQL Editor にコピーして実行
-- ============================================================

-- ユーザープロファイルテーブル
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

-- パフォーマンス用インデックス
CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(date);
CREATE INDEX IF NOT EXISTS idx_meals_user ON meals(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(telegram_user_id, date);

-- ============================================================
-- Row Level Security (RLS) 設定
-- 個人利用のため全アクセスを許可
-- ============================================================

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE meals ENABLE ROW LEVEL SECURITY;

-- user_profiles の全アクセスポリシー
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'allow_all_user_profiles'
    ) THEN
        CREATE POLICY allow_all_user_profiles ON user_profiles
            FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;

-- meals の全アクセスポリシー
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'allow_all_meals'
    ) THEN
        CREATE POLICY allow_all_meals ON meals
            FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;
