from __future__ import annotations

import pandas as pd
import plotly.express as px


EMPTY_CHART_MESSAGE = "No data available for this KPI yet."


def empty_chart(title: str, message: str = EMPTY_CHART_MESSAGE):
    fig = px.bar(pd.DataFrame({"x": [0], "y": [0]}), x="x", y="y")
    fig.update_traces(marker_color="#dfe6ee")
    fig.update_layout(
        title=title,
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "x": 0.5,
                "y": 0.5,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 15},
            }
        ],
        template="plotly_white",
    )
    return fig


def build_steps_chart(daily: pd.DataFrame):
    if daily.empty or "steps" not in daily.columns:
        return empty_chart("Daily steps")

    fig = px.bar(daily, x="day", y="steps", title="Daily steps")
    goal = daily["step_goal"].dropna()
    if not goal.empty:
        fig.add_hline(
            y=float(goal.iloc[-1]),
            line_dash="dash",
            annotation_text="goal",
            annotation_position="top left",
        )
    fig.update_layout(xaxis_title="Day", yaxis_title="Steps", template="plotly_white")
    return fig


def build_rhr_chart(daily: pd.DataFrame):
    if daily.empty or "rhr" not in daily.columns:
        return empty_chart("Resting heart rate")

    rhr = daily.dropna(subset=["rhr"]).copy()
    if rhr.empty:
        return empty_chart("Resting heart rate")

    fig = px.line(rhr, x="day", y="rhr", markers=True, title="Resting heart rate")
    fig.update_layout(xaxis_title="Day", yaxis_title="bpm", template="plotly_white")
    return fig


def build_activity_week_chart(acts: pd.DataFrame):
    if acts.empty or "minutes" not in acts.columns:
        return empty_chart("Exercise minutes per week")

    data = acts.copy()
    data["week"] = pd.to_datetime(data["day"]).dt.to_period("W").dt.start_time
    weekly = data.groupby(["week", "type"], as_index=False)["minutes"].sum()
    fig = px.bar(weekly, x="week", y="minutes", color="type", title="Exercise minutes per week")
    fig.update_layout(xaxis_title="Week", yaxis_title="Minutes", template="plotly_white")
    return fig


def summarize_workouts(acts: pd.DataFrame):
    if acts.empty:
        return {
            "total_minutes": 0,
            "avg_minutes": 0,
            "top_type": "n/a",
            "type_breakdown": pd.DataFrame(columns=["type", "minutes"]),
        }

    summary = acts.groupby("type", as_index=False)["minutes"].sum().sort_values("minutes", ascending=False)
    total_minutes = float(acts["minutes"].sum())
    avg_minutes = float(acts["minutes"].mean()) if not acts.empty else 0.0
    top_type = summary["type"].iloc[0] if not summary.empty else "n/a"
    return {
        "total_minutes": total_minutes,
        "avg_minutes": avg_minutes,
        "top_type": top_type,
        "type_breakdown": summary,
    }


def build_workout_summary_chart(acts: pd.DataFrame):
    if acts.empty or "minutes" not in acts.columns:
        return empty_chart("Workout summary")

    summary = summarize_workouts(acts)["type_breakdown"]
    if summary.empty:
        return empty_chart("Workout summary")

    fig = px.pie(summary, names="type", values="minutes", title="Workout distribution")
    return fig


def build_daily_trend_chart(daily: pd.DataFrame, metric: str = "steps"):
    if daily.empty or metric not in daily.columns:
        return empty_chart(f"{metric.replace('_', ' ').title()} trend")

    fig = px.line(daily, x="day", y=metric, markers=True, title=f"{metric.replace('_', ' ').title()} trend")
    fig.update_layout(xaxis_title="Day", yaxis_title=metric.replace("_", " ").title(), template="plotly_white")
    return fig


