"""OpenAPI documentation shared by the documented routes.

The search handlers read ``request.query_params`` themselves (the Torznab
protocol is lenient about what it accepts), so their parameters are
documented here instead of being declared on the handlers, which would add
validation that the protocol does not have.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Path
from fastapi.security import APIKeyCookie, APIKeyQuery

from pyjackett.server.auth import COOKIE_NAME
from pyjackett.server.schemas import Detail, ErrorResponse

API_TITLE = "PyJackett API"
API_SUMMARY = "Search many torrent trackers through one Torznab API."
API_DESCRIPTION = """\
PyJackett turns many torrent trackers into one search API. Point Sonarr,
Radarr, Lidarr, Readarr or Prowlarr at the **Torznab** endpoint, or use the
JSON endpoints from your own code.

## Authentication

Every endpoint takes the server's API key in the `apikey` query parameter
(`passkey` is accepted as an alias). The key is shown in the dashboard
header. The discovery endpoints also accept a dashboard session cookie.

## Indexers

An *indexer* is one tracker, or a group of them. `all` searches every
configured tracker; `tag:<name>`, `type:<name>`, `lang:<name>` and
`status:<healthy|failing|unknown>` search a filtered group. Only configured
indexers can be searched; `GET /indexers` lists what exists.

## Errors

* **Torznab** endpoints answer errors as an XML `<error code description>`
  document, usually with HTTP 200, as the protocol requires. Check the body.
* **JSON** search endpoints answer 401 (bad key, empty body) or 404 (unknown
  or unconfigured indexer, plain text).
* **Discovery** endpoints answer JSON: `{"detail": "Unauthorized"}` with 401
  or `{"result": "error", "error": "..."}` with 404.
* A tracker that fails or times out never fails a manual search: its entry
  in `indexers` carries `status: "error"` and the reason.

## Versioning

This is version 1 of the API, served under `/api/v1`. Jackett's
`/api/v2.0` paths keep working for existing clients but are not documented.
Results are cached for a few minutes; pass `cache=false` to Torznab to
bypass the cache.
"""
API_TAGS = [
    {
        "name": "search",
        "description": "Search the trackers of an indexer.",
    },
    {
        "name": "discovery",
        "description": "Find out which indexers exist and what they offer. "
        "Read-only.",
    },
]

IndexerId = Annotated[
    str,
    Path(
        description="Indexer id, e.g. `torrentscsv`, or `all` / a filter "
        "such as `tag:anime` to search several trackers at once.",
        examples=["all"],
    ),
]

# Declared as dependencies so the security requirement is documented; the
# actual check stays in ``server.auth``.
api_key_query = APIKeyQuery(
    name="apikey",
    scheme_name="ApiKey",
    description="The server's API key (also accepted as `passkey`).",
    auto_error=False,
)
session_cookie = APIKeyCookie(
    name=COOKIE_NAME,
    scheme_name="DashboardSession",
    description="Session cookie set by `POST /UI/Login`.",
    auto_error=False,
)


# ---- parameters -------------------------------------------------------------


def _query(
    name: str,
    description: str,
    schema: dict[str, Any],
    example: Any = None,
) -> dict[str, Any]:
    parameter: dict[str, Any] = {
        "name": name,
        "in": "query",
        "required": False,
        "description": description,
        "schema": schema,
    }
    if example is not None:
        parameter["example"] = example
    return parameter


_STRING = {"type": "string"}
_INTEGER = {"type": "integer"}


def _integers(*names: str, what: str) -> list[dict[str, Any]]:
    return [_query(n, f"{what} id.", _INTEGER) for n in names]


TORZNAB_PARAMETERS: list[dict[str, Any]] = [
    _query(
        "t",
        "The function. `caps` describes the indexer, `indexers` lists the "
        "members of a meta indexer, the rest search. Defaults to `search`.",
        {
            "type": "string",
            "enum": [
                "caps",
                "search",
                "tvsearch",
                "movie",
                "music",
                "book",
                "indexers",
            ],
            "default": "search",
        },
        "search",
    ),
    _query("q", "Free text to search for.", _STRING, "big movie"),
    _query(
        "cat",
        "Comma separated Torznab category ids; see `GET /categories`.",
        _STRING,
        "2000,5000",
    ),
    _query("limit", "Maximum number of releases.", _INTEGER, 50),
    _query(
        "offset",
        "Skip this many releases; only for trackers with pagination.",
        _INTEGER,
        0,
    ),
    _query(
        "extended",
        "`1` adds the attributes of the extended Torznab feed.",
        {"type": "integer", "enum": [0, 1]},
    ),
    _query(
        "cache",
        "`false` skips the results cache for this request.",
        {"type": "boolean", "default": True},
    ),
    _query("season", "Season number (`t=tvsearch`).", _INTEGER, 1),
    _query("ep", "Episode number (`t=tvsearch`).", _STRING, "2"),
    _query(
        "imdbid",
        "IMDb id, with or without the `tt` prefix.",
        _STRING,
        "tt0133093",
    ),
    *_integers("tvdbid", what="TheTVDB"),
    *_integers("rid", what="TVRage"),
    *_integers("tmdbid", what="TMDb"),
    *_integers("tvmazeid", what="TVmaze"),
    *_integers("traktid", what="Trakt"),
    *_integers("doubanid", what="Douban"),
    _query("year", "Release year.", _INTEGER, 2020),
    _query("genre", "Genre.", _STRING),
    _query("album", "Album (`t=music`).", _STRING),
    _query("artist", "Artist (`t=music`).", _STRING),
    _query("label", "Label (`t=music`).", _STRING),
    _query("track", "Track (`t=music`).", _STRING),
    _query("title", "Book title (`t=book`).", _STRING),
    _query("author", "Author (`t=book`).", _STRING),
    _query("publisher", "Publisher (`t=book`).", _STRING),
    _query(
        "configured",
        "With `t=indexers` on a meta indexer: only list configured "
        "(`true`) or unconfigured (`false`) members.",
        {"type": "boolean"},
    ),
]
POTATO_PARAMETERS: list[dict[str, Any]] = [
    _query("search", "Movie title to search for.", _STRING, "big movie"),
    _query(
        "imdbid",
        "IMDb id, with or without the `tt` prefix.",
        _STRING,
        "tt0133093",
    ),
]
MANUAL_PARAMETERS: list[dict[str, Any]] = [
    _query(
        "query",
        "Text to search for. A trailing `S01E02`, `E02` or `S01` selects a "
        "season and episode; `tt1234567` alone is an IMDb lookup.",
        _STRING,
        "Other Show S01E01",
    ),
    _query(
        "Category[]",
        "Comma separated Torznab category ids.",
        _STRING,
        "5000,5040",
    ),
    _query(
        "Tracker[]",
        "Comma separated indexer ids to search; default is all members.",
        _STRING,
        "torrentscsv,faketracker",
    ),
    _query("imdbid", "IMDb id.", _STRING, "tt0133093"),
    *_integers("tmdbid", "tvdbid", "tvmazeid", what="External"),
]


# ---- responses --------------------------------------------------------------

TORZNAB_CAPS_EXAMPLE = """\
<?xml version="1.0" encoding="UTF-8"?>
<caps>
  <server title="Fake Tracker"/>
  <limits default="100" max="100"/>
  <searching>
    <search available="yes" supportedParams="q"/>
    <tv-search available="yes" supportedParams="q,season,ep"/>
  </searching>
  <categories>
    <category id="2000" name="Movies"/>
  </categories>
