"""Pulls steps, resting HR and activities from Garmin into a local SQLite file.
Run `python sync.py` once in a terminal to log in (token is then cached).

The database keeps both:
- flattened dashboard-friendly tables (`daily`, `activities`)
- full raw JSON payloads (`raw_daily`, `raw_activity`) for future dashboard reuse
"""
import getpass
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from garminconnect import Garmin

from dao.database import DB, db

TOKENS = Path.home() / ".garmin_tokens"
BACKFILL_DAYS = 30   # first run only
REFRESH_DAYS = 3     # re-pull recent days (watch data often syncs late)


def login(interactive=False):
    try:  # reuse cached token: no fresh login, no MFA
        g = Garmin()
        g.login(str(TOKENS))
        return g
    except Exception:
        pass
    email, pw = os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD")
    if not interactive and not (email and pw):
        raise RuntimeError("Not logged in. Run `python sync.py` once in a terminal first.")
    email = email or input("Garmin email: ")
    pw = pw or getpass.getpass("Garmin password: ")
    g = Garmin(email, pw, prompt_mfa=lambda: input("MFA code: "))
    g.login(str(TOKENS))
    return g


def sync(interactive=False):
    con = db()
    today = date.today()
    last = con.execute("SELECT MAX(day) FROM daily").fetchone()[0]
    if last:
        start = date.fromisoformat(last) - timedelta(days=REFRESH_DAYS - 1)
    else:
        start = today - timedelta(days=BACKFILL_DAYS)
    g = login(interactive)

    d = start
    while d <= today:
        s = g.get_stats(d.isoformat()) or {}
        raw_daily = json.dumps(s, ensure_ascii=False)
        con.execute(
            "INSERT OR REPLACE INTO raw_daily(day, raw_json) VALUES (?, ?)",
            (d.isoformat(), raw_daily),
        )
        con.execute(
            "INSERT OR REPLACE INTO daily VALUES (?,?,?,?)",
            (d.isoformat(), s.get("totalSteps"), s.get("dailyStepGoal"), s.get("restingHeartRate")),
        )
        d += timedelta(days=1)
        time.sleep(0.5)

    for a in g.get_activities_by_date(start.isoformat(), today.isoformat()) or []:
        activity_id = a["activityId"]
        day = a["startTimeLocal"][:10]
        raw_activity = json.dumps(a, ensure_ascii=False)
        con.execute(
            "INSERT OR REPLACE INTO raw_activity(id, day, raw_json) VALUES (?, ?, ?)",
            (activity_id, day, raw_activity),
        )
        con.execute(
            "INSERT OR REPLACE INTO activities VALUES (?,?,?,?,?,?)",
            (activity_id, day, a.get("activityName"),
             (a.get("activityType") or {}).get("typeKey"),
             (a.get("duration") or 0) / 60, a.get("calories")),
        )

    con.execute("INSERT OR REPLACE INTO meta VALUES ('last_sync', ?)", (datetime.now().isoformat(),))
    con.commit()


if __name__ == "__main__":
    sync(interactive=True)
    print("Synced.")
