"""
Diet Analyze - Streamlit ダッシュボード

食事記録の可視化、PFCバランス分析、カロリー推移グラフを表示する
プレミアムなダッシュボード。Streamlit Community Cloud にデプロイ。
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# dashboard/ を sys.path の先頭に置き、ルートの同名モジュールより優先させる
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Streamlit Cloud の Secrets から環境変数を設定
if hasattr(st, "secrets"):
    for key in ["SUPABASE_URL", "SUPABASE_KEY", "GEMINI_API_KEY"]:
        if key in st.secrets:
            os.environ[key] = st.secrets[key]

import traceback as _traceback

_import_error = None
try:
    from database import (
        get_all_meals_range,
        get_all_user_profiles,
        get_daily_summary,
        get_meals_by_date,
        delete_meal,
    )
    from analyzer import analyze_meal
except Exception as _e:
    _import_error = f"{type(_e).__name__}: {_e}\n\n{_traceback.format_exc()}"

# ===== ページ設定 =====
st.set_page_config(
    page_title="Diet Analyze - 栄養ダッシュボード",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

if _import_error:
    st.error("Import failed — see details below")
    st.code(_import_error, language="text")
    st.stop()

# ===== カスタムCSS =====
st.markdown("""
<style>
    /* メトリックカードのスタイル */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(0, 230, 118, 0.2);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
    }

    div[data-testid="stMetric"] label {
        color: #a0a0a0 !important;
        font-size: 0.85rem !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #00E676 !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }

    /* サイドバー */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0a0f 0%, #1a1a2e 100%);
        border-right: 1px solid rgba(0, 230, 118, 0.15);
    }

    /* タブのスタイル */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: rgba(26, 26, 46, 0.8);
        border-radius: 8px;
        border: 1px solid rgba(0, 230, 118, 0.15);
        padding: 8px 20px;
    }

    .stTabs [aria-selected="true"] {
        background: rgba(0, 230, 118, 0.15) !important;
        border-color: #00E676 !important;
    }

    /* テーブルのスタイル */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }

    /* ヘッダー */
    h1 {
        background: linear-gradient(90deg, #00E676, #00BCD4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }

    h2, h3 {
        color: #e0e0e0 !important;
    }

    /* プログレスバー風 */
    .progress-container {
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
        height: 24px;
        overflow: hidden;
        margin: 8px 0;
    }
    .progress-bar {
        height: 100%;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: bold;
        color: #0a0a0f;
        transition: width 0.5s ease;
    }

    /* 区切り線 */
    hr {
        border-color: rgba(0, 230, 118, 0.15) !important;
    }
</style>
""", unsafe_allow_html=True)

# ===== 定数 =====
JST = timezone(timedelta(hours=9))


def today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


# ===== Plotly テンプレート =====
PLOTLY_TEMPLATE = {
    "layout": {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#e0e0e0", "family": "sans-serif"},
        "xaxis": {"gridcolor": "rgba(255,255,255,0.05)", "zerolinecolor": "rgba(255,255,255,0.1)"},
        "yaxis": {"gridcolor": "rgba(255,255,255,0.05)", "zerolinecolor": "rgba(255,255,255,0.1)"},
        "colorway": ["#00E676", "#00BCD4", "#FF6B6B", "#FFD93D", "#6C63FF", "#FF9F43"],
    }
}


def make_progress_bar(current: float, target: float, color: str = "#00E676") -> str:
    """HTMLプログレスバーを生成"""
    pct = min(current / target * 100, 100) if target > 0 else 0
    bar_color = color if pct <= 100 else "#FF6B6B"
    return f"""
    <div class="progress-container">
        <div class="progress-bar" style="width: {pct}%; background: linear-gradient(90deg, {bar_color}, {bar_color}88);">
            {pct:.0f}%
        </div>
    </div>
    """


# =============================================================
# サイドバー
# =============================================================

with st.sidebar:
    st.markdown("# 🥗 Diet Analyze")

    # 更新ボタン
    if st.button("🔄 データを更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # 自動更新（60秒ごと）
    st.markdown(
        """<meta http-equiv="refresh" content="60">""",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # 日付選択
    selected_date = st.date_input(
        "📅 日付選択",
        value=datetime.now(JST).date(),
        max_value=datetime.now(JST).date(),
    )
    date_str = selected_date.isoformat()

    st.markdown("---")

    # 期間フィルター
    period = st.radio(
        "📊 表示期間",
        options=["7日間", "14日間", "30日間"],
        index=0,
        horizontal=True,
    )
    period_days = {"7日間": 7, "14日間": 14, "30日間": 30}[period]

    st.markdown("---")

    # プロファイル表示
    profiles = []
    try:
        profiles = get_all_user_profiles()
    except Exception:
        pass

    if profiles:
        profile = profiles[0]  # 個人利用なので最初のユーザー
        target = profile.get("daily_calorie_target", 2200)
        st.markdown("### 👤 プロファイル")
        gender_jp = "男性" if profile.get("gender") == "male" else "女性"
        st.markdown(f"**性別:** {gender_jp}")
        st.markdown(f"**身長:** {profile.get('height_cm', 168)} cm")
        st.markdown(f"**体重:** {profile.get('weight_kg', 70)} kg")
        st.markdown(f"**活動量:** {profile.get('activity_level', 'moderate')}")
        bmi = profile.get("weight_kg", 70) / (profile.get("height_cm", 168) / 100) ** 2
        st.markdown(f"**BMI:** {bmi:.1f}")
        st.markdown(f"**🎯 目標:** {target:,.0f} kcal/日")
    else:
        target = 2200
        st.info("Telegramでボットに /start を送信してプロファイルを作成してください。")

    st.markdown("---")

    # 手動入力
    st.markdown("### ✏️ 手動入力")
    manual_text = st.text_area(
        "食事内容を入力",
        placeholder="例: 牛丼とみそ汁",
        height=80,
    )
    if st.button("📝 記録する", use_container_width=True, type="primary"):
        if manual_text.strip():
            with st.spinner("🔄 AI分析中..."):
                try:
                    result = analyze_meal(manual_text.strip())
                    # ダッシュボードからの入力は user_id=0 で保存
                    from database import save_meal as db_save
                    from database import upsert_user_profile
                    # ダッシュボードユーザーのプロファイルを作成
                    upsert_user_profile(0, username="dashboard", daily_calorie_target=target)
                    for item in result.items:
                        item_dict = item.model_dump()
                        db_save(
                            telegram_user_id=profiles[0]["telegram_user_id"] if profiles else 0,
                            date=date_str,
                            original_text=manual_text,
                            food_name=item_dict.pop("food_name"),
                            meal_type=item_dict.pop("meal_type"),
                            confidence=item_dict.pop("confidence"),
                            **item_dict,
                        )
                    st.success(f"✅ {len(result.items)}品を記録しました！")
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ エラー: {e}")
        else:
            st.warning("テキストを入力してください")


# =============================================================
# メインコンテンツ
# =============================================================

st.markdown("# 🥗 Diet Analyze Dashboard")

# ===== タブ =====
tab_today, tab_trend, tab_records = st.tabs(["📊 今日のサマリー", "📈 トレンド", "📋 食事記録"])


# ----- タブ1: 今日のサマリー -----
with tab_today:
    user_id = profiles[0]["telegram_user_id"] if profiles else None

    empty_summary = {"meal_count": 0}
    for _f in ["calories","protein","fat","carbs","fiber","sugar","sodium",
               "calcium","iron","magnesium","zinc","potassium","salt_equivalent",
               "vitamin_a","vitamin_b1","vitamin_b2","vitamin_b6","vitamin_b12",
               "vitamin_c","vitamin_d","vitamin_e","vitamin_k","folate",
               "saturated_fat","cholesterol","carbohydrates"]:
        empty_summary[f"total_{_f}"] = 0

    try:
        summary = get_daily_summary(user_id, date_str) if user_id else empty_summary.copy()
        meals_today = get_meals_by_date(user_id, date_str) if user_id else []
    except Exception:
        summary = empty_summary.copy()
        meals_today = []

    st.markdown(f"### 📅 {date_str}")

    # KPI カード
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 カロリー", f"{summary['total_calories']:,.0f} kcal")
    with col2:
        st.metric("🥩 タンパク質", f"{summary['total_protein']:,.1f} g")
    with col3:
        st.metric("🧈 脂質", f"{summary['total_fat']:,.1f} g")
    with col4:
        st.metric("🍚 炭水化物", f"{summary['total_carbs']:,.1f} g")

    # カロリー進捗バー
    st.markdown("#### 🎯 目標に対する進捗")
    st.markdown(
        make_progress_bar(summary["total_calories"], target),
        unsafe_allow_html=True,
    )
    remaining = target - summary["total_calories"]
    if remaining > 0:
        st.caption(f"あと {remaining:,.0f} kcal")
    else:
        st.caption(f"⚠️ {abs(remaining):,.0f} kcal 超過")

    st.markdown("---")

    # PFCバランス (ドーナツチャート)
    col_pfc, col_micro = st.columns(2)

    with col_pfc:
        st.markdown("#### 🥗 PFCバランス")
        p = summary["total_protein"]
        f = summary["total_fat"]
        c = summary["total_carbs"]

        if p + f + c > 0:
            fig_pfc = go.Figure(data=[go.Pie(
                labels=["タンパク質", "脂質", "炭水化物"],
                values=[p * 4, f * 9, c * 4],  # カロリーベース
                hole=0.55,
                marker=dict(colors=["#00E676", "#FF6B6B", "#FFD93D"]),
                textinfo="label+percent",
                textfont=dict(size=13, color="#e0e0e0"),
                hovertemplate="<b>%{label}</b><br>%{value:.0f} kcal<br>%{percent}<extra></extra>",
            )])
            fig_pfc.update_layout(
                **PLOTLY_TEMPLATE["layout"],
                showlegend=False,
                height=300,
                margin=dict(t=10, b=10, l=10, r=10),
                annotations=[dict(
                    text=f"{summary['total_calories']:,.0f}<br>kcal",
                    x=0.5, y=0.5, font_size=18, font_color="#00E676",
                    showarrow=False,
                )],
            )
            st.plotly_chart(fig_pfc, use_container_width=True)
        else:
            st.info("データがありません")

    with col_micro:
        st.markdown("#### 🧪 ビタミン・ミネラル")
        micro_data = {
            "栄養素": [
                "食物繊維", "食塩相当量",
                "カルシウム", "鉄分", "マグネシウム", "亜鉛", "カリウム",
                "ビタミンA", "ビタミンB1", "ビタミンB2", "ビタミンB6", "ビタミンB12",
                "ビタミンC", "ビタミンD", "ビタミンE", "ビタミンK", "葉酸",
            ],
            "摂取量": [
                summary.get("total_fiber", 0), summary.get("total_salt_equivalent", 0),
                summary.get("total_calcium", 0), summary.get("total_iron", 0),
                summary.get("total_magnesium", 0), summary.get("total_zinc", 0),
                summary.get("total_potassium", 0),
                summary.get("total_vitamin_a", 0), summary.get("total_vitamin_b1", 0),
                summary.get("total_vitamin_b2", 0), summary.get("total_vitamin_b6", 0),
                summary.get("total_vitamin_b12", 0), summary.get("total_vitamin_c", 0),
                summary.get("total_vitamin_d", 0), summary.get("total_vitamin_e", 0),
                summary.get("total_vitamin_k", 0), summary.get("total_folate", 0),
            ],
            "単位": ["g", "g", "mg", "mg", "mg", "mg", "mg",
                  "μg", "mg", "mg", "mg", "μg", "mg", "μg", "mg", "μg", "μg"],
            "目安": [21, 7.5, 800, 7.5, 370, 11, 2500,
                   900, 1.4, 1.6, 1.4, 2.4, 100, 8.5, 6.0, 150, 240],
        }
        df_micro = pd.DataFrame(micro_data)
        df_micro["達成率"] = (df_micro["摂取量"] / df_micro["目安"] * 100).round(0).astype(int).astype(str) + "%"
        df_micro["表示"] = df_micro["摂取量"].round(1).astype(str) + " " + df_micro["単位"]
        st.dataframe(
            df_micro[["栄養素", "表示", "目安", "達成率"]].set_index("栄養素"),
            use_container_width=True,
            height=500,
        )

    # 今日の食事リスト
    if meals_today:
        st.markdown("---")
        st.markdown("#### 🍽️ 食事一覧")
        for meal in meals_today:
            with st.container():
                col_name, col_cal, col_p, col_f, col_c = st.columns([3, 1.5, 1, 1, 1])
                with col_name:
                    st.markdown(f"**{meal.get('food_name', '')}**")
                    st.caption(f"{meal.get('meal_type', '')} | 信頼度: {meal.get('confidence', '')}")
                with col_cal:
                    st.markdown(f"🔥 **{meal.get('calories', 0):,.0f}** kcal")
                with col_p:
                    st.markdown(f"P: {meal.get('protein', 0):,.1f}g")
                with col_f:
                    st.markdown(f"F: {meal.get('fat', 0):,.1f}g")
                with col_c:
                    st.markdown(f"C: {meal.get('carbohydrates', 0):,.1f}g")


# ----- タブ2: トレンド -----
with tab_trend:
    st.markdown("### 📈 カロリー推移")

    try:
        end_date = date_str
        start_date = (selected_date - timedelta(days=period_days - 1)).isoformat()
        all_meals = get_all_meals_range(user_id, start_date, end_date) if user_id else []
    except Exception:
        all_meals = []

    if all_meals:
        df = pd.DataFrame(all_meals)
        df["calories"] = pd.to_numeric(df["calories"], errors="coerce").fillna(0)
        df["protein"] = pd.to_numeric(df["protein"], errors="coerce").fillna(0)
        df["fat"] = pd.to_numeric(df["fat"], errors="coerce").fillna(0)
        df["carbohydrates"] = pd.to_numeric(df["carbohydrates"], errors="coerce").fillna(0)

        # 日別集計
        daily = df.groupby("date").agg(
            total_calories=("calories", "sum"),
            total_protein=("protein", "sum"),
            total_fat=("fat", "sum"),
            total_carbs=("carbohydrates", "sum"),
            meal_count=("id", "count"),
        ).reset_index()
        daily = daily.sort_values("date")

        # カロリー推移グラフ
        fig_cal = go.Figure()
        fig_cal.add_trace(go.Bar(
            x=daily["date"],
            y=daily["total_calories"],
            marker=dict(
                color=[
                    "#00E676" if c <= target else "#FF6B6B"
                    for c in daily["total_calories"]
                ],
                opacity=0.8,
            ),
            name="カロリー",
            hovertemplate="<b>%{x}</b><br>%{y:,.0f} kcal<extra></extra>",
        ))
        fig_cal.add_hline(
            y=target, line_dash="dash", line_color="#FFD93D",
            annotation_text=f"目標: {target:,.0f} kcal",
            annotation_font_color="#FFD93D",
        )
        fig_cal.update_layout(
            **PLOTLY_TEMPLATE["layout"],
            height=350,
            margin=dict(t=30, b=40, l=50, r=20),
            yaxis_title="カロリー (kcal)",
            showlegend=False,
        )
        st.plotly_chart(fig_cal, use_container_width=True)

        # PFC推移（積み上げエリアチャート）
        st.markdown("### 🥗 PFCバランス推移")
        fig_pfc = go.Figure()
        fig_pfc.add_trace(go.Scatter(
            x=daily["date"], y=daily["total_protein"] * 4,
            mode="lines", name="タンパク質",
            line=dict(color="#00E676", width=2),
            fill="tonexty", fillcolor="rgba(0,230,118,0.1)",
            stackgroup="pfc",
        ))
        fig_pfc.add_trace(go.Scatter(
            x=daily["date"], y=daily["total_fat"] * 9,
            mode="lines", name="脂質",
            line=dict(color="#FF6B6B", width=2),
            fill="tonexty", fillcolor="rgba(255,107,107,0.1)",
            stackgroup="pfc",
        ))
        fig_pfc.add_trace(go.Scatter(
            x=daily["date"], y=daily["total_carbs"] * 4,
            mode="lines", name="炭水化物",
            line=dict(color="#FFD93D", width=2),
            fill="tonexty", fillcolor="rgba(255,217,61,0.1)",
            stackgroup="pfc",
        ))
        fig_pfc.update_layout(
            **PLOTLY_TEMPLATE["layout"],
            height=350,
            margin=dict(t=30, b=40, l=50, r=20),
            yaxis_title="カロリー (kcal)",
            legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(fig_pfc, use_container_width=True)

        # 統計サマリー
        st.markdown("### 📊 期間統計")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("平均カロリー", f"{daily['total_calories'].mean():,.0f} kcal")
        with col_s2:
            st.metric("最高カロリー", f"{daily['total_calories'].max():,.0f} kcal")
        with col_s3:
            st.metric("最低カロリー", f"{daily['total_calories'].min():,.0f} kcal")
        with col_s4:
            over_days = (daily["total_calories"] > target).sum()
            st.metric("超過日数", f"{over_days} / {len(daily)} 日")

    else:
        st.info("📊 まだデータがありません。Telegramで食事を記録してください！")


# ----- タブ3: 食事記録 -----
with tab_records:
    st.markdown("### 📋 食事記録一覧")

    try:
        end_date = date_str
        start_date = (selected_date - timedelta(days=period_days - 1)).isoformat()
        records = get_all_meals_range(user_id, start_date, end_date) if user_id else []
    except Exception:
        records = []

    if records:
        df_records = pd.DataFrame(records)

        # --- 削除UI ---
        st.markdown("#### 🗑️ 記録の削除")
        # 削除候補のリストを作成
        delete_options = {}
        for _, row in df_records.iterrows():
            rid = row.get("id", "?")
            date_val = row.get("date", "")
            name = row.get("food_name", "不明")
            cal = row.get("calories", 0) or 0
            label = f"ID:{rid} | {date_val} | {name} ({cal:,.0f} kcal)"
            delete_options[label] = rid

        selected = st.multiselect(
            "削除する記録を選択",
            options=list(delete_options.keys()),
            placeholder="削除したい記録を選んでください...",
        )

        if selected:
            if st.button(f"🗑️ {len(selected)} 件を削除する", type="primary"):
                deleted_count = 0
                for label in selected:
                    meal_id = delete_options[label]
                    uid = user_id or 0
                    if delete_meal(meal_id, uid):
                        deleted_count += 1
                if deleted_count > 0:
                    st.success(f"✅ {deleted_count} 件の記録を削除しました！")
                    st.rerun()
                else:
                    st.error("⚠️ 削除に失敗しました。SupabaseのRLSポリシーを確認してください。")

        st.markdown("---")

        # --- テーブル表示 ---
        display_cols = [
            "date", "meal_type", "food_name", "calories",
            "protein", "fat", "carbohydrates", "fiber", "sugar",
            "salt_equivalent", "calcium", "iron", "magnesium", "zinc", "potassium",
            "vitamin_a", "vitamin_b1", "vitamin_b2", "vitamin_b6", "vitamin_b12",
            "vitamin_c", "vitamin_d", "vitamin_e", "vitamin_k", "folate",
            "confidence",
        ]
        available_cols = [c for c in display_cols if c in df_records.columns]
        df_display = df_records[available_cols].copy()

        rename_map = {
            "date": "日付", "meal_type": "食事", "food_name": "食品名",
            "calories": "kcal", "protein": "P(g)", "fat": "F(g)",
            "carbohydrates": "C(g)", "fiber": "繊維(g)", "sugar": "糖質(g)",
            "salt_equivalent": "食塩(g)",
            "calcium": "Ca(mg)", "iron": "Fe(mg)", "magnesium": "Mg(mg)",
            "zinc": "Zn(mg)", "potassium": "K(mg)",
            "vitamin_a": "VA(μg)", "vitamin_b1": "VB1", "vitamin_b2": "VB2",
            "vitamin_b6": "VB6", "vitamin_b12": "VB12(μg)",
            "vitamin_c": "VC(mg)", "vitamin_d": "VD(μg)",
            "vitamin_e": "VE(mg)", "vitamin_k": "VK(μg)", "folate": "葉酸(μg)",
            "confidence": "信頼度",
        }
        df_display = df_display.rename(columns=rename_map)

        for col in df_display.select_dtypes(include=["float64", "float32"]).columns:
            df_display[col] = df_display[col].round(1)

        st.dataframe(
            df_display,
            use_container_width=True,
            height=500,
            hide_index=True,
        )

        # CSVダウンロード
        csv = df_display.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 CSVダウンロード",
            data=csv,
            file_name=f"diet_records_{start_date}_to_{end_date}.csv",
            mime="text/csv",
        )
    else:
        st.info("📋 まだ記録がありません。Telegramで食事を記録してください！")


# ===== フッター =====
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.8rem;'>"
    "🥗 Diet Analyze | Powered by Gemini AI | Made with Streamlit"
    "</div>",
    unsafe_allow_html=True,
)
