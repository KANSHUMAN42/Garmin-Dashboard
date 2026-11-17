from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from dashboard.charts import (
    build_activity_week_chart,
    build_body_battery_chart,
    build_daily_trend_chart,
    build_monthly_kpi_chart,
    build_monthly_kpi_table,
    build_rhr_chart,
    build_sleep_cycle_chart,
    build_sleep_quality_summary,
    build_steps_chart,
    build_workout_summary_chart,
    load_body_battery_summary,
    load_sleep_summary,
    summarize_workouts,
)
from services.data_service import load_dashboard_data


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

    if daily.empty:
        st.info("No local Garmin data found yet. Run `python sync.py` once in a terminal to import data, then reopen the dashboard.")
        return

    with st.sidebar:
        st.caption(f"Last sync: {last_sync:%d %b %H:%M}" if last_sync else "Never synced")
        st.caption("To refresh data, run `python sync.py` from the project folder.")
        st.caption("Data location: garmin.db in the project folder")

    st.subheader("Database overview")
    with st.expander("View raw DB tables and schema", expanded=False):
        table_names = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", con)
        st.dataframe(table_names, use_container_width=True)

        for table in ["daily", "activities", "raw_daily", "raw_activity", "meta"]:
            try:
                schema = pd.read_sql(f"PRAGMA table_info({table})", con)
                st.write(f"### {table}")
                st.dataframe(schema, use_container_width=True)
                sample = pd.read_sql(f"SELECT * FROM {table} LIMIT 5", con)
                st.dataframe(sample, use_container_width=True)
            except Exception:
                pass

        st.caption("All data is stored locally in the SQLite file: garmin.db")

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    workout_summary = summarize_workouts(acts)
    sleep_summary = build_sleep_quality_summary(sleep_df)

    st.markdown('<div class="section-header">Daily insight snapshot</div>', unsafe_allow_html=True)
    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Avg steps / day", f"{daily['steps'].mean():,.0f}")
    with metric_cols[1]:
        st.metric("Avg resting HR", f"{daily['rhr'].mean():.0f} bpm" if daily["rhr"].notna().any() else "n/a")
    with metric_cols[2]:
        st.metric("Workout minutes", f"{workout_summary['total_minutes']:.0f} min")
    with metric_cols[3]:
        st.metric("Avg sleep", f"{sleep_summary['avg_sleep_hours']:.1f}h")

    st.markdown('<div class="section-header">Most important trends</div>', unsafe_allow_html=True)
    left_chart, right_chart = st.columns([1.5, 1])
    with left_chart:
        st.subheader("Daily steps")
        st.plotly_chart(build_steps_chart(daily), use_container_width=True)
    with right_chart:
        st.subheader("Resting heart rate")
        st.plotly_chart(build_rhr_chart(daily), use_container_width=True)

    st.markdown('<div class="section-header">Recovery and recovery quality</div>', unsafe_allow_html=True)
    recovery_left, recovery_right = st.columns(2)
    with recovery_left:
        st.subheader("Sleep cycle")
        st.plotly_chart(build_sleep_cycle_chart(sleep_df), use_container_width=True)
    with recovery_right:
        st.subheader("Body battery")
        st.plotly_chart(build_body_battery_chart(body_df), use_container_width=True)

    st.markdown('<div class="section-header">Workout performance</div>', unsafe_allow_html=True)
    work_left, work_right = st.columns([1.2, 1.3])
    with work_left:
        st.subheader("Workout summary")
        st.metric("Total workout minutes", f"{workout_summary['total_minutes']:.0f} min")
        st.metric("Average per workout", f"{workout_summary['avg_minutes']:.0f} min")
        st.metric("Top workout type", workout_summary["top_type"])
    with work_right:
        st.plotly_chart(build_workout_summary_chart(acts), use_container_width=True)

    st.subheader("Exercise minutes per week")
    st.plotly_chart(build_activity_week_chart(acts), use_container_width=True)

    st.markdown('<div class="section-header">Progress and long-term view</div>', unsafe_allow_html=True)
    monthly_left, monthly_right = st.columns([1.2, 1.5])
    with monthly_left:
        st.subheader("Monthly KPI table")
        st.dataframe(monthly_df, use_container_width=True)
    with monthly_right:
        st.subheader("Monthly KPI trend")
        st.plotly_chart(build_monthly_kpi_chart(monthly_df), use_container_width=True)

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
        st.dataframe(trend_df, use_container_width=True)
        st.plotly_chart(build_daily_trend_chart(daily, "steps"), use_container_width=True)


if __name__ == "__main__":
    main()
