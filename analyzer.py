"""
Diet Analyze - AI栄養分析エンジン

Gemini API を使用してテキストから食事内容を分析し、
栄養成分を構造化データとして返す。
"""

import os
import json
import logging
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ===== Pydantic モデル（Gemini構造化出力用） =====


class FoodItem(BaseModel):
    """個別の食品アイテムの栄養成分"""
    food_name: str = Field(description="食品名（日本語）")
    meal_type: str = Field(description="食事の種類: 朝食/昼食/夕食/間食")
    calories: float = Field(description="カロリー (kcal)")
    protein: float = Field(description="タンパク質 (g)")
    fat: float = Field(description="脂質 (g)")
    carbohydrates: float = Field(description="炭水化物 (g)")
    fiber: float = Field(description="食物繊維 (g)")
    sugar: float = Field(description="糖質 (g)")
    sodium: float = Field(description="ナトリウム (mg)")
    calcium: float = Field(description="カルシウム (mg)")
    iron: float = Field(description="鉄分 (mg)")
    vitamin_a: float = Field(description="ビタミンA (μg)")
    vitamin_c: float = Field(description="ビタミンC (mg)")
    confidence: str = Field(description="推定精度: 高/中/低")


class MealAnalysis(BaseModel):
    """食事分析の結果"""
    items: list[FoodItem] = Field(description="分析された個別食品リスト")
    total_calories: float = Field(description="合計カロリー (kcal)")
    summary: str = Field(description="栄養に関する一言アドバイス（日本語）")


# ===== 分析プロンプト =====

ANALYSIS_PROMPT = """あなたは日本の食品栄養データに精通した栄養分析AIです。

ユーザーが入力したテキストから食事内容を特定し、一般的な1人前の量を基に栄養成分を推定してください。

## ルール
1. 複数の食品が含まれる場合は、個別に分析してください
2. 量が明記されていない場合は、日本の一般的な1人前の量で計算してください
3. 「大盛り」「少なめ」などの記述があれば量を調整してください
4. コンビニ商品や外食チェーンの場合は、一般的な栄養データを参考にしてください
5. 栄養成分が不明な場合でも、類似食品から合理的に推定してください
6. confidence（推定精度）は以下の基準で判定：
   - 高: 一般的な食品で栄養データが確立されている
   - 中: 調理法や量に幅がある
   - 低: 特殊な料理や情報が少ない
7. meal_type は時間帯が不明な場合は「食事」としてください
8. summary は健康的なアドバイスを1-2文で簡潔に

## ユーザーの入力テキスト:
{user_text}
"""


# ===== Gemini クライアント =====

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Gemini API クライアントを取得する（シングルトン）"""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        _client = genai.Client(api_key=api_key)
    return _client


def analyze_meal(user_text: str, model: str = "gemini-2.5-flash") -> MealAnalysis:
    """
    ユーザーのテキストから食事内容を分析する。

    Args:
        user_text: ユーザーが入力した食事テキスト（例: "牛丼とサラダとみそ汁"）
        model: 使用するGeminiモデル

    Returns:
        MealAnalysis: 構造化された分析結果
    """
    client = _get_client()

    prompt = ANALYSIS_PROMPT.format(user_text=user_text)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=MealAnalysis,
                temperature=0.3,  # 低めにして一貫性を高める
            ),
        )

        # 構造化データとしてパース
        if response.parsed:
            return response.parsed

        # フォールバック: テキストからJSONをパース
        if response.text:
            data = json.loads(response.text)
            return MealAnalysis(**data)

        raise ValueError("Gemini API からの応答が空です")

    except Exception as e:
        logger.error(f"食事分析エラー: {e}")
        # エラー時のフォールバック
        return MealAnalysis(
            items=[
                FoodItem(
                    food_name=user_text,
                    meal_type="食事",
                    calories=0,
                    protein=0,
                    fat=0,
                    carbohydrates=0,
                    fiber=0,
                    sugar=0,
                    sodium=0,
                    calcium=0,
                    iron=0,
                    vitamin_a=0,
                    vitamin_c=0,
                    confidence="低",
                )
            ],
            total_calories=0,
            summary=f"分析エラー: {str(e)[:100]}",
        )


def format_meal_result(analysis: MealAnalysis, daily_total: float = 0, daily_target: float = 2000) -> str:
    """
    分析結果をTelegram向けのテキストメッセージにフォーマットする。

    Args:
        analysis: Gemini分析結果
        daily_total: 本日のこれまでの合計カロリー
        daily_target: 1日の目標カロリー

    Returns:
        フォーマットされたメッセージ文字列
    """
    lines = ["🍽️ 食事を記録しました！\n"]

    for item in analysis.items:
        lines.append(f"📝 {item.food_name}")
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(f"🔥 カロリー:    {item.calories:,.0f} kcal")
        lines.append(f"🥩 タンパク質:  {item.protein:,.1f} g")
        lines.append(f"🧈 脂質:        {item.fat:,.1f} g")
        lines.append(f"🍚 炭水化物:    {item.carbohydrates:,.1f} g")
        lines.append(f"🌿 食物繊維:    {item.fiber:,.1f} g")

        if item.sugar > 0:
            lines.append(f"🍬 糖質:        {item.sugar:,.1f} g")
        if item.calcium > 0:
            lines.append(f"🦴 カルシウム:  {item.calcium:,.0f} mg")
        if item.iron > 0:
            lines.append(f"⚙️ 鉄分:        {item.iron:,.1f} mg")
        if item.vitamin_c > 0:
            lines.append(f"🍊 ビタミンC:   {item.vitamin_c:,.1f} mg")

        lines.append(f"📊 信頼度: {item.confidence}")
        lines.append("")

    # 今日の合計
    new_total = daily_total + analysis.total_calories
    progress = min(new_total / daily_target, 1.0) if daily_target > 0 else 0
    bar_filled = int(progress * 15)
    bar_empty = 15 - bar_filled
    progress_bar = "▓" * bar_filled + "░" * bar_empty
    percent = progress * 100

    lines.append(f"📊 今日の合計: {new_total:,.0f} / {daily_target:,.0f} kcal")
    lines.append(f"{progress_bar} {percent:.0f}%")

    if percent > 100:
        lines.append("⚠️ 目標カロリーを超過しています！")

    lines.append(f"\n💬 {analysis.summary}")

    return "\n".join(lines)


# テスト用
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_text = "おにぎり2個と唐揚げ弁当"
    print(f"分析中: {test_text}")
    result = analyze_meal(test_text)
    print(format_meal_result(result))
