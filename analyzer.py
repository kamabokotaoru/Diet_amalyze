"""
Diet Analyze - AI栄養分析エンジン

Gemini API を使用してテキストから食事内容を分析し、
栄養成分を構造化データとして返す。
あすけんレベルの詳細な栄養素を記録。
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
    """個別の食品アイテムの栄養成分（あすけん準拠）"""
    food_name: str = Field(description="食品名（日本語）")
    meal_type: str = Field(description="食事の種類: 朝食/昼食/夕食/間食")
    # === 主要栄養素 ===
    calories: float = Field(description="カロリー (kcal)")
    protein: float = Field(description="タンパク質 (g)")
    fat: float = Field(description="脂質 (g)")
    carbohydrates: float = Field(description="炭水化物 (g)")
    fiber: float = Field(description="食物繊維 (g)")
    sugar: float = Field(description="糖質 (g)")
    saturated_fat: float = Field(description="飽和脂肪酸 (g)")
    cholesterol: float = Field(description="コレステロール (mg)")
    salt_equivalent: float = Field(description="食塩相当量 (g)")
    # === ミネラル ===
    calcium: float = Field(description="カルシウム (mg)")
    iron: float = Field(description="鉄分 (mg)")
    magnesium: float = Field(description="マグネシウム (mg)")
    zinc: float = Field(description="亜鉛 (mg)")
    potassium: float = Field(description="カリウム (mg)")
    # === ビタミン ===
    vitamin_a: float = Field(description="ビタミンA (μg RAE)")
    vitamin_b1: float = Field(description="ビタミンB1 (mg)")
    vitamin_b2: float = Field(description="ビタミンB2 (mg)")
    vitamin_b6: float = Field(description="ビタミンB6 (mg)")
    vitamin_b12: float = Field(description="ビタミンB12 (μg)")
    vitamin_c: float = Field(description="ビタミンC (mg)")
    vitamin_d: float = Field(description="ビタミンD (μg)")
    vitamin_e: float = Field(description="ビタミンE (mg)")
    vitamin_k: float = Field(description="ビタミンK (μg)")
    folate: float = Field(description="葉酸 (μg)")
    # === メタ ===
    confidence: str = Field(description="推定精度: 高/中/低")


class MealAnalysis(BaseModel):
    """食事分析の結果"""
    items: list[FoodItem] = Field(description="分析された個別食品リスト")
    total_calories: float = Field(description="合計カロリー (kcal)")
    meal_comment: str = Field(description="この食事に対する栄養アドバイス（日本語、2-3文）")


class DailySummaryAnalysis(BaseModel):
    """1日の総評"""
    total_calories: float = Field(description="1日の合計カロリー")
    calorie_evaluation: str = Field(description="カロリーの評価（多い/適正/少ない）")
    pfc_balance: str = Field(description="PFCバランスの評価")
    good_points: list[str] = Field(description="良かった点（2-3個）")
    improvement_points: list[str] = Field(description="改善点（2-3個）")
    lacking_nutrients: list[str] = Field(description="不足している栄養素リスト")
    excessive_nutrients: list[str] = Field(description="過剰な栄養素リスト")
    tomorrow_advice: str = Field(description="明日の食事へのアドバイス（2-3文）")
    overall_score: int = Field(description="今日の食事スコア（0-100点）")
    overall_comment: str = Field(description="総評コメント（3-4文）")


# ===== 食事タイミング検出 =====

MEAL_TYPE_KEYWORDS = {
    "朝食": ["朝", "あさ", "朝ごはん", "朝食", "朝飯", "モーニング", "breakfast"],
    "昼食": ["昼", "ひる", "昼ごはん", "昼食", "昼飯", "ランチ", "lunch"],
    "夕食": ["夜", "よる", "晩", "ばん", "夕", "夕ごはん", "夕食", "夕飯", "晩ごはん", "晩飯", "ディナー", "dinner"],
    "間食": ["間食", "おやつ", "おかし", "お菓子", "スナック", "snack", "デザート"],
}


def detect_meal_type(text: str) -> str | None:
    """テキストから食事タイミングを検出する"""
    text_lower = text.lower().strip()
    for meal_type, keywords in MEAL_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if text_lower.startswith(keyword):
                return meal_type
    return None


def strip_meal_prefix(text: str) -> str:
    """テキストから食事タイミングのプレフィックスを除去する"""
    text = text.strip()
    for keywords in MEAL_TYPE_KEYWORDS.values():
        for keyword in keywords:
            if text.lower().startswith(keyword):
                remainder = text[len(keyword):].lstrip("：:　 ,、")
                if remainder:
                    return remainder
    return text


# ===== 分析プロンプト =====

ANALYSIS_PROMPT = """あなたは日本の食品栄養データに精通した栄養分析AIです（あすけんのような精度を目指します）。