</caps>
"""
TORZNAB_FEED_EXAMPLE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <title>Fake Tracker</title>
    <item>
      <title>Big Movie 2020 1080p</title>
      <guid>https://tracker.example/details/1</guid>
      <size>1610612736</size>
      <link>http://pyjackett:9117/dl/faketracker/?path=...&amp;file=Big+Movie</link>
      <pubDate>Fri, 01 Mar 2024 12:00:00 +0000</pubDate>
      <torznab:attr name="seeders" value="42"/>
      <torznab:attr name="peers" value="49"/>
      <torznab:attr name="category" value="2040"/>
    </item>
  </channel>
</rss>
"""
TORZNAB_ERROR_EXAMPLE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<error code="100" description="Invalid API Key"/>\n'
)
_XML = {"type": "string", "format": "xml"}

TORZNAB_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "The results feed, the capabilities document or, "
        "for protocol errors such as a bad key, an `<error>` document.",
        "content": {
            "application/rss+xml": {
                "schema": _XML,
                "example": TORZNAB_FEED_EXAMPLE,
            },
            "application/xml": {
                "schema": _XML,
                "examples": {
                    "caps": {
                        "summary": "t=caps",
                        "value": TORZNAB_CAPS_EXAMPLE,
                    },
                    "error": {
                        "summary": "Protocol error",
                        "value": TORZNAB_ERROR_EXAMPLE,
                    },
                },
            },
        },
    },
    400: {
        "description": "A request parameter is invalid (XML `<error>`).",
        "content": {"application/xml": {"schema": _XML}},
    },
    429: {
        "description": "The tracker asked to slow down (XML `<error>`).",
        "headers": {
            "Retry-After": {
                "description": "Seconds to wait before trying again.",
                "schema": {"type": "integer"},
            }
        },
        "content": {"application/xml": {"schema": _XML}},
    },
}
PLAIN_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or wrong API key. Empty body."},
    404: {
        "description": "The indexer is unknown, not configured, or cannot "
        "handle the query.",
        "content": {"text/plain": {"schema": {"type": "string"}}},
    },
}
NDJSON_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "One JSON object per line, emitted as soon as a "
        "tracker finishes: `indexer` is its outcome (see `indexers` of the "
        "plain search) and `results` its releases.",
        "content": {
            "application/x-ndjson": {
                "schema": {"type": "string"},
                "example": '{"indexer": {"id": "faketracker", "name": '
                '"Fake Tracker", "status": "ok", "results": 2, '
                '"elapsed_ms": 120, "error": null}, "results": []}\n',
            }
        },
    }
}
UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    401: {"model": Detail, "description": "Missing or wrong API key."},
}
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Unknown indexer."},
}


def _can_fail_validation(operation: dict[str, Any]) -> bool:
    """Search parameters are lenient; path strings always validate."""
    if "search" in operation.get("tags", []):
        return False
    parameters = operation.get("parameters", [])
    return any(p["in"] != "path" for p in parameters)


def _without_alias_parameter(operation: dict[str, Any]) -> None:
    """``ignored`` only exists for the undocumented ``/torznab/<path>``."""
    operation["parameters"] = [
        p
        for p in operation.get("parameters", [])
        if not (p["name"] == "ignored" and p["in"] == "query")
    ]


def finish_openapi(spec: dict[str, Any]) -> dict[str, Any]:
    """Remove what FastAPI generates but the API does not do.

    * the 422 of operations that can never answer it: the search handlers
      read their parameters themselves (see the module docstring) and a
      path string always validates, so it would only mislead generators;
    * the ``ignored`` query parameter of the Torznab operation.
    """
    for operations in spec.get("paths", {}).values():
        for operation in operations.values():
            _without_alias_parameter(operation)
            if not _can_fail_validation(operation):
                operation.get("responses", {}).pop("422", None)
    return spec
