# PyJackett

A Python port of [Jackett](https://github.com/Jackett/Jackett): a Torznab and
TorrentPotato proxy that gives Sonarr, Radarr, Lidarr, Readarr and similar apps
one API over many torrent trackers.

It bundles Jackett's 585 Cardigann definitions, runs them with a Python port of
the engine, and adds 17 native indexers. Jackett's API paths work unchanged, so
existing clients only need a new base URL.

## Quick start

Requires Python 3.11 or newer.

```bash
pip install -e .
python -m pyjackett        # http://127.0.0.1:9117
```

Sign in to the dashboard (default `admin` / `admin`; change it), then point
your app at `http://<host>:9117/api/v2.0/indexers/<id>/results/torznab/` with
the API key shown there. Use `all` as the id to search every configured
indexer.

A fresh install configures 13 major public indexers. Set
`PYJACKETT_INDEXERS=all` to configure every public one.

The API is documented at `/api/v1/docs`.

## Specification and documentation

PyJackett aims to be a drop-in replacement for Jackett; the requirements are
in [SPEC.md](SPEC.md).

- [Torznab specification](https://torznab.github.io/spec-1.3-draft/): the
  protocol clients speak. Jackett publishes no OpenAPI document, so this and
  Jackett's behaviour are the API reference.
- [Jackett on GitHub](https://github.com/Jackett/Jackett) and its
  [wiki](https://github.com/Jackett/Jackett/wiki), including
  [server configuration](https://github.com/Jackett/Jackett/wiki/Jackett-Configuration),
  the [definition format](https://github.com/Jackett/Jackett/wiki/Definition-format)
  and [supported trackers](https://github.com/Jackett/Jackett/wiki/Supported-Trackers).
- PyJackett's API as an OpenAPI 3.1 document: [openapi.json](openapi.json)
  (also served at `/api/v1/openapi.json`, with interactive docs at
  `/api/v1/docs`). Regenerate it with `python scripts/export_openapi.py`.
  Jackett's `/api/v2.0` paths are documented too, under the `jackett` tag.

## Configuration

Settings live in `ServerConfig.json` (the same keys as Jackett's) in the data
directory: `PYJACKETT_DATA`, or a per-user default. Extra definitions go in
`<data directory>/Definitions/*.yml`.

| Variable | Purpose |
| --- | --- |
| `PYJACKETT_API_KEY`, `PYJACKETT_ADMIN_USERNAME`, `PYJACKETT_ADMIN_PASSWORD` | Fix the API key and dashboard login instead of generating them. |
| `PYJACKETT_KEY` | Passphrase that encrypts stored indexer secrets. |
| `PYJACKETT_INDEXERS` | Public indexers to configure at startup: unset for the default list, `all`, or comma-separated ids. |
| `PYJACKETT_MAX_CONCURRENCY` | Most indexer searches running at once, across all requests. |
| `PYJACKETT_SKIP_FAILING` | `1` leaves failing indexers out of `all` searches until their back-off ends. |
| `PYJACKETT_SYNC_DEFINITIONS` | `0` disables the daily definition update. |
| `PYJACKETT_DEFINITION_CACHE` | Parsed-definition cache file. Build it ahead of time with `python -m pyjackett --warm-cache`. |

## Deployment

```bash
docker build -t pyjackett .
docker run -p 9117:9117 -v pyjackett-data:/data \
  -e PYJACKETT_API_KEY=<key> \
  -e PYJACKETT_ADMIN_USERNAME=<user> \
  -e PYJACKETT_ADMIN_PASSWORD=<password> \
  pyjackett
```

On Render, use the Docker runtime (or `render.yaml`). The free tier wipes its
disk on every restart, so set the three variables above; it sleeps when idle;
and it cannot run FlareSolverr, so Cloudflare-protected indexers will not work.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

Code style and design rules are in `CLAUDE.md`.

## Not ported

The self-updater, the Windows service and tray icon, SOCKS4 proxies, and the
native C# indexers beyond the 17 included (most of those trackers are available
as YAML definitions).

## License

GPL-2.0, like the project it derives from. The bundled definitions come from
the Jackett repository.
