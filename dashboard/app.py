from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from dashboard.charts import (
    build_activity_trend_chart,
    build_activity_week_chart,
    build_body_battery_chart,
    build_daily_trend_chart,
    build_monthly_kpi_chart,
    build_monthly_kpi_table,
    build_rhr_chart,
    build_sleep_cycle_chart,
    build_sleep_quality_summary,
    build_steps_chart,
    build_stress_chart,
    build_workout_summary_chart,
    load_body_battery_summary,
    load_sleep_summary,
    summarize_workouts,
)
from services.data_service import load_dashboard_data


def load_top_activity_data(con):
    df = pd.read_sql(
        """
        SELECT
            day,
            CAST(json_extract(raw_json, '$.activeSeconds') AS INTEGER) AS active_seconds,
            CAST(json_extract(raw_json, '$.averageStressLevel') AS REAL) AS avg_stress,
            CAST(json_extract(raw_json, '$.stressDuration') AS INTEGER) AS stress_duration,
            CAST(json_extract(raw_json, '$.totalSteps') AS INTEGER) AS total_steps,
            CAST(json_extract(raw_json, '$.dailyStepGoal') AS INTEGER) AS step_goal
        FROM raw_daily
        WHERE raw_json IS NOT NULL
        ORDER BY day
        """,
        con,
    )
    empty_daily = pd.DataFrame(columns=["day", "active_seconds", "avg_stress", "stress_duration", "total_steps", "step_goal", "active_minutes"])
    if df.empty:
        return {"daily": empty_daily, "hourly": pd.DataFrame(columns=["hour", "hourly_activity_minutes"]) }

    for column in ["active_seconds", "avg_stress", "stress_duration", "total_steps", "step_goal"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["active_minutes"] = (df["active_seconds"] / 60).fillna(0)

    daily_df = df[["day", "avg_stress", "stress_duration", "active_minutes"]].copy()
    daily_df = daily_df.dropna(subset=["day"], how="all")

    hourly_values = []
    if not df.empty:
        base_minutes = float(df["active_minutes"].mean()) if df["active_minutes"].notna().any() else 0.0
        for hour in range(24):
            hourly_values.append({"hour": hour, "hourly_activity_minutes": round(base_minutes / 24.0, 2)})
    hourly_df = pd.DataFrame(hourly_values, columns=["hour", "hourly_activity_minutes"])
    return {"daily": daily_df, "hourly": hourly_df}


def summarize_health(daily: pd.DataFrame, acts: pd.DataFrame):
    if daily.empty:
        return {
            "overall_score": 0,
            "improvement_score": 100,
            "prediction": "No Garmin data yet. Sync your data to generate a health forecast.",
            "recommendations": ["Run python sync.py to import Garmin data."],
            "scores": {"steps": 0, "recovery": 0, "activity": 0},
        }

    steps = pd.to_numeric(daily["steps"], errors="coerce").dropna()
    step_goals = pd.to_numeric(daily["step_goal"], errors="coerce").dropna()
    rhr = pd.to_numeric(daily["rhr"], errors="coerce").dropna()
    workout_minutes = pd.to_numeric(acts["minutes"], errors="coerce").sum() if not acts.empty else 0.0

    recent_steps = float(steps.tail(14).mean()) if not steps.empty else 0.0
    target_steps = float(step_goals.tail(14).mean()) if not step_goals.empty else 8000.0
    avg_rhr = float(rhr.tail(14).mean()) if not rhr.empty else 65.0

    step_score = min(100.0, max(0.0, (recent_steps / max(target_steps, 7000.0)) * 100.0))

    if avg_rhr <= 52:
        recovery_score = 92.0
    elif avg_rhr <= 57:
        recovery_score = 85.0
    elif avg_rhr <= 62:
        recovery_score = 75.0
    elif avg_rhr <= 68:
        recovery_score = 65.0
    else:
        recovery_score = max(20.0, 100.0 - (avg_rhr - 60.0) * 5.0)

    weekly_minutes = float(acts["minutes"].sum()) if not acts.empty else 0.0
    activity_score = min(100.0, max(0.0, (weekly_minutes / 180.0) * 100.0))

    overall_score = int(round(0.45 * step_score + 0.35 * recovery_score + 0.20 * activity_score))
    improvement_score = max(0, 100 - overall_score)

    if overall_score >= 80:
        prediction = "Strong health trend: recovery and cardio load are in a good range. Maintain your routine."
    elif overall_score >= 65:
        prediction = "Healthy baseline: keep training consistent and focus on improving recovery and daily movement."
    elif overall_score >= 50:
        prediction = "Needs attention: regular movement and recovery habits should improve your health trend."
    else:
        prediction = "At-risk trend: prioritize sleep, recovery, and consistent daily activity to improve resilience."

    score_map = {"steps": round(step_score, 1), "recovery": round(recovery_score, 1), "activity": round(activity_score, 1)}
    recommendations = []
    if step_score < 75:
        recommendations.append("Add 3k-5k extra steps on 3 days this week to lift aerobic base.")
    if recovery_score < 70:
        recommendations.append("Prioritize sleep consistency and reduce intense late-day training for better recovery.")
    if activity_score < 75:
        recommendations.append("Add 2 short cardio or strength sessions to improve weekly training load.")
    if not recommendations:
        recommendations.append("Keep your current routine and maintain consistency across sleep, steps, and training.")

    return {
        "overall_score": overall_score,
        "improvement_score": improvement_score,
        "prediction": prediction,
        "recommendations": recommendations,
        "scores": score_map,
    }


def benchmark_label(metric: str, value: float) -> tuple[str, str]:
    if metric == "steps":
        avg = 8000.0
        good = 10000.0
        better = 12000.0
        if value >= better:
            return "BETTER THAN AVERAGE", "benchmark-pill"
        if value >= good:
            return "GOOD GARMIN BASELINE", "benchmark-pill"
        if value >= avg:
            return "AROUND AVERAGE", "benchmark-pill warning"
        return "BELOW AVERAGE", "benchmark-pill alert"

    if metric == "sleep":
        avg = 7.0
        good = 7.5
        better = 8.0
        if value >= better:
            return "BETTER THAN AVERAGE", "benchmark-pill"
        if value >= good:
            return "GOOD GARMIN BASELINE", "benchmark-pill"
        if value >= avg:
            return "AROUND AVERAGE", "benchmark-pill warning"
        return "BELOW AVERAGE", "benchmark-pill alert"

    if metric == "rhr":
        avg = 60.0
        good = 58.0
        better = 52.0
        if value <= better:
            return "BETTER THAN AVERAGE", "benchmark-pill"
        if value <= good:
            return "GOOD GARMIN BASELINE", "benchmark-pill"
        if value <= avg:
            return "AROUND AVERAGE", "benchmark-pill warning"
        return "ABOVE AVERAGE", "benchmark-pill alert"

    if metric == "workout":
        avg = 120.0
        good = 150.0
        better = 180.0
        if value >= better:
            return "BETTER THAN AVERAGE", "benchmark-pill"
        if value >= good:
            return "GOOD GARMIN BASELINE", "benchmark-pill"
        if value >= avg:
            return "AROUND AVERAGE", "benchmark-pill warning"
        return "BELOW AVERAGE", "benchmark-pill alert"

    if metric == "stress":
        avg = 35.0
        good = 25.0
        better = 18.0
        if value <= better:
            return "BETTER THAN AVERAGE", "benchmark-pill"
        if value <= good:
            return "GOOD GARMIN BASELINE", "benchmark-pill"
        if value <= avg:
            return "AROUND AVERAGE", "benchmark-pill warning"
        return "ABOVE AVERAGE", "benchmark-pill alert"

    if metric == "activity":
        avg = 75.0
        good = 100.0
        better = 130.0
        if value >= better:
            return "BETTER THAN AVERAGE", "benchmark-pill"
        if value >= good:
            return "GOOD GARMIN BASELINE", "benchmark-pill"
        if value >= avg:
            return "AROUND AVERAGE", "benchmark-pill warning"
        return "BELOW AVERAGE", "benchmark-pill alert"

    return "TYPICAL BENCHMARK", "benchmark-pill"


def benchmark_text(metric: str, value: float) -> str:
    label, _ = benchmark_label(metric, value)
    if metric == "steps":
        return f"{label} • Typical: ~8,000 steps/day • Good: 10,000+ • Better: 12,000+"
    if metric == "sleep":
        return f"{label} • Typical: ~7.0h/night • Good: 7.5h+ • Better: 8.0h+"
    if metric == "rhr":
        return f"{label} • Typical: ~60 bpm • Good: <=58 bpm • Better: <=52 bpm"
    if metric == "workout":
        return f"{label} • Typical: ~120 min/week • Good: 150+ min • Better: 180+ min"
    if metric == "stress":
        return f"{label} • Typical: ~35 stress • Good: <=25 • Better: <=18"
    if metric == "activity":
        return f"{label} • Typical: ~75 min/day • Good: 100+ min • Better: 130+ min"
    return "Typical benchmark: Good is above average and Better is near the top end of the range."


def main():
    st.set_page_config(page_title="Garmin Dashboard", layout="wide")
    st.title("Garmin dashboard")

    st.markdown(
        """
        <style>
        .stApp {
            background: #0d1418;
            color: #edf4f5;
        }

        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }

        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #131d24 0%, #0f171b 100%);
            border: 1px solid rgba(159, 173, 181, 0.18);
            border-radius: 0.9rem;
            padding: 0.8rem 0.9rem;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
        }

        div[data-testid="stMetric"] > div {
            color: #edf4f5 !important;
        }

        div[data-testid="stMetric"] label {
            color: #a2b4b9 !important;
            font-size: 0.7rem !important;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #f8fbfc !important;
            font-weight: 700;
        }

        .section-header {
            margin-top: 1.5rem;
            margin-bottom: 0.7rem;
            font-size: 1.08rem;
            font-weight: 700;
            color: #f4f8fb;
            border-bottom: 1px solid rgba(174, 188, 195, 0.17);
            padding-bottom: 0.45rem;
        }

        h1, h2, h3, h4, p, span, div {
            color: #edf4f5 !important;
        }

        .stDataFrame > div,
        .stExpander,
        .stAlert {
            background: #111b21;
            border: 1px solid rgba(174, 188, 195, 0.14);
            border-radius: 0.8rem;
        }

        .stPlotlyChart > div {
            border-radius: 0.8rem;
            border: 1px solid rgba(174, 188, 195, 0.12);
            overflow: hidden;
        }

        .stSidebar {
            background: #0b1217;
            border-right: 1px solid rgba(174, 188, 195, 0.12);
        }

        .stSelectbox > div,
        .stButton > button {
            background: #121d24;
            border: 1px solid rgba(174, 188, 195, 0.18);
            color: #edf4f5;
        }

        .stButton > button {
            border-radius: 0.6rem;
        }

        .benchmark-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-top: 0.55rem;
            margin-bottom: 0.6rem;
            padding: 0.5rem 0.85rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            background: linear-gradient(135deg, #2ef2c5 0%, #3ea8ff 100%);
            color: #04151a !important;
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 0 22px rgba(62, 168, 255, 0.42);
            min-height: 2rem;
            line-height: 1.1;
        }

        .benchmark-pill.warning {
            background: linear-gradient(135deg, #ffe082 0%, #ffb703 100%);
            color: #2a1800 !important;
            box-shadow: 0 0 22px rgba(255, 183, 3, 0.34);
        }

        .benchmark-pill.alert {
            background: linear-gradient(135deg, #ff8a80 0%, #ff4d6d 100%);
            color: #fffafc !important;
            box-shadow: 0 0 22px rgba(255, 77, 109, 0.38);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        days = st.selectbox("Range", [14, 30, 60, 90], index=1, format_func=lambda x: f"Last {x} days")
        st.caption("Data source: local SQLite database")

    data = load_dashboard_data(days)
    con = data["connection"]
    daily = data["daily"]
    acts = data["activities"]
    last_sync = data["last_sync"]
    sleep_df = data["sleep_df"]
    body_df = data["body_df"]
    monthly_df = data["monthly_df"]
    health = summarize_health(daily, acts)

    if daily.empty:
        st.info("No local Garmin data found yet. Run `python sync.py` once in a terminal to import data, then reopen the dashboard.")
        return

    with st.sidebar:
        st.caption(f"Last sync: {last_sync:%d %b %H:%M}" if last_sync else "Never synced")
        st.caption("To refresh data, run `python sync.py` from the project folder.")
        st.caption("Data location: garmin.db in the project folder")

    activity_state = load_top_activity_data(con)
    activity_df = activity_state["daily"]
    hourly_df = activity_state["hourly"]
    stress_df = activity_df[["day", "avg_stress", "stress_duration"]].copy()

    st.subheader("Today at a glance")
    today_cards = st.columns(4)
    with today_cards[0]:
        today_steps = float(daily["steps"].dropna().iloc[-1]) if "steps" in daily.columns and not daily["steps"].dropna().empty else 0.0
        st.metric("Today steps", f"{today_steps:,.0f}")
    with today_cards[1]:
        today_activity = float(daily["activity"].dropna().iloc[-1]) if "activity" in daily.columns and not daily["activity"].dropna().empty else 0.0
        st.metric("Today active", f"{today_activity:,.0f} min")
    with today_cards[2]:
        today_sleep = float(sleep_df["sleep_hours"].dropna().iloc[-1]) if sleep_df is not None and "sleep_hours" in sleep_df.columns and not sleep_df["sleep_hours"].dropna().empty else 0.0
        st.metric("Sleep", f"{today_sleep:.1f}h")
    with today_cards[3]:
        st.metric("Recovery", f"{health['overall_score']}/100")

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    workout_summary = summarize_workouts(acts)
    sleep_summary = build_sleep_quality_summary(sleep_df)

    st.markdown('<div class="section-header">Daily insight snapshot</div>', unsafe_allow_html=True)
    metric_cols = st.columns(4)
    with metric_cols[0]:
        avg_steps = float(daily["steps"].mean()) if "steps" in daily.columns and daily["steps"].notna().any() else 0.0
        st.metric("Avg steps / day", f"{avg_steps:,.0f}")
        label, css_class = benchmark_label("steps", avg_steps)
        st.markdown(f'<div class="{css_class}">{label}</div>', unsafe_allow_html=True)
        st.caption(benchmark_text("steps", avg_steps))
    with metric_cols[1]:
        avg_rhr = float(daily["rhr"].mean()) if "rhr" in daily.columns and daily["rhr"].notna().any() else 0.0
        st.metric("Avg resting HR", f"{avg_rhr:.0f} bpm" if avg_rhr else "n/a")
        if avg_rhr:
            label, css_class = benchmark_label("rhr", avg_rhr)
            st.markdown(f'<div class="{css_class}">{label}</div>', unsafe_allow_html=True)
            st.caption(benchmark_text("rhr", avg_rhr))
        else:
            st.caption("Average Garmin user benchmark: ~60 bpm, good <=58 bpm")
    with metric_cols[2]:
        weekly_minutes = float(workout_summary["total_minutes"]) if workout_summary["total_minutes"] else 0.0
        st.metric("Workout minutes", f"{weekly_minutes:.0f} min")
        label, css_class = benchmark_label("workout", weekly_minutes)
        st.markdown(f'<div class="{css_class}">{label}</div>', unsafe_allow_html=True)
        st.caption(benchmark_text("workout", weekly_minutes))
    with metric_cols[3]:
        avg_sleep = float(sleep_summary["avg_sleep_hours"]) if "avg_sleep_hours" in sleep_summary else 0.0
        st.metric("Avg sleep", f"{avg_sleep:.1f}h")
        label, css_class = benchmark_label("sleep", avg_sleep)
        st.markdown(f'<div class="{css_class}">{label}</div>', unsafe_allow_html=True)
        st.caption(benchmark_text("sleep", avg_sleep))

    st.subheader("Health analysis")
    with st.container(border=True):
        st.subheader("Health forecast")
        forecast_cols = st.columns(3)
        with forecast_cols[0]:
            st.metric("Health score", f"{health['overall_score']}/100", border=True)
        with forecast_cols[1]:
            st.metric("Improvement score", f"{health['improvement_score']}/100", border=True)
        with forecast_cols[2]:
            st.metric("Prediction", health["prediction"][:22] + ("..." if len(health["prediction"]) > 22 else ""), border=True)

        st.markdown("**Overall outlook**")
        st.write(health["prediction"])

        for label, value in health["scores"].items():
            st.markdown(f"**{label.title()}**")
            st.progress(value / 100.0)

        st.markdown("**Recommended focus areas**")
        for rec in health["recommendations"]:
            st.write(f"• {rec}")

    st.subheader("Stress and activity overview")
    view_mode = st.segmented_control("Activity view", ["Daily", "Hourly"], default="Daily")

    top_left, top_right = st.columns(2)
    with top_left:
        stress_average = float(activity_df["avg_stress"].dropna().mean()) if not activity_df.empty and activity_df["avg_stress"].notna().any() else 0.0
        st.metric("Stress score", f"{int(stress_average)}/100")
        label, css_class = benchmark_label("stress", stress_average)
        st.markdown(f'<div class="{css_class}">{label}</div>', unsafe_allow_html=True)
        st.caption(benchmark_text("stress", stress_average))
        st.plotly_chart(build_stress_chart(stress_df), width="stretch")
    with top_right:
        active_average = float(activity_df["active_minutes"].dropna().mean()) if not activity_df.empty and activity_df["active_minutes"].notna().any() else 0.0
        st.metric("Active minutes / day", f"{int(active_average)} min")
        label, css_class = benchmark_label("activity", active_average)
        st.markdown(f'<div class="{css_class}">{label}</div>', unsafe_allow_html=True)
        st.caption(benchmark_text("activity", active_average))
        chart_df = hourly_df if view_mode == "Hourly" else activity_df
        st.plotly_chart(build_activity_trend_chart(chart_df, "hourly" if view_mode == "Hourly" else "daily"), width="stretch")

    st.subheader("Database overview")
    with st.expander("View raw DB tables and schema", expanded=False):
        table_names = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", con)
        st.dataframe(table_names, width="stretch")

        for table in ["daily", "activities", "raw_daily", "raw_activity", "meta"]:
            try:
                schema = pd.read_sql(f"PRAGMA table_info({table})", con)
                st.write(f"### {table}")
                st.dataframe(schema, width="stretch")
                sample = pd.read_sql(f"SELECT * FROM {table} LIMIT 5", con)
                st.dataframe(sample, width="stretch")
            except Exception:
                pass

        st.caption("All data is stored locally in the SQLite file: garmin.db")

    st.markdown('<div class="section-header">Most important trends</div>', unsafe_allow_html=True)
    left_chart, right_chart = st.columns([1.5, 1])
    with left_chart:
        st.subheader("Daily steps")
        st.plotly_chart(build_steps_chart(daily), width="stretch")
    with right_chart:
        st.subheader("Resting heart rate")
        st.plotly_chart(build_rhr_chart(daily), width="stretch")

    st.markdown('<div class="section-header">Recovery and recovery quality</div>', unsafe_allow_html=True)
    recovery_left, recovery_right = st.columns(2)
    with recovery_left:
        st.subheader("Sleep cycle")
        st.plotly_chart(build_sleep_cycle_chart(sleep_df), width="stretch")
    with recovery_right:
        st.subheader("Body battery")
        st.plotly_chart(build_body_battery_chart(body_df), width="stretch")

    st.markdown('<div class="section-header">Workout performance</div>', unsafe_allow_html=True)
    work_left, work_right = st.columns([1.2, 1.3])
    with work_left:
        st.subheader("Workout summary")
        st.metric("Total workout minutes", f"{workout_summary['total_minutes']:.0f} min")
        st.metric("Average per workout", f"{workout_summary['avg_minutes']:.0f} min")
        st.metric("Top workout type", workout_summary["top_type"])
    with work_right:
        st.plotly_chart(build_workout_summary_chart(acts), width="stretch")

    st.subheader("Exercise minutes per week")
    st.plotly_chart(build_activity_week_chart(acts), width="stretch")

    st.markdown('<div class="section-header">Progress and long-term view</div>', unsafe_allow_html=True)
    monthly_left, monthly_right = st.columns([1.2, 1.5])
    with monthly_left:
        st.subheader("Monthly KPI table")
        st.dataframe(monthly_df, width="stretch")
    with monthly_right:
        st.subheader("Monthly KPI trend")
        st.plotly_chart(build_monthly_kpi_chart(monthly_df), width="stretch")

    st.subheader("Trend summary")
    trend_df = pd.DataFrame(
        {
            "metric": ["steps", "rhr"],
            "value": [
                float(daily["steps"].dropna().iloc[-1]) if "steps" in daily.columns and not daily["steps"].dropna().empty else 0.0,
                float(daily["rhr"].dropna().iloc[-1]) if "rhr" in daily.columns and not daily["rhr"].dropna().empty else 0.0,
            ],
        },
    )
    if not trend_df.empty:
        st.dataframe(trend_df, width="stretch")
        st.plotly_chart(build_daily_trend_chart(daily, "steps"), width="stretch")


if __name__ == "__main__":
    main()
