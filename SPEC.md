# PyJackett specification: drop-in replacement for Jackett

Status: draft. Requirement IDs (`C-1`, ...) are for tests and issues to cite.

## 1. Goal

A running Jackett instance can be swapped for PyJackett by changing only the
base URL (and, if not reused, the API key). Sonarr, Radarr, Lidarr, Readarr,
Prowlarr, CouchPotato and similar clients keep working without reconfiguration
beyond that.

## 2. Reference material

| What | Link |
| --- | --- |
| Torznab protocol (the contract clients rely on) | <https://torznab.github.io/spec-1.3-draft/> |
| Jackett source and README | <https://github.com/Jackett/Jackett> |
| Jackett wiki (configuration, FAQ, troubleshooting) | <https://github.com/Jackett/Jackett/wiki> |
| Jackett server configuration keys | <https://github.com/Jackett/Jackett/wiki/Jackett-Configuration> |
| Cardigann definition format | <https://github.com/Jackett/Jackett/wiki/Definition-format> |
| Supported trackers | <https://github.com/Jackett/Jackett/wiki/Supported-Trackers> |
| PyJackett's API (OpenAPI 3.1) | [openapi.json](openapi.json), also at `/api/v1/openapi.json` |

Jackett publishes no OpenAPI document for its HTTP API; the Torznab spec plus
Jackett's behaviour are the reference. Where they disagree, Jackett's behaviour
wins.

## 3. Compatibility surface

### 3.1 Required: wire-compatible

| ID | Requirement |
| --- | --- |
| C-1 | `GET /api/v2.0/indexers/{id}/results/torznab/[api]` answers `t=caps`, `search`, `tvsearch`, `movie`, `music`, `book` with Torznab XML (RSS 2.0 + `torznab:attr`). |
| C-2 | `{id}` accepts a configured indexer id, `all`, and Jackett's filter ids (`tag:x`, `type:public`, `type:private`, `status:healthy`, `test:passed`, `test:failed`, `lang:xx`). |
| C-3 | Query parameters: `apikey`, `q`, `cat`, `limit`, `offset`, `season`, `ep`, `imdbid`, `tvdbid`, `tmdbid`, `tvmazeid`, `rid`, `doubanid`, `artist`, `album`, `year`, `genre`, `title`, `author`, `extended`. Unknown parameters are ignored. |
| C-4 | Errors use Torznab `<error code= description=>` with Jackett's codes (100 bad key, 200 missing parameter, 201 unsupported function, 900 indexer failure). HTTP status stays 200 for protocol errors, as Jackett does. |
| C-5 | Release items carry `title`, `guid`, `link`, `comments`, `pubDate`, `size`, `enclosure`, and attrs `category`, `seeders`, `peers`, `grabs`, `downloadvolumefactor`, `uploadvolumefactor`, `infohash`, `magneturl`, `imdbid`, `tvdbid`, `tmdbid`, `minimumratio`, `minimumseedtime` when known. |
| C-6 | `link` points to `/dl/{id}/?jackett_apikey=...&path=...&file=...`; PyJackett fetches the torrent (with the tracker session) so credentials never reach the client. Magnet links pass through. |
| C-7 | `GET /api/v2.0/indexers/{id}/results/potato/` implements TorrentPotato for indexers with movie categories. |
| C-8 | `GET /api/v2.0/indexers/all/results` returns Jackett's JSON shape (`Results`, `Indexers`) for scripts built on it. |
| C-9 | Legacy paths `/torznab/{id}`, `/torznab/{id}/api`, `/potato/{id}` and `/bh/{id}`, `/img/{id}` keep working. |
| C-10 | The Torznab API key is checked on every API call, as Jackett does. A key can be pinned with `PYJACKETT_API_KEY` so clients need no change. |
| C-11 | A reverse-proxy `BasePathOverride` in `ServerConfig.json` moves every route under that prefix. |

### 3.2 Required: configuration compatible

| ID | Requirement |
| --- | --- |
| K-1 | `ServerConfig.json` uses Jackett's key names (`Port`, `AllowExternal`, `APIKey`, `AdminPassword`, `BasePathOverride`, `OmdbApiKey`, `ProxyType`, `ProxyUrl`, `ProxyPort`, `ProxyUsername`, `ProxyPassword`, `FlareSolverrUrl`, ...). Unknown keys are preserved on save. |
| K-2 | Indexer config files in `Indexers/{id}.json` use Jackett's `[{id, value}]` format, so a Jackett data directory can be copied over. Secrets are re-encrypted on first write. |
| K-3 | Default port is 9117. |
| K-4 | Cardigann definitions in the Jackett YAML dialect load unchanged, including user definitions in `Definitions/*.yml`, and all Jackett template functions, filters and selectors. |
| K-5 | Definitions are synced from the Jackett repository daily; `PYJACKETT_SYNC_DEFINITIONS=0` disables it. |

### 3.3 Required: behavioural parity

| ID | Requirement |
| --- | --- |
| B-1 | Category mapping: tracker categories map to Newznab categories (including 100000+ custom ids); `cat` filters on both. |
| B-2 | Capabilities are generated per indexer from its definition (supported search modes and params); clients that read `t=caps` configure themselves from it. |
| B-3 | Season/episode and IMDb/TVDB ID searches fall back to text search the way Jackett does when the tracker lacks ID search. |
| B-4 | Failing indexers are reported without failing an `all` search; one slow indexer must not block the rest beyond the search timeout. |
| B-5 | Results are cached per query; identical requests within the cache window do not hit the tracker. |
| B-6 | Login, captcha, cookie and session handling follow the definition's `login` block; sessions survive restarts. |
| B-7 | Proxy (HTTP/SOCKS5) and FlareSolverr are honoured when configured. |

### 3.4 Not required (documented deviations)

- The Jackett admin API (`/api/v2.0/indexers`, `/api/v2.0/server/config`) is
  best-effort: the shapes the dashboard and Prowlarr use are supported, not
  every field.
- No self-updater, Windows service or tray icon, SOCKS4 proxies, or native C#
  indexers beyond the 17 ported.
- PyJackett adds `/api/v1/*` (OpenAPI-documented) and a streaming search; these
  are extensions and may change.

## 4. Non-functional

| ID | Requirement |
| --- | --- |
| N-1 | Runs on Python 3.11+, one process, no external services. |
| N-2 | Fits the Render free tier: 512 MB RAM, sleeping when idle, ephemeral disk (hence env-var configuration and a definition cache). |
| N-3 | A cold search to a single healthy indexer answers within the tracker's latency plus 200 ms of overhead. |
| N-4 | Credentials are never logged or put in client-visible URLs. |

## 5. Acceptance

A change is compatible when:

1. Contract tests replay recorded Jackett responses (fixtures in
   `tests/fixtures`) against PyJackett and the XML/JSON matches structurally
   (ordering of attrs and `pubDate` formatting aside).
2. Each Cardigann definition in the bundled set loads and produces caps
   without error (`--warm-cache` is the smoke test).
3. Manual check: add PyJackett as a Torznab indexer in Sonarr, Radarr and
   Prowlarr using the Jackett URL form; "Test" passes and an interactive search
   returns releases.
4. Copy a real Jackett data directory over PyJackett's; the same indexers
   appear configured and a search succeeds.

## 6. Open questions

- Exact coverage of Jackett's admin JSON API needed by Prowlarr's Jackett-import
  and by third-party dashboards.
- Whether `ServerConfig.json` `BlackholeDir` and Jackett's `.torrent`
  blackhole download (`/bh`) need full parity.
- A compatibility test matrix per Jackett release (which version is the
  reference).
