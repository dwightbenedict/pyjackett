"""Request and response models; they feed the generated OpenAPI document."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Body of every failed management API call."""

    result: str = "error"
    error: str
    stacktrace: str | None = None


class ServerInfo(BaseModel):
    name: str
    version: str
    api_version: str
    update_channel: str


class UpdateCheck(BaseModel):
    current_version: str
    update_available: bool
    managed_by: str
    detail: str


class ApiKeyResponse(BaseModel):
    api_key: str


class RotateApiKeyRequest(BaseModel):
    password: str | None = Field(default=None, description="Current admin password, if one is set.")


class IndexerIds(BaseModel):
    ids: list[str] = Field(min_length=1)


class BulkOutcome(BaseModel):
    id: str
    status: str = Field(description="ok or error")
    error: str | None = None


class SearchOutcome(BaseModel):
    """Status of one tracker in a manual search."""

    id: str
    name: str
    status: str = Field(description="ok or error")
    results: int
    elapsed_ms: int
    error: str | None = None


class Release(BaseModel):
    """One torrent found by a tracker."""

    title: str | None = Field(None, examples=["Big Movie 2020 1080p"])
    guid: str | None = Field(None, description="Stable id at the tracker.")
    link: str | None = Field(None, description="Download URL, proxied through this server.")
    magnet_uri: str | None = None
    details: str | None = Field(None, description="Page of the release.")
    category: list[int] = Field(default_factory=list, description="Torznab category ids.")
    category_desc: str = Field("", examples=["Movies/HD"])
    size: int | None = Field(None, description="Bytes.")
    files: int | None = None
    grabs: int | None = Field(None, description="Times downloaded.")
    description: str | None = None
    seeders: int | None = None
    peers: int | None = Field(None, description="Leechers.")
    poster: str | None = None
    info_hash: str | None = None
    tracker: str | None = Field(None, description="Name of the tracker.")
    tracker_id: str | None = Field(None, description="Indexer id.")
    tracker_type: str | None = Field(None, examples=["public"])
    blackhole_link: str | None = None
    imdb: int | None = Field(None, description="IMDb id without `tt`.")
    year: int | None = None
    minimum_ratio: float | None = None
    minimum_seed_time: int | None = Field(None, description="Seconds.")
    download_volume_factor: float | None = Field(None, description="0 means freeleech.")
    upload_volume_factor: float | None = None
    publish_date: str | None = Field(None, description="ISO 8601.")
    first_seen: str | None = Field(None, description="ISO 8601.")
    gain: float = Field(0, description="Seeders per gigabyte.")


class ManualSearchResponse(BaseModel):
    indexers: list[SearchOutcome] = Field(
        description="Outcome per tracker; failures never fail the request."
    )
    results: list[Release] = Field(description="Newest first.")


class PotatoItem(BaseModel):
    release_name: str
    torrent_id: str | None = None
    details_url: str | None = None
    download_url: str | None = None
    imdb_id: str | None = None
    freeleech: bool
    type: str = "movie"
    size: int = Field(description="Megabytes.")
    leechers: int
    seeders: int
    publish_date: str | None = None


class PotatoResponse(BaseModel):
    results: list[PotatoItem]


class CategoryRef(BaseModel):
    ID: str
    Name: str


class IndexerSummary(BaseModel):
    """An indexer as listed by the discovery API."""

    id: str = Field(examples=["torrentscsv"])
    name: str
    description: str
    type: str | None = Field(None, description="public, semi-public or private.")
    configured: bool = Field(description="Only configured ones can search.")
    site_link: str
    alternativesitelinks: list[str]
    language: str = Field(examples=["en-US"])
    tags: list[str]
    last_error: str = Field(description="Empty when the last test passed.")
    potatoenabled: bool = Field(description="Whether the TorrentPotato endpoint can be used.")
    healthy: bool = Field(description="Answered recently without errors.")
    failing: bool = Field(description="Failed recently; retried with back-off.")
    latency_ms: int | None = Field(
        None,
        description="Time of the last successful search, if there was one.",
    )
    testing: bool = Field(False, description="A test of this indexer is running right now.")
    caps: list[CategoryRef] = Field(description="Flat list of categories.")


class Category(BaseModel):
    id: int = Field(examples=[2000])
    name: str = Field(examples=["Movies"])
    subcategories: list[Category]


class Limits(BaseModel):
    default: int | None
    max: int | None


class SearchModeCapability(BaseModel):
    available: bool
    parameters: list[str]


class Capabilities(BaseModel):
    """The ``t=caps`` document as JSON."""

    limits: Limits
    supports_raw_search: bool
    search_modes: dict[str, SearchModeCapability] = Field(
        description="Keyed by search, tv-search, movie-search, music-search and book-search."
    )
    categories: list[Category]


class Detail(BaseModel):
    """Body of a 401 from the discovery API."""

    detail: str = "Unauthorized"


class ImportOutcome(BaseModel):
    imported: list[str]
    skipped: list[str]
    restart_required: bool


Category.model_rebuild()


class StatsResponse(BaseModel):
    totals: dict[str, Any]
    indexers: dict[str, dict[str, Any]]


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    401: {"description": "Missing or invalid API key / session"},
    403: {"model": ErrorResponse, "description": "Wrong password"},
    404: {"model": ErrorResponse, "description": "Unknown indexer"},
    409: {"model": ErrorResponse, "description": "Needs credentials"},
    500: {"model": ErrorResponse, "description": "Unexpected failure"},
}
