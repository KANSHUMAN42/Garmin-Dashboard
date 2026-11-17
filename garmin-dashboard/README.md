# Garmin Dashboard

This project is a local-first Garmin dashboard built with Python, Streamlit, and SQLite.

## Project structure

```text
garmin-dashboard/
├── app.py                     # entry point for the app
├── sync.py                    # manual Garmin sync script
├── requirements.txt           # Python dependencies
├── garmin.db                  # local SQLite database
├── dao/
│   ├── __init__.py            # DAO exports
│   └── database.py           # SQLite connection and schema setup
├── services/
│   ├── __init__.py           # service exports
│   └── data_service.py       # loaded data and DB access logic
├── dashboard/
│   ├── __init__.py           # dashboard package
│   ├── app.py                # dashboard UI and layout
│   └── charts.py             # reusable chart generation functions
└── README.md
```

## How it works

1. `sync.py` pulls data from Garmin and stores it in the local SQLite database.
2. `dao/database.py` owns the database connection and schema.
3. `services/data_service.py` reads the DB and returns the data needed by the dashboard.
4. `dashboard/app.py` renders the dashboard UI.
5. `dashboard/charts.py` builds all visualizations.

## Why this architecture

This structure separates responsibilities:

- DAO layer: database access and schema management
- Service layer: business/data preparation logic
- Dashboard layer: UI + visual rendering

This keeps the app easier to extend when you add more health metrics or charts later.

## Run locally

```bash
cd garmin-dashboard
python -m streamlit run app.py
```

## Refresh data locally

```bash
cd garmin-dashboard
python sync.py
```

This script fetches fresh Garmin data and stores it in `garmin.db`.