def load_sleep_summary(con):
    try:
        sleep_df = pd.read_sql(
            """
            SELECT
                day,
                json_extract(raw_json, '$.sleepingSeconds') AS sleeping_seconds,
                json_extract(raw_json, '$.deepSleepSeconds') AS deep_sleep_seconds,
                json_extract(raw_json, '$.lightSleepSeconds') AS light_sleep_seconds,
                json_extract(raw_json, '$.remSleepSeconds') AS rem_sleep_seconds
            FROM raw_daily
            WHERE raw_json IS NOT NULL
            ORDER BY day
            """,
            con,
        )
    except Exception:
        return pd.DataFrame(columns=["day", "sleeping_seconds", "deep_sleep_seconds", "light_sleep_seconds", "rem_sleep_seconds"])

    if sleep_df.empty:
        return sleep_df

    for column in ["sleeping_seconds", "deep_sleep_seconds", "light_sleep_seconds", "rem_sleep_seconds"]:
        sleep_df[column] = pd.to_numeric(sleep_df[column], errors="coerce")

    sleep_df["sleep_hours"] = sleep_df["sleeping_seconds"] / 3600
    sleep_df["deep_sleep_hours"] = sleep_df["deep_sleep_seconds"] / 3600
    sleep_df["light_sleep_hours"] = sleep_df["light_sleep_seconds"] / 3600
    sleep_df["rem_sleep_hours"] = sleep_df["rem_sleep_seconds"] / 3600
    return sleep_df


def build_sleep_cycle_chart(sleep_df: pd.DataFrame):
    if sleep_df is None or sleep_df.empty:
        return empty_chart("Sleep cycle", "No sleep data available yet.")

    required = {"day", "deep_sleep_hours", "light_sleep_hours", "rem_sleep_hours"}
    if not required.issubset(sleep_df.columns):
        return empty_chart("Sleep cycle", "Sleep data not available in the current database.")

    chart_df = sleep_df[["day", "deep_sleep_hours", "light_sleep_hours", "rem_sleep_hours"]].copy()
    chart_df = chart_df.melt(id_vars="day", var_name="stage", value_name="hours")
    fig = px.bar(
        chart_df,
        x="day",
        y="hours",
        color="stage",
        barmode="stack",
        title="Sleep cycle",
        category_orders={"stage": ["deep_sleep_hours", "light_sleep_hours", "rem_sleep_hours"]},
    )
    fig.update_layout(xaxis_title="Day", yaxis_title="Hours", template="plotly_white")
    return fig


def build_trend_summary(daily: pd.DataFrame):
    if daily.empty:
        return pd.DataFrame(columns=["metric", "current", "previous", "change_pct"])

    trend = pd.DataFrame(
        {
            "metric": ["steps", "rhr"],
            "current": [
                float(daily["steps"].dropna().iloc[-1]) if "steps" in daily.columns and not daily["steps"].dropna().empty else 0.0,
                float(daily["rhr"].dropna().iloc[-1]) if "rhr" in daily.columns and not daily["rhr"].dropna().empty else 0.0,
            ],
            "previous": [
                float(daily["steps"].dropna().iloc[-2]) if "steps" in daily.columns and not daily["steps"].dropna().empty and len(daily["steps"].dropna()) > 1 else 0.0,
                float(daily["rhr"].dropna().iloc[-2]) if "rhr" in daily.columns and not daily["rhr"].dropna().empty and len(daily["rhr"].dropna()) > 1 else 0.0,
            ],
        }
    )
    trend["change_pct"] = ((trend["current"] - trend["previous"]) / trend["previous"].replace(0, pd.NA)) * 100
    trend["change_pct"] = trend["change_pct"].fillna(0)
    return trend


def load_body_battery_summary(con):
    try:
        body = pd.read_sql(
            """
            SELECT
                day,
                json_extract(raw_json, '$.bodyBatteryChargedValue') AS charged,
                json_extract(raw_json, '$.bodyBatteryDrainedValue') AS drained,
                json_extract(raw_json, '$.bodyBatteryHighestValue') AS highest,
                json_extract(raw_json, '$.bodyBatteryLowestValue') AS lowest
            FROM raw_daily
            WHERE raw_json IS NOT NULL
            ORDER BY day
            """,
            con,
        )
    except Exception:
        return pd.DataFrame(columns=["day", "charged", "drained", "highest", "lowest"])

    if body.empty:
        return body

    for column in ["charged", "drained", "highest", "lowest"]:
        body[column] = pd.to_numeric(body[column], errors="coerce")
    return body


