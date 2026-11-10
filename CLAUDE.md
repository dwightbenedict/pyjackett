# PyJackett

Python port of Jackett (FastAPI + httpx). Source in `src/pyjackett`, tests in
`tests`.

## Commands

Use the project virtualenv (`.venv\Scripts\python.exe` on Windows).

- Tests: `python -m pytest -q`
- Lint: `python -m ruff check src tests`
- Format: `python -m ruff format src tests`

Before finishing any refactor or feature, tests, `ruff check` and
`ruff format --check` must all pass.

## Formatting rules

- Line length is 79 (ruff, pycodestyle and prettier all agree).
- Double quotes, trailing commas in multi-line constructs.
- Ruff rule sets: E, W, F, N, I, UP, B, SIM. Imports are sorted by ruff.
- Target Python 3.11. Start modules with `from __future__ import annotations`
  and a one-line docstring.
- Type-hint public signatures. Use `X | None`, not `Optional`.
- Match the surrounding code: comment density, naming and idiom. Section
  dividers look like `# ---- name ----...`; do not add them to small files.
- Working-tree files use CRLF (git `autocrlf`). Keep a file's existing line
  endings when scripting edits.

## Structure rules

- Single responsibility, for functions and classes alike. A function does one
  thing and its name says what; a class has one reason to change. If a
  description needs "and", split it. Extract steps into named helpers rather
  than growing a function with section comments.
- Bundle related functions in a module. A module covers one topic
  (`cardigann/login_form.py`, `utils/cookies.py`); do not mix unrelated
  helpers, and do not create a catch-all `helpers.py`.
- Bundle related modules in a package. A package covers one area
  (`cardigann/`, `http/`, `indexers/`, `config/`, `server/routes/`). Put a new
  module in the package that owns its topic, and create a new package only
  for a new area with several modules.
- When a module or class grows a second responsibility, split it before
  adding the feature, not after.

## Design rules (apply to refactors and new features)

### Dependency injection

- `app_context.build_context` is the only composition root. It builds and
  wires every long-lived service. New services are constructed there and
  passed in; nothing else instantiates collaborators.
- Take collaborators through the constructor. Do not reach for module-level
  singletons, `app.state` or `request.app` outside `server/deps.py`.
- Never call `time`, `datetime.now`, `asyncio.sleep`, `random` or
  `os.environ` inside a service. Inject a `Clock` (`utils/clock.py`:
  `now`, `time`, `monotonic`, `sleep`, `jitter`) and, for environment
  values, pass them in from `build_context` (`environ` mapping).
  `Stopwatch(clock)` measures durations.
- Depend on a `Protocol` when a collaborator has more than one plausible
  implementation or needs faking in tests (`SearchCache`, `SecretProtector`,
  `IndexerSource`, `ChallengeSolver`, `Clock`). Concrete defaults are allowed
  only for leaf factories such as `httpx.AsyncClient`.
- Indexers receive `IndexerDependencies`; add new shared collaborators there
  rather than adding constructor parameters to each indexer.
- Do not mutate collaborators after construction through public attributes;
  use constructor arguments or an explicit setter method.
- Global side effects (logger handlers, log levels) belong to an object with
  `attach`/`detach` tied to the app lifespan, not to `build_context`.

### Web layer

- Route handlers take `context: Context` (from `server/deps.py`) and use
  FastAPI `Depends` for cross-cutting checks. Do not call a context getter by
  hand.
- Depend on the narrowest service, not on `AppContext`: functions that only
  need security checks take a `SecurityService`, URL helpers take the config.
  Pass `context.security`, not `context`.
- Handlers stay thin: parsing and presentation only. Behaviour belongs in a
  service or on the indexer.
- Error presentation goes through `TorznabErrors`/`PlainErrors` and
  `GuardFailureError`, not ad-hoc responses.

### Indexers

- Extend through the template method in `BaseIndexer.results_for_query`.
  Override the hooks (`_accepts`, `_cached_result`, `_search_tracker`,
  `_post_process`, `_record_outcome`, `caches_results`) instead of copying
  the pipeline.
- A new kind of indexer is a new `IndexerSource`; `IndexerManager` is a
  facade over sources, `IndexerRegistry` and `MetaIndexerFactory`, which are
  all injected.
- Behaviour that belongs to one indexer (e.g. `verify()`) lives on the
  indexer, and failures raise domain exceptions from `core/exceptions.py`,
  never bare `RuntimeError`.
- Replace `if/elif` chains on a kind with a strategy table or an `@register`
  decorator (see Cardigann login methods and `cardigann/filters.py`).

## Tests

- Fake the network with `httpx.MockTransport`; build apps through
  `build_context(...)` (see `tests/conftest.py`).
- Fake time with a `Clock` stub (see `tests/test_injection.py`), never with
  real sleeps.
- New seams and new hooks get a test; a refactor must keep the existing
  tests passing without edits to their assertions.
- Routes are not all covered by tests. After changing a handler, run
  `ruff check` (it catches undefined names) and exercise the route.

## Commits

Small, focused commits with an imperative subject line and a body that
explains the why.
