"""
Diet Analyze - 設定管理モジュール

環境変数の読み込み、ユーザープロファイル管理、
BMR(基礎代謝)計算を行う。
"""

import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み（ローカル開発用）
load_dotenv()

# ===== API Keys =====
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# ===== デフォルトユーザー設定 =====
DEFAULT_GENDER = "male"
DEFAULT_HEIGHT_CM = 168
DEFAULT_WEIGHT_KG = float(os.environ.get("DEFAULT_WEIGHT_KG", 70))
DEFAULT_ACTIVITY_LEVEL = os.environ.get("DEFAULT_ACTIVITY_LEVEL", "moderate")

# ===== 活動量レベルと係数 =====
ACTIVITY_MULTIPLIERS = {
    "低":       1.2,    # sedentary - デスクワーク中心
    "low":      1.2,
    "sedentary": 1.2,
    "中":       1.55,   # moderate - 軽い運動
    "moderate": 1.55,
    "高":       1.725,  # active - 活発な運動
    "high":     1.725,
    "active":   1.725,
    "very_high": 1.9,   # very active - ハードな運動
}

# ===== Gemini モデル設定 =====
GEMINI_MODEL = "gemini-2.5-flash"


def calculate_bmr(gender: str, weight_kg: float, height_cm: float, age: int = 30) -> float:
    """
    Harris-Benedict方程式でBMR(基礎代謝量)を計算する。

    Args:
        gender: "male" or "female"
        weight_kg: 体重(kg)
        height_cm: 身長(cm)
        age: 年齢（デフォルト30歳）

    Returns:
        BMR (kcal/日)
    """
    if gender == "male":
        return 88.362 + (13.397 * weight_kg) + (4.799 * height_cm) - (5.677 * age)
    else:
        return 447.593 + (9.247 * weight_kg) + (3.098 * height_cm) - (4.330 * age)


def calculate_daily_calories(
    gender: str = DEFAULT_GENDER,
    weight_kg: float = DEFAULT_WEIGHT_KG,
    height_cm: float = DEFAULT_HEIGHT_CM,
    activity_level: str = DEFAULT_ACTIVITY_LEVEL,
    age: int = 30,
) -> float:
    """
    1日の推奨カロリー摂取量を計算する。

    Returns:
        推奨カロリー (kcal/日)
    """
    bmr = calculate_bmr(gender, weight_kg, height_cm, age)
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
    return round(bmr * multiplier, 0)


def validate_config() -> list[str]:
    """
    必要な設定値が揃っているか検証する。

    Returns:
        エラーメッセージのリスト（空なら問題なし）
    """
    errors = []
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY が設定されていません")
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN が設定されていません")
    if not SUPABASE_URL:
        errors.append("SUPABASE_URL が設定されていません")
    if not SUPABASE_KEY:
        errors.append("SUPABASE_KEY が設定されていません")
    return errors


# 起動時に設定を検証
if __name__ == "__main__":
    errors = validate_config()
    if errors:
        print("⚠️ 設定エラー:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("✅ すべての設定が正常です")
        cal = calculate_daily_calories()
        print(f"📊 デフォルト推奨カロリー: {cal} kcal/日")
