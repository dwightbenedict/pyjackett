"""The generated OpenAPI document follows the usual documentation rules."""

from __future__ import annotations

import pytest

from pyjackett.interfaces.api_docs import API_TAGS

V1 = "/api/v1"
METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture
def spec(client):
    return client.get(f"{V1}/openapi.json").json()


def operations(spec):
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method in METHODS:
                yield method.upper(), path, operation


def refs(node):
    """Every ``$ref`` target in a document fragment."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from refs(value)


def test_info_block_describes_the_api(spec):
    info = spec["info"]
    assert info["title"] == "PyJackett API"
    assert info["summary"]
    assert info["license"]["name"] == "GPL-2.0-only"
    assert info["version"]
    for topic in ("Authentication", "Errors", "Versioning"):
        assert f"## {topic}" in info["description"]


def test_tags_are_declared_and_described(spec):
    declared = {tag["name"]: tag for tag in spec["tags"]}
    assert set(declared) == {tag["name"] for tag in API_TAGS}
    assert all(tag["description"] for tag in declared.values())
    for method, path, operation in operations(spec):
        assert operation["tags"], f"{method} {path}"
        assert set(operation["tags"]) <= set(declared), f"{method} {path}"


def test_every_operation_is_fully_described(spec):
    ids = []
    for method, path, operation in operations(spec):
        where = f"{method} {path}"
        assert operation.get("operationId"), where
        assert operation.get("summary"), where
        assert operation.get("description") or operation["summary"], where
        assert any(code.startswith("2") for code in operation["responses"]), (
            where
        )
        ids.append(operation["operationId"])
    assert len(ids) == len(set(ids))
    assert all(i[0].islower() and "_" not in i for i in ids)


def test_every_operation_declares_how_to_authenticate(spec):
    schemes = spec["components"]["securitySchemes"]
    assert schemes["ApiKey"] == {
        "type": "apiKey",
        "in": "query",
        "name": "apikey",
        "description": "The server's API key (also accepted as `passkey`).",
    }
    assert schemes["DashboardSession"]["in"] == "cookie"
    for method, path, operation in operations(spec):
        assert operation.get("security"), f"{method} {path}"


def test_every_reference_resolves(spec):
    for target in refs(spec):
        node = spec
        for part in target.removeprefix("#/").split("/"):
            node = node[part]


def test_path_parameters_are_described(spec):
    for method, path, operation in operations(spec):
        for parameter in operation.get("parameters", []):
            if parameter["in"] == "path":
                assert parameter.get("description"), f"{method} {path}"


def test_torznab_documents_its_query_parameters(spec):
    operation = spec["paths"][f"{V1}/indexers/{{indexer_id}}/results/torznab"][
        "get"
    ]
    parameters = {p["name"]: p for p in operation["parameters"]}
    for name in (
        "t",
        "q",
        "cat",
        "limit",
        "offset",
        "season",
        "ep",
        "imdbid",
        "tvdbid",
        "cache",
    ):
        assert parameters[name]["description"], name
        assert parameters[name]["in"] == "query", name
    assert "ignored" not in parameters
    assert "caps" in parameters["t"]["schema"]["enum"]
    assert "application/rss+xml" in operation["responses"]["200"]["content"]
    assert "429" in operation["responses"]


def test_json_search_documents_its_parameters_and_models(spec):
    search = spec["paths"][f"{V1}/indexers/{{indexer_id}}/results"]["get"]
    names = {p["name"] for p in search["parameters"]}
    assert {"query", "Category[]", "Tracker[]", "imdbid"} <= names
    schema = search["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert schema == {"$ref": "#/components/schemas/ManualSearchResponse"}
    release = spec["components"]["schemas"]["Release"]["properties"]
    assert release["size"]["description"] == "Bytes."


def test_stream_is_documented_as_ndjson(spec):
    stream = spec["paths"][f"{V1}/indexers/{{indexer_id}}/results/stream"][
        "get"
    ]
    assert "application/x-ndjson" in stream["responses"]["200"]["content"]


def test_unreachable_validation_errors_are_not_documented(spec):
    for method, path, operation in operations(spec):
        if "search" in operation["tags"]:
            assert "422" not in operation["responses"], f"{method} {path}"
    caps = spec["paths"][f"{V1}/indexers/{{indexer_id}}/caps"]["get"]
    assert "422" not in caps["responses"]
    listing = spec["paths"][f"{V1}/indexers"]["get"]
    assert "422" in listing["responses"]  # configured=maybe is invalid


def test_discovery_filters_are_described(spec):
    listing = spec["paths"][f"{V1}/indexers"]["get"]
    parameters = {p["name"]: p for p in listing["parameters"]}
    assert set(parameters) == {"configured", "type", "language", "tag", "q"}
    assert all(p["description"] for p in parameters.values())


def test_documented_models_match_what_the_api_returns(client, api_key):
    client.post(f"{V1}/indexers/faketracker/add")
    listing = client.get(f"{V1}/indexers").json()
    properties = client.get(f"{V1}/openapi.json").json()["components"][
        "schemas"
    ]["IndexerSummary"]["properties"]
    assert set(listing[0]) == set(properties)
    reply = client.get(
        f"{V1}/indexers/faketracker/results",
        params={"apikey": api_key, "query": "movie"},
    ).json()
    release_fields = client.get(f"{V1}/openapi.json").json()["components"][
        "schemas"
    ]["Release"]["properties"]
    assert set(reply["results"][0]) == set(release_fields)


def test_jackett_prefix_mirrors_every_v1_operation(spec):
    v1 = {p.removeprefix(V1): p for p in spec["paths"] if p.startswith(V1)}
    twins = {
        p.removeprefix("/api/v2.0"): p
        for p in spec["paths"]
        if p.startswith("/api/v2.0")
    }
    assert v1 and set(twins) == set(v1)
    for suffix, path in twins.items():
        for method, operation in spec["paths"][path].items():
            original = spec["paths"][v1[suffix]][method]
            assert operation["tags"] == ["jackett"]
            assert operation["operationId"] == (
                f"{original['operationId']}Jackett"
            )
            assert operation["parameters"] == original["parameters"]
