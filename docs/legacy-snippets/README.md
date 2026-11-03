# Archived implementation drafts

These files preserve the original mixed prose/code drafts for traceability. They
are reference material, not importable Python modules or deployment instructions.
Use the maintained implementation and commands documented at the repository root.

| Draft | Maintained location |
|---|---|
| `authentication-draft.md` | `src/tasico_shasta/config.py`, `src/tasico_shasta/api.py` |
| `optimization-draft.md` | `src/tasico_shasta/optimization.py` |
| `model-training-draft.md` | `src/tasico_shasta/modeling.py`, `src/tasico_shasta/cli.py` |
| `ci-cd-draft.md` | `.github/workflows/ci.yml`, `pyproject.toml`, `pytest.ini` |
| `quick-start-draft.md` | `README.md` |
| `requirements-draft.txt` | `pyproject.toml` |

The remaining connector, dashboard, database, report, and streaming drafts have
not yet been promoted to supported product modules. Do not treat their examples,
simulated data, or Go/No-Go thresholds as verified production behavior.
