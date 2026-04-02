# Repository Guidelines

## Project Structure & Module Organization

Core Python code lives in `src/copaw/`. Key areas include `cli/` for the `copaw` entrypoints, `app/channels/` for channel adapters, `providers/` and `local_models/` for model integration, and `agents/skills/` for built-in skills. Tests live in `tests/`, with focused suites such as `tests/lock/`, `tests/store/`, and `tests/app/backup/`. Frontend apps are split into `console/` (main web UI) and `website/` (docs/site). Deployment helpers live under `deploy/` and `scripts/`; longer-form design notes are in `docs/superpowers/specs/`.

## Build, Test, and Development Commands

Use Python 3.10-3.13.

- `pip install -e ".[dev]"`: install CoPaw in editable mode with test and lint tooling.
- `pre-commit install && pre-commit run --all-files`: run the required local quality gate.
- `pytest`: run the Python test suite.
- `copaw init --defaults` then `copaw app`: initialize config and start the app locally.
- `cd console && npm ci && npm run dev`: run the Console in Vite dev mode.
- `cd console && npm run build`: type-check and build the Console.
- `cd website && pnpm install --frozen-lockfile && pnpm run build`: build the docs website and search index.

## Coding Style & Naming Conventions

Python uses 4-space indentation, `snake_case` modules, and Black with a 79-character line length. Pre-commit also runs mypy, flake8, pylint, Bandit, and basic file hygiene hooks. TypeScript/React in `console/` and `website/` uses 2-space indentation, `PascalCase` component names, and Prettier 3; `console/` additionally enforces ESLint rules via `npm run lint`. Follow existing directory naming such as `channel.py`, `registry.py`, and `test_redlock.py`.

## Testing Guidelines

Write Python tests with `pytest` and name files `test_*.py`. Keep tests close to the affected subsystem, for example `tests/channels/` or `tests/lock/`. Use `pytest -m "not slow"` when you need to skip slow cases. There is no dedicated frontend test runner in this repo today, so frontend changes should at minimum pass formatting and build checks.

## Commit & Pull Request Guidelines

Use Conventional Commits: `feat(scope): summary`, `fix(scope): summary`, `docs(scope): summary`. Recent history follows this closely, for example `feat(lock): ...` and `fix(lock): ...`. PR titles should use the same format. Include a clear description, linked issue, security notes when relevant, testing steps, and local verification output for `pre-commit run --all-files` and `pytest`. Update docs in `website/public/docs/` when behavior changes, and include screenshots for visible Console or website UI changes.
