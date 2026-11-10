# PyJackett

A Python port of [Jackett](https://github.com/Jackett/Jackett): a Torznab /
TorrentPotato proxy that gives Sonarr, Radarr, Lidarr, Readarr and friends a
single API over many torrent trackers.

* **585 trackers out of the box** – every Cardigann YAML definition shipped by
  Jackett is bundled and executed by a Python port of its engine.
* **Same API** – `/api/v2.0/indexers/{id}/results/torznab`, `/potato`, the
  `all` aggregate indexer, `tag:`/`type:`/`lang:` filter indexers, `/dl`,
  `/bh` (blackhole) and `/img` proxies.
* **A new dashboard** – single page, responsive, light/dark theme, no external
  assets.

## Quick start

```bash
pip install -e .            # Python 3.11+
python -m pyjackett         # http://127.0.0.1:9117
```

Options: `--data-dir`, `--port`, `--host`, `--debug`. Configuration lives in
`%APPDATA%\PyJackett` (Windows), `~/Library/Application Support/PyJackett`
(macOS) or `~/.config/pyjackett`; override with `PYJACKETT_DATA`.
Extra definitions can be dropped in `<data dir>/Definitions/*.yml`.
`ServerConfig.json` uses the same keys as Jackett's.

Add an indexer from the dashboard, then point your *arr app at
`http://host:9117/api/v2.0/indexers/<id>/results/torznab/` with the API key
shown in the header.

## Project layout

Modules are grouped by responsibility; each function and class does one thing.

```
src/pyjackett/
  core/        domain model: categories, capabilities, query, release
  utils/       stateless helpers: numbers, dates, cookies, urls, bencode, regex
  config/      server/indexer configuration, form items, encryption, stores
  http/        web client: request building, response parsing, session,
               certificate pinning, FlareSolverr
  cardigann/   the YAML engine: definition schema + loader, template language,
               filters, HTML/JSON selectors, login, search, download
  indexers/    base classes, health, retry, requester, manager,
               meta/ (aggregate + filters), native/ (Python indexers)
  services/    results cache, log cache, security, proxied links
  server/      FastAPI app: routes/, Torznab XML, query parsing, auth
  web/         the dashboard (HTML, CSS, ES modules)
  definitions/ the bundled Cardigann YAML files
```

## Development

```bash
pip install -e ".[dev]"
pytest                                  # unit + end-to-end tests (fake tracker)
ruff format src tests && ruff check src tests
pycodestyle src tests                   # PEP 8 (config in setup.cfg)
```

Code style: PEP 8, 79 columns, enforced by `ruff` and `pycodestyle`.
(`E203`/`W503` are ignored because PEP 8 itself formats slices and binary
operators that way.)

The dashboard JavaScript follows the same rules (79 columns, one
responsibility per function, related functions grouped in a module):

```bash
npm install
npm run format   # Prettier (config: .prettierrc.json)
npm run lint     # Prettier --check + ESLint (config: eslint.config.js)
```

ESLint enforces the 79-column limit, `===`, `const`/no `var`, braces, a
cyclomatic-complexity warning at 10 and a function-length warning at 50 lines
(Prettier puts each argument on its own line, so JS runs taller than Python).

## What is and is not ported

Ported: the Cardigann engine (templates, filters, HTML/XML/JSON parsing,
login methods `post`/`form`/`cookie`/`get`/`oneurl`, captchas, `before`,
`selectors` and `infohash` download rules), Torznab caps/search/RSS output,
TorrentPotato, manual search, results cache, per-indexer encrypted
configuration, proxy (HTTP/SOCKS5), FlareSolverr, OMDb IMDb fallback, blackhole,
admin password, log cleansing.

Not ported (yet):

* **Native C# indexers** – Jackett has ~80 hand-written trackers (RuTracker,
  AnimeBytes, Gazelle/Avistaz families, ...). The extension point exists
  (`indexers/native`, see `torrents_csv.py` for a worked example) and
  `torrentscsv` is ported; the rest are not. Most popular trackers are also
  available as YAML definitions.
* Self-update service, Windows service/tray, SOCKS4 proxies.
* Cardigann is executed on HTML parsed by *html5lib* (like Jackett's AngleSharp,
  it follows the HTML5 parsing rules) which is slower than lxml but matches the
  selectors the definitions were written for.

## License

GPL-2.0, like the project it is derived from. The bundled definitions come
from the Jackett repository.