def build_body_battery_chart(body_df: pd.DataFrame):
    if body_df is None or body_df.empty:
        return empty_chart("Body battery", "No body battery data available yet.")

    needed = {"day", "highest", "lowest"}
    if not needed.issubset(body_df.columns):
        return empty_chart("Body battery", "Body battery metrics are not available in the current database.")

    chart_df = body_df[["day", "highest", "lowest"]].copy()
    chart_df = chart_df.rename(columns={"highest": "peak", "lowest": "low"})
    fig = px.line(chart_df, x="day", y=["peak", "low"], markers=True, title="Body battery range")
    fig.update_layout(xaxis_title="Day", yaxis_title="Body battery", template="plotly_white")
    return fig


def build_sleep_quality_summary(sleep_df: pd.DataFrame):
    if sleep_df is None or sleep_df.empty:
        return {
            "avg_sleep_hours": 0.0,
            "avg_deep_sleep_hours": 0.0,
            "avg_light_sleep_hours": 0.0,
            "avg_rem_sleep_hours": 0.0,
        }

    return {
        "avg_sleep_hours": float(sleep_df["sleep_hours"].mean()) if "sleep_hours" in sleep_df.columns else 0.0,
        "avg_deep_sleep_hours": float(sleep_df["deep_sleep_hours"].mean()) if "deep_sleep_hours" in sleep_df.columns else 0.0,
        "avg_light_sleep_hours": float(sleep_df["light_sleep_hours"].mean()) if "light_sleep_hours" in sleep_df.columns else 0.0,
        "avg_rem_sleep_hours": float(sleep_df["rem_sleep_hours"].mean()) if "rem_sleep_hours" in sleep_df.columns else 0.0,
    }


def build_monthly_kpi_table(daily: pd.DataFrame, acts: pd.DataFrame):
    if daily.empty and acts.empty:
        return pd.DataFrame(columns=["month", "avg_steps", "avg_rhr", "workout_minutes"])

    monthly = pd.DataFrame()
    if not daily.empty:
        daily_copy = daily.copy()
        daily_copy["month"] = pd.to_datetime(daily_copy["day"]).dt.to_period("M").astype(str)
        monthly_steps = daily_copy.groupby("month", as_index=False)["steps"].mean()
        monthly_rhr = daily_copy.groupby("month", as_index=False)["rhr"].mean()
        monthly = monthly_steps.merge(monthly_rhr, on="month", how="outer")

    if not acts.empty:
        acts_copy = acts.copy()
        acts_copy["month"] = pd.to_datetime(acts_copy["day"]).dt.to_period("M").astype(str)
        monthly_minutes = acts_copy.groupby("month", as_index=False)["minutes"].sum()
        if monthly.empty:
            monthly = monthly_minutes.rename(columns={"minutes": "workout_minutes"})
        else:
            monthly = monthly.merge(monthly_minutes, on="month", how="outer")

    if monthly.empty:
        return pd.DataFrame(columns=["month", "avg_steps", "avg_rhr", "workout_minutes"])

    monthly = monthly.rename(columns={"steps": "avg_steps", "rhr": "avg_rhr", "minutes": "workout_minutes"})
    monthly["avg_steps"] = pd.to_numeric(monthly.get("avg_steps", pd.Series([0] * len(monthly))), errors="coerce").fillna(0)
    monthly["avg_rhr"] = pd.to_numeric(monthly.get("avg_rhr", pd.Series([0] * len(monthly))), errors="coerce").fillna(0)
    monthly["workout_minutes"] = pd.to_numeric(monthly.get("workout_minutes", pd.Series([0] * len(monthly))), errors="coerce").fillna(0)
    return monthly.sort_values("month")


def build_monthly_kpi_chart(monthly_df: pd.DataFrame):
    if monthly_df is None or monthly_df.empty:
        return empty_chart("Monthly KPI trend")

    fig = px.line(monthly_df, x="month", y=["avg_steps", "workout_minutes"], title="Monthly KPI trend")
    fig.update_layout(xaxis_title="Month", yaxis_title="Value", template="plotly_white")
    return fig
