"""Detection of trackers that moved to another domain."""

from __future__ import annotations

from urllib.parse import urlsplit

from pyjackett.http.models import WebResult
from pyjackett.utils.text import is_blank


def redirect_domain_hint(
    request_url: str, redirect_url: str | None, site_link: str
) -> str | None:
    """New site link if a request to the site was redirected off-domain."""
    if is_blank(redirect_url) or not request_url.startswith(site_link):
        return None
    target, site = urlsplit(redirect_url), urlsplit(site_link)
    if target.hostname != site.hostname:
        return f"{target.scheme}://{target.netloc}/"
    return None


def result_domain_hint(result: WebResult, site_link: str) -> str | None:
    return redirect_domain_hint(
        result.request.url, result.redirecting_to, site_link
    )