ユーザーが入力したテキストから食事内容を特定し、日本食品標準成分表に基づいて栄養成分を推定してください。

## ルール
1. 複数の食品が含まれる場合は、個別に分析してください
2. 量が明記されていない場合は、日本の一般的な1人前の量で計算してください
3. 「大盛り」「少なめ」などの記述があれば量を調整してください
4. コンビニ商品や外食チェーンの場合は、一般的な栄養データを参考にしてください
5. 栄養成分が不明な場合でも、類似食品から合理的に推定してください
6. 食事タイミング: {meal_type}
7. confidence（推定精度）は以下の基準で判定：
   - 高: 一般的な食品で栄養データが確立されている
   - 中: 調理法や量に幅がある
   - 低: 特殊な料理や情報が少ない
8. meal_comment には、この食事の栄養バランスについて具体的なアドバイスを2-3文で書いてください
   例: 「タンパク質が不足しています。卵やヨーグルトを追加すると良いでしょう。食物繊維もサラダで補えると理想的です。」

## 記録する栄養素（すべて必須）
- 主要: カロリー、タンパク質、脂質、炭水化物、食物繊維、糖質、飽和脂肪酸、コレステロール、食塩相当量
- ミネラル: カルシウム、鉄分、マグネシウム、亜鉛、カリウム
- ビタミン: A、B1、B2、B6、B12、C、D、E、K、葉酸

## ユーザーの入力テキスト:
{user_text}
"""

IMAGE_ANALYSIS_PROMPT = """あなたは日本の食品栄養データに精通した栄養分析AIです（あすけんのような精度を目指します）。

この食事の写真を分析し、写っている食品を特定して、日本食品標準成分表に基づいて栄養成分を推定してください。

## ルール
1. 写真に写っている食品をすべて個別に特定してください
2. 量は写真から見た目で推定してください（皿のサイズ、盛り付け量を参考に）
3. 料理名が分かる場合は日本語の一般的な名称を使用してください
4. 栄養成分が不明な場合でも、類似食品から合理的に推定してください
5. 食事タイミング: {meal_type}
6. confidence（推定精度）は以下の基準で判定：
   - 高: 明確に特定できる一般的な食品
   - 中: 料理は特定できるが量や調理法に幅がある
   - 低: 写真が不鮮明、または特殊な料理
7. meal_comment には、この食事の栄養バランスについて具体的なアドバイスを2-3文で書いてください

## 記録する栄養素（すべて必須）
- 主要: カロリー、タンパク質、脂質、炭水化物、食物繊維、糖質、飽和脂肪酸、コレステロール、食塩相当量
- ミネラル: カルシウム、鉄分、マグネシウム、亜鉛、カリウム
- ビタミン: A、B1、B2、B6、B12、C、D、E、K、葉酸
{caption_text}
"""

DAILY_SUMMARY_PROMPT = """あなたは管理栄養士のように、1日の食事を総合的に評価するAIです。

以下の1日の食事記録を分析し、詳細な総評を行ってください。

