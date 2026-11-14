"""Command line entry point: ``python -m pyjackett``."""

from __future__ import annotations

import argparse
import logging
import os

import uvicorn

from pyjackett import __version__
from pyjackett.domain.default_indexers import DEFAULT_PUBLIC_INDEXERS
from pyjackett.interfaces.api import create_app
from pyjackett.services.environment import sync_definitions_from
from pyjackett.wiring import build_context

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
KEEP_ALIVE_SECONDS = 5  # idle connections are memory on a small host


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pyjackett", description="API support for your favorite trackers"
    )
    parser.add_argument("--data-dir", help="folder for configuration files")
    parser.add_argument("--port", type=int, help="override the saved port")
    parser.add_argument("--host", help="override the bind address")
    parser.add_argument("--debug", action="store_true", help="verbose logs")
    parser.add_argument(
        "--warm-cache",
        action="store_true",
        help="parse the definitions into the cache, then exit (build step)",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args(argv)


def configure_logging(debug: bool) -> None:
    logging.basicConfig(format=LOG_FORMAT)
    logging.getLogger("pyjackett").setLevel(
        logging.DEBUG if debug else logging.INFO
    )


def bind_address(config, override: str | None) -> str:
    if override:
        return override
    return "0.0.0.0" if config.allow_external else config.local_bind_address


def warm_definition_cache(data_dir: str | None) -> int:
    """Parse every definition once so later starts can skip the work."""
    context = build_context(data_dir)
    context.indexers.init_indexers()
    return len(context.indexers.all_indexers())


def main(argv: list[str] | None = None) -> None:
    arguments = parse_arguments(argv)
    configure_logging(arguments.debug)
    if arguments.warm_cache:
        count = warm_definition_cache(arguments.data_dir)
        logging.getLogger(__name__).info("Cached %d indexers", count)
        return
    context = build_context(
        arguments.data_dir,
        configure_public=True,
        default_public=DEFAULT_PUBLIC_INDEXERS,
        sync_definitions=sync_definitions_from(os.environ),
    )
    config = context.config
    logging.getLogger(__name__).info(
        "PyJackett %s - data folder: %s", __version__, context.data_dir
    )
    uvicorn.run(
        create_app(context),
        host=bind_address(config, arguments.host),
        port=arguments.port or config.port,
        log_level="warning",
        access_log=False,
        timeout_keep_alive=KEEP_ALIVE_SECONDS,
    )


if __name__ == "__main__":
    main()
