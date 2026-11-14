"""Write the generated OpenAPI document to ``openapi.json``."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from pyjackett.app_context import build_context
from pyjackett.server.app import create_app

ROOT = Path(__file__).resolve().parent.parent


def main(target: Path = ROOT / "openapi.json") -> None:
    with tempfile.TemporaryDirectory() as data_dir:
        context = build_context(data_dir, include_bundled=False)
        spec = create_app(context, load_indexers=False).openapi()
    target.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "openapi.json")
