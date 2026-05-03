-- ============================================================
-- Diet Analyze - Supabase テーブル初期化スクリプト v2
-- ============================================================
-- あすけんレベルの栄養素を記録
-- 使い方: Supabase Dashboard → SQL Editor にコピーして実行
-- ============================================================

-- 既存テーブルを削除（データが入っている場合は注意！）
DROP TABLE IF EXISTS meals CASCADE;
DROP TABLE IF EXISTS user_profiles CASCADE;

-- ユーザープロファイルテーブル
CREATE TABLE user_profiles (
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

-- 食事記録テーブル（あすけん準拠の栄養素）
CREATE TABLE meals (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    date TEXT NOT NULL,
    meal_type TEXT,
    original_text TEXT NOT NULL,
    food_name TEXT NOT NULL,
    -- 主要栄養素
    calories REAL DEFAULT 0,
    protein REAL DEFAULT 0,
    fat REAL DEFAULT 0,
    carbohydrates REAL DEFAULT 0,
    fiber REAL DEFAULT 0,
    sugar REAL DEFAULT 0,
    saturated_fat REAL DEFAULT 0,
    cholesterol REAL DEFAULT 0,
    salt_equivalent REAL DEFAULT 0,
    sodium REAL DEFAULT 0,
    -- ミネラル
    calcium REAL DEFAULT 0,
    iron REAL DEFAULT 0,
    magnesium REAL DEFAULT 0,
    zinc REAL DEFAULT 0,
    potassium REAL DEFAULT 0,
    -- ビタミン
    vitamin_a REAL DEFAULT 0,
    vitamin_b1 REAL DEFAULT 0,
    vitamin_b2 REAL DEFAULT 0,
    vitamin_b6 REAL DEFAULT 0,
    vitamin_b12 REAL DEFAULT 0,
    vitamin_c REAL DEFAULT 0,
    vitamin_d REAL DEFAULT 0,
    vitamin_e REAL DEFAULT 0,
    vitamin_k REAL DEFAULT 0,
    folate REAL DEFAULT 0,
    -- メタ
    confidence TEXT DEFAULT '中',
    telegram_user_id BIGINT REFERENCES user_profiles(telegram_user_id)
);

-- パフォーマンス用インデックス
CREATE INDEX idx_meals_date ON meals(date);
CREATE INDEX idx_meals_user ON meals(telegram_user_id);
CREATE INDEX idx_meals_user_date ON meals(telegram_user_id, date);

-- RLS + 全アクセス許可ポリシー
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE meals ENABLE ROW LEVEL SECURITY;

CREATE POLICY allow_all_user_profiles ON user_profiles FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY allow_all_meals ON meals FOR ALL USING (true) WITH CHECK (true);
