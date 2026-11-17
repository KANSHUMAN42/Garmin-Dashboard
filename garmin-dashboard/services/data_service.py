from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from dao.database import db


def load_local_data(days: int):
    con = db()
    row = con.execute("SELECT v FROM meta WHERE k='last_sync'").fetchone()
    last_sync = datetime.fromisoformat(row[0]) if row else None
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    daily = pd.read_sql("SELECT * FROM daily WHERE day >= ? ORDER BY day", con, params=(since,))
    acts = pd.read_sql("SELECT * FROM activities WHERE day >= ? ORDER BY day", con, params=(since,))
    return con, daily, acts, last_sync


def load_dashboard_data(days: int):
    con, daily, acts, last_sync = load_local_data(days)
    from dashboard.charts import load_body_battery_summary, load_sleep_summary, build_monthly_kpi_table

    sleep_df = load_sleep_summary(con)
    body_df = load_body_battery_summary(con)
    monthly_df = build_monthly_kpi_table(daily, acts)
    return {
        "connection": con,
        "daily": daily,
        "activities": acts,
        "last_sync": last_sync,
        "sleep_df": sleep_df,
        "body_df": body_df,
        "monthly_df": monthly_df,
    }
