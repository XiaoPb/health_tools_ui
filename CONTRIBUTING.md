# Contributing

1. Install Python 3.12 and uv.
2. Run `uv sync --group dev`.
3. Add tests before changing behavior.
4. Run `uv run pytest` and `uv run ruff check .` before opening a pull request.
5. Query `.agents/skills/huskarui/query_metainfo.py` before using a PyHuskarUI component.

Keep command metadata aligned with the pinned ghealth-tools release. A dependency update must
include command parity, YAML round-trip, QML smoke, and packaging checks.