## 評価基準（成人男性、168cm基準）
- 推奨カロリー: {target_calories} kcal/日
- タンパク質: 体重×1.0-1.5g
- 脂質: 総カロリーの20-30%
- 炭水化物: 総カロリーの50-65%
- 食物繊維: 21g以上
- カルシウム: 800mg
- 鉄: 7.5mg
- ビタミンA: 900μg
- ビタミンB1: 1.4mg
- ビタミンB2: 1.6mg
- ビタミンC: 100mg
- ビタミンD: 8.5μg
- 食塩相当量: 7.5g未満

## 今日の食事記録:
{meals_text}

## 栄養合計:
{nutrition_summary}

スコアは、カロリーの適正さ(30%)、PFCバランス(25%)、ビタミン・ミネラルの充足度(25%)、食事の多様性(20%)で評価してください。
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


def _make_error_result(label: str, meal_type: str, error: str) -> MealAnalysis:
    """分析エラー時のフォールバック結果を作成する"""
    return MealAnalysis(
        items=[
            FoodItem(
                food_name=label,
                meal_type=meal_type or "食事",
                calories=0, protein=0, fat=0, carbohydrates=0,
                fiber=0, sugar=0, saturated_fat=0, cholesterol=0,
                salt_equivalent=0, calcium=0, iron=0, magnesium=0,
                zinc=0, potassium=0, vitamin_a=0, vitamin_b1=0,
                vitamin_b2=0, vitamin_b6=0, vitamin_b12=0, vitamin_c=0,
                vitamin_d=0, vitamin_e=0, vitamin_k=0, folate=0,
                confidence="低",
            )
        ],
        total_calories=0,
        meal_comment=f"分析エラー: {error[:100]}",
    )


def analyze_meal(user_text: str, model: str = "gemini-2.5-flash") -> MealAnalysis:
    """
    ユーザーのテキストから食事内容を分析する。

    Args:
        user_text: ユーザーが入力した食事テキスト
        model: 使用するGeminiモデル

    Returns:
        MealAnalysis: 構造化された分析結果
    """
    client = _get_client()

    # 食事タイミングを検出
    detected_type = detect_meal_type(user_text)
    meal_type_hint = detected_type if detected_type else "不明（テキストから推定してください）"

    # 食事プレフィックスを除去したテキスト
    clean_text = strip_meal_prefix(user_text)

    prompt = ANALYSIS_PROMPT.format(
        user_text=clean_text,
        meal_type=meal_type_hint,
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=MealAnalysis,
                temperature=0.3,
            ),
        )

        if response.parsed:
            result = response.parsed
        elif response.text:
            data = json.loads(response.text)
            result = MealAnalysis(**data)
        else:
            raise ValueError("Gemini API からの応答が空です")

        # 検出した食事タイミングを上書き
        if detected_type:
            for item in result.items:
                item.meal_type = detected_type

        return result

    except Exception as e:
        logger.error(f"食事分析エラー: {e}")
        return _make_error_result(user_text, detected_type, str(e))


def analyze_meal_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    caption: str = "",
    model: str = "gemini-2.5-flash",
) -> MealAnalysis:
    """
    食事の写真から栄養成分を分析する。

    Args:
        image_bytes: 画像のバイナリデータ
        mime_type: 画像のMIMEタイプ (image/jpeg, image/png, etc.)
        caption: ユーザーが写真と一緒に送ったテキスト（食事タイミング等）
        model: 使用するGeminiモデル

    Returns:
        MealAnalysis: 構造化された分析結果
    """
    client = _get_client()

    # キャプションから食事タイミングを検出
    detected_type = detect_meal_type(caption) if caption else None
    meal_type_hint = detected_type if detected_type else "不明（写真の内容から推定してください）"

    # キャプション処理
    caption_text = ""
    if caption:
        clean_caption = strip_meal_prefix(caption)
        if clean_caption:
            caption_text = f"\n## ユーザーからの補足:\n{clean_caption}"

    prompt = IMAGE_ANALYSIS_PROMPT.format(
        meal_type=meal_type_hint,
        caption_text=caption_text,
    )

    try:
        # 画像 + テキストを送信
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        response = client.models.generate_content(
            model=model,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=MealAnalysis,
                temperature=0.3,
            ),
        )

        if response.parsed:
            result = response.parsed
        elif response.text:
            data = json.loads(response.text)
            result = MealAnalysis(**data)
        else:
            raise ValueError("Gemini API からの応答が空です")

        # 検出した食事タイミングを上書き
        if detected_type:
            for item in result.items:
                item.meal_type = detected_type

        return result

    except Exception as e:
        logger.error(f"画像分析エラー: {e}")
        return _make_error_result("写真の食事", detected_type, str(e))


