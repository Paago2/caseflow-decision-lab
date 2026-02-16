# caseflow-decision-lab

## Developer Workflow

The three commands most developers should know are:

- `make up`
- `make test`
- `make check`

Install pre-commit hooks once per clone with `uv run pre-commit install`.

This project is now installed as a package from the `src/` layout (editable in containers), so imports resolve via the installed package and `PYTHONPATH` is no longer required for normal app/test execution.
