"""Static file serving that makes browsers revalidate on every load."""

from __future__ import annotations

from typing import Any

from fastapi.staticfiles import StaticFiles
from starlette.responses import Response


class RevalidatingStaticFiles(StaticFiles):
    """Serve files with ``no-cache`` so edits show up on a plain reload.

    Browsers still keep a copy but check the ETag first, so unchanged
    files cost a 304 instead of a download.
    """

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response