def analyze_daily_summary(
    meals: list[dict],
    target_calories: float = 2200,
    model: str = "gemini-2.5-flash",
) -> DailySummaryAnalysis:
    """
    1日の食事を総合評価する。

    Args:
        meals: その日の食事記録リスト
        target_calories: 目標カロリー
        model: Geminiモデル

    Returns:
        DailySummaryAnalysis: 総評結果
    """
    client = _get_client()

    # 食事テキストを整形
    meals_lines = []
    totals = {}
    for meal in meals:
        mt = meal.get("meal_type", "不明")
        fn = meal.get("food_name", "")
        cal = meal.get("calories", 0)
        meals_lines.append(f"  [{mt}] {fn} ({cal:.0f} kcal)")

        # 合計計算
        for key in ["calories", "protein", "fat", "carbohydrates", "fiber",
                     "sugar", "calcium", "iron", "vitamin_a", "vitamin_b1",
                     "vitamin_b2", "vitamin_c", "vitamin_d", "salt_equivalent",
                     "magnesium", "zinc", "potassium", "folate"]:
            totals[key] = totals.get(key, 0) + (meal.get(key, 0) or 0)

    meals_text = "\n".join(meals_lines) if meals_lines else "記録なし"

    # 栄養合計テキスト
    nutrition_lines = [
        f"カロリー: {totals.get('calories', 0):.0f} kcal",
        f"タンパク質: {totals.get('protein', 0):.1f} g",
        f"脂質: {totals.get('fat', 0):.1f} g",
        f"炭水化物: {totals.get('carbohydrates', 0):.1f} g",
        f"食物繊維: {totals.get('fiber', 0):.1f} g",
        f"食塩相当量: {totals.get('salt_equivalent', 0):.1f} g",
        f"カルシウム: {totals.get('calcium', 0):.0f} mg",
        f"鉄: {totals.get('iron', 0):.1f} mg",
        f"ビタミンA: {totals.get('vitamin_a', 0):.0f} μg",
        f"ビタミンC: {totals.get('vitamin_c', 0):.0f} mg",
        f"ビタミンD: {totals.get('vitamin_d', 0):.1f} μg",
    ]
    nutrition_summary = "\n".join(nutrition_lines)

    prompt = DAILY_SUMMARY_PROMPT.format(
        target_calories=target_calories,
        meals_text=meals_text,
        nutrition_summary=nutrition_summary,
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DailySummaryAnalysis,
                temperature=0.4,
            ),
        )

        if response.parsed:
            return response.parsed
        elif response.text:
            data = json.loads(response.text)
            return DailySummaryAnalysis(**data)
        else:
            raise ValueError("応答が空です")

    except Exception as e:
        logger.error(f"日次総評エラー: {e}")
        return DailySummaryAnalysis(
            total_calories=totals.get("calories", 0),
            calorie_evaluation="不明",
            pfc_balance="不明",
            good_points=["分析エラー"],
            improvement_points=[str(e)[:100]],
            lacking_nutrients=[],
            excessive_nutrients=[],
            tomorrow_advice="再度お試しください。",
            overall_score=0,
            overall_comment=f"エラー: {str(e)[:100]}",
        )


