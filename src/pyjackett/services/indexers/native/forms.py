"""Configuration forms shared by the native indexers."""

from __future__ import annotations

from pyjackett.domain.config_items import (
    BoolItem,
    DisplayInfoItem,
    StringItem,
)
from pyjackett.domain.indexer_config import ConfigurationData

USERNAME = "username"
PASSWORD = "password"
PID = "pid"


def add_instructions(data: ConfigurationData, message: str | None) -> None:
    if message:
        data.add_dynamic("instructions", DisplayInfoItem("", message))


def add_basic_login(data: ConfigurationData, message: str | None = None):
    data.add_dynamic(USERNAME, StringItem("Username"))
    data.add_dynamic(PASSWORD, StringItem("Password"))
    add_instructions(data, message)


def add_basic_login_with_pid(data: ConfigurationData, message: str | None = None) -> None:
    data.add_dynamic(USERNAME, StringItem("Username"))
    data.add_dynamic(PASSWORD, StringItem("Password"))
    data.add_dynamic(PID, StringItem("Pid"))
    add_instructions(data, message)


def add_basic_login_with_email(data: ConfigurationData, message: str | None = None) -> None:
    data.add_dynamic("email", StringItem("Email"))
    data.add_dynamic(PASSWORD, StringItem("Password"))
    add_instructions(data, message)


def add_api_key(data: ConfigurationData, name: str = "APIKey") -> None:
    data.add_dynamic("apikey", StringItem(name, ""))


def add_flag(data: ConfigurationData, name: str, value: bool = False):
    data.add_dynamic(name.lower().replace(" ", ""), BoolItem(name, value))


def text(data: ConfigurationData, key: str) -> str:
    """The value of a string item (empty when unset)."""
    item = data.get_dynamic(key)
    return (getattr(item, "value", None) or "").strip() if item else ""


def flag(data: ConfigurationData, key: str) -> bool:
    item = data.get_dynamic(key)
    return bool(getattr(item, "value", False)) if item else False
