"""Builds an indexer's configuration form from its ``settings`` block."""

from __future__ import annotations

from pyjackett.cardigann.definition import IndexerDefinition, SettingsField
from pyjackett.config.indexer_config import ConfigurationData
from pyjackett.config.items import (
    BoolItem,
    ConfigItem,
    DisplayInfoItem,
    MultiSelectItem,
    SingleSelectItem,
    StringItem,
)

DEFAULT_SETTINGS = (
    SettingsField(name="username", label="Username", type="text"),
    SettingsField(name="password", label="Password", type="password"),
)

COOKIE_HELP = (
    "<ol><li>Login to this tracker with your browser</li><li>If present in "
    "the login page, ensure you have the <b>Remember me</b> ticked and the "
    "<b>Log Me Out if IP Changes</b> unticked when you login</li><li>"
    "Navigate to the web site's torrent search page to view the list of "
    "available torrents for download</li><li>Open the <b>DevTools</b> panel "
    "by pressing <b>F12</b></li><li>Select the <b>Network</b> tab</li><li>"
    "Click on the <b>Doc</b> button (Chrome Browser) or <b>HTML</b> button "
    "(FireFox)</li><li>Refresh the page by pressing <b>F5</b></li><li>Click "
    "on the first row entry</li><li>Select the <b>Headers</b> tab on the "
    "Right panel</li><li>Find <b>'cookie:'</b> in the <b>Request "
    "Headers</b> section</li><li><b>Select</b> and <b>Copy</b> the whole "
    "cookie string <i>(everything after 'cookie: ')</i> and <b>Paste</b> "
    "here.</li></ol>"
)
FLARESOLVERR_HELP = (
    "This site may use Cloudflare DDoS Protection, therefore PyJackett "
    'requires <a href="https://github.com/FlareSolverr/FlareSolverr" '
    'target="_blank">FlareSolverr</a> to access it.'
)
USER_AGENT_HELP = (
    "<ol><li>From the same place you fetched the cookie,</li><li>Find "
    "<b>'user-agent:'</b> in the <b>Request Headers</b> section</li><li>"
    "<b>Select</b> and <b>Copy</b> the whole user-agent string <i>"
    "(everything after 'user-agent: ')</i> and <b>Paste</b> here.</li></ol>"
)


def _require_options(setting: SettingsField) -> dict[str, str]:
    if setting.options is None:
        raise ValueError(
            f"Options must be given for the '{setting.type}' type."
        )
    return setting.options


def _info_item(setting: SettingsField, title: str, definition_name: str):
    """Build the read-only help items; None for non-info types."""
    kind = setting.type
    if kind == "info":
        return DisplayInfoItem(title, setting.default)
    if kind == "info_category_8000":
        return DisplayInfoItem(
            f"About {definition_name} Categories",
            f"{definition_name} does not return categories in its search "
            "results.</br>To add to your Apps' Torznab indexer, replace all "
            "categories with 8000(Other).",
        )
    if kind == "info_cookie":
        return DisplayInfoItem("How to get the Cookie", COOKIE_HELP)
    if kind == "info_flaresolverr":
        return DisplayInfoItem("FlareSolverr", FLARESOLVERR_HELP)
    if kind == "info_useragent":
        return DisplayInfoItem("How to get the User-Agent", USER_AGENT_HELP)
    return None


def _input_item(setting: SettingsField, title: str) -> ConfigItem:
    kind = setting.type
    if kind == "checkbox":
        return BoolItem(title, setting.default == "true")
    if kind == "multi-select":
        return MultiSelectItem(
            title, _require_options(setting), setting.defaults
        )
    if kind == "select":
        return SingleSelectItem(
            title, _require_options(setting), setting.default
        )
    if kind in (None, "text", "password"):
        return StringItem(title, setting.default)
    raise ValueError(f"Invalid setting type '{kind}' specified.")


def create_item(setting: SettingsField, definition_name: str) -> ConfigItem:
    title = setting.label or setting.name
    info = _info_item(setting, title, definition_name)
    return info or _input_item(setting, title)


def build_configuration(definition: IndexerDefinition) -> ConfigurationData:
    """One form item per setting (username/password if none declared)."""
    config = ConfigurationData()
    settings = (
        DEFAULT_SETTINGS
        if definition.settings is None
        else (definition.settings)
    )
    for setting in settings:
        config.add_dynamic(setting.name, create_item(setting, definition.name))
    return config
