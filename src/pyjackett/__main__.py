"""Command line entry point: ``python -m pyjackett``."""

from __future__ import annotations

import argparse
import logging

import uvicorn

from pyjackett import __version__
from pyjackett.app_context import build_context
from pyjackett.server.app import create_app

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pyjackett", description="API support for your favorite trackers"
    )
    parser.add_argument("--data-dir", help="folder for configuration files")
    parser.add_argument("--port", type=int, help="override the saved port")
    parser.add_argument("--host", help="override the bind address")
    parser.add_argument("--debug", action="store_true", help="verbose logs")
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


def main(argv: list[str] | None = None) -> None:
    arguments = parse_arguments(argv)
    configure_logging(arguments.debug)
    context = build_context(arguments.data_dir)
    config = context.config
    logging.getLogger(__name__).info(
        "PyJackett %s - data folder: %s", __version__, context.data_dir
    )
    uvicorn.run(
        create_app(context),
        host=bind_address(config, arguments.host),
        port=arguments.port or config.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