def format_meal_result(analysis: MealAnalysis, daily_total: float = 0, daily_target: float = 2000) -> str:
    """分析結果をTelegram向けにフォーマットする"""
    lines = ["🍽️ 食事を記録しました！\n"]

    for item in analysis.items:
        lines.append(f"📝 {item.food_name}  [{item.meal_type}]")
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(f"🔥 カロリー:    {item.calories:,.0f} kcal")
        lines.append(f"🥩 タンパク質:  {item.protein:,.1f} g")
        lines.append(f"🧈 脂質:        {item.fat:,.1f} g")
        lines.append(f"🍚 炭水化物:    {item.carbohydrates:,.1f} g")
        lines.append(f"🌿 食物繊維:    {item.fiber:,.1f} g")
        lines.append(f"🧂 食塩:        {item.salt_equivalent:,.1f} g")

        # ミネラル
        minerals = []
        if item.calcium > 0:
            minerals.append(f"Ca:{item.calcium:.0f}")
        if item.iron > 0:
            minerals.append(f"Fe:{item.iron:.1f}")
        if item.magnesium > 0:
            minerals.append(f"Mg:{item.magnesium:.0f}")
        if item.zinc > 0:
            minerals.append(f"Zn:{item.zinc:.1f}")
        if minerals:
            lines.append(f"💎 ミネラル(mg): {' / '.join(minerals)}")

        # ビタミン
        vitamins = []
        if item.vitamin_a > 0:
            vitamins.append(f"A:{item.vitamin_a:.0f}μg")
        if item.vitamin_b1 > 0:
            vitamins.append(f"B1:{item.vitamin_b1:.2f}")
        if item.vitamin_b2 > 0:
            vitamins.append(f"B2:{item.vitamin_b2:.2f}")
        if item.vitamin_c > 0:
            vitamins.append(f"C:{item.vitamin_c:.0f}")
        if item.vitamin_d > 0:
            vitamins.append(f"D:{item.vitamin_d:.1f}μg")
        if vitamins:
            lines.append(f"💊 ビタミン: {' / '.join(vitamins)}")

        lines.append(f"📊 信頼度: {item.confidence}")
        lines.append("")

    # 食事ごとのコメント
    lines.append(f"💬 {analysis.meal_comment}")
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

    return "\n".join(lines)


def format_daily_summary(summary: DailySummaryAnalysis, target: float = 2200) -> str:
    """1日の総評をTelegram向けにフォーマットする"""
    # スコアに応じた絵文字
    score = summary.overall_score
    if score >= 80:
        grade = "🌟 S"
    elif score >= 60:
        grade = "✨ A"
    elif score >= 40:
        grade = "👍 B"
    else:
        grade = "💪 C"

    lines = [
        "📋 1日の食事総評",
        "━━━━━━━━━━━━━━━",
        "",
        f"🏆 今日のスコア: {score}/100 点 [{grade}]",
        "",
        f"🔥 カロリー: {summary.total_calories:,.0f} / {target:,.0f} kcal ({summary.calorie_evaluation})",
        f"⚖️ PFCバランス: {summary.pfc_balance}",
        "",
    ]

    # 良かった点
    lines.append("✅ 良かった点:")
    for point in summary.good_points:
        lines.append(f"  • {point}")
    lines.append("")

    # 改善点
    lines.append("📝 改善点:")
    for point in summary.improvement_points:
        lines.append(f"  • {point}")
    lines.append("")

    # 不足・過剰栄養素
    if summary.lacking_nutrients:
        lines.append(f"⚠️ 不足: {', '.join(summary.lacking_nutrients)}")
    if summary.excessive_nutrients:
        lines.append(f"🔴 過剰: {', '.join(summary.excessive_nutrients)}")
    lines.append("")

    # 明日へのアドバイス
    lines.append(f"🌅 明日のアドバイス:")
    lines.append(f"  {summary.tomorrow_advice}")
    lines.append("")

    # 総評
    lines.append(f"📖 総評:")
    lines.append(f"  {summary.overall_comment}")

    return "\n".join(lines)


# テスト用
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_text = "朝 トーストとバナナと牛乳"
    print(f"分析中: {test_text}")
    result = analyze_meal(test_text)
    print(format_meal_result(result))
