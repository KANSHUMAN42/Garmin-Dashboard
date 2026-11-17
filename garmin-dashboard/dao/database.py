from __future__ import annotations

import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB = BASE / "garmin.db"


def db():
    con = sqlite3.connect(DB)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily(
            day TEXT PRIMARY KEY,
            steps INTEGER,
            step_goal INTEGER,
            rhr INTEGER
        );

        CREATE TABLE IF NOT EXISTS activities(
            id INTEGER PRIMARY KEY,
            day TEXT,
            name TEXT,
            type TEXT,
            minutes REAL,
            calories REAL
        );

        CREATE TABLE IF NOT EXISTS raw_daily(
            day TEXT PRIMARY KEY,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_activity(
            id INTEGER PRIMARY KEY,
            day TEXT,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
        """
    )
    return con
