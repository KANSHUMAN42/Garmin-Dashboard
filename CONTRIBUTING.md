# Contributing

Thanks for your interest in contributing to Garmin Dashboard.

## How to contribute

1. Fork the repository.
2. Create a new branch for your change.
3. Make your update with a clear, focused change.
4. Run the project locally and make sure it still works.
5. Open a pull request with a short explanation of what changed and why.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python sync.py
streamlit run app.py
```

## Project goals

Please keep this project aligned with its purpose:

- local-first Garmin data workflow
- SQLite-backed dashboard
- data import and display without repeated live API calls
- clean, readable analytics and visualizations

## Contribution guidelines

- Keep changes focused and easy to review.
- Prefer small, well-documented pull requests.
- Avoid storing personal credentials or Garmin session secrets in the repo.
- If you add new graph or metric logic, keep it modular and easy to extend.
- Mention any new config or setup steps in your PR description.

## Questions

If you are unsure whether your idea fits the project, open an issue first and discuss it before submitting a large change.
