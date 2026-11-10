"""The form fields an indexer configuration is made of.

Each item knows how to render itself for the dashboard form and how to
persist/restore its value. Item ids are the lower-cased name without spaces,
which is what the dashboard posts back.
"""

from __future__ import annotations

import base64
import re
from typing import Any, Protocol

PASSWORD_PLACEHOLDER = "|||%%PREVJACKPASSWD%%|||"


class Protector(Protocol):
    def protect(self, plain_text: str | None) -> str:
        """Protocol method."""

    def unprotect(self, token: str | None) -> str:
        """Protocol method."""


class ConfigItem:
    """Base class: a named, typed value."""

    can_be_shown = True
    can_be_saved = True

    def __init__(self, name: str, item_type: str) -> None:
        self.name = name
        self.item_type = item_type

    @property
    def id(self) -> str:
        return self.name.replace(" ", "").lower()

    def _base_json(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.item_type, "name": self.name}

    def to_json(
        self, protector: Protector | None = None, for_display: bool = True
    ) -> dict[str, Any] | None:
        return None

    def from_json(
        self, data: dict[str, Any], protector: Protector | None = None
    ) -> None:
        """Restore the value from a stored or posted JSON object."""


class StringItem(ConfigItem):
    """A single line of text; passwords are encrypted when saved."""

    def __init__(
        self,
        name: str,
        value: str | None = None,
        item_type: str = "inputstring",
    ) -> None:
        super().__init__(name, item_type)
        self.value = value

    @property
    def _is_password(self) -> bool:
        return self.name.lower() == "password"

    def to_json(self, protector=None, for_display=True):
        data = self._base_json()
        value = self.value
        if self._is_password:
            value = protector.protect(value) if protector else value or ""
        data["value"] = value
        return data

    def from_json(self, data, protector=None):
        value = data.get("value")
        if not self._is_password:
            self.value = value
        elif value != PASSWORD_PLACEHOLDER:
            self.value = protector.unprotect(value) if protector else value


class HiddenStringItem(StringItem):
    """Persisted but never shown (cookies, last error)."""

    can_be_shown = False

    def __init__(self, name: str, value: str | None = None) -> None:
        super().__init__(name, value, "hiddendata")

    def from_json(self, data, protector=None):
        self.value = data.get("value")


class DisplayInfoItem(StringItem):
    """Read-only HTML snippet shown in the form."""

    can_be_saved = False

    def __init__(self, name: str, value: str | None = None) -> None:
        super().__init__(name, value, "displayinfo")

    def to_json(self, protector=None, for_display=True):
        data = self._base_json()
        data["value"] = self.value
        return data


class BoolItem(ConfigItem):
    def __init__(self, name: str, value: bool = False) -> None:
        super().__init__(name, "inputbool")
        self.value = value

    def to_json(self, protector=None, for_display=True):
        return {**self._base_json(), "value": self.value}

    def from_json(self, data, protector=None):
        self.value = bool(data.get("value"))


class DisplayImageItem(ConfigItem):
    """An image (e.g. a captcha) shown as a data URL."""

    can_be_saved = False

    def __init__(self, name: str, value: bytes | None = None) -> None:
        super().__init__(name, "displayimage")
        self.value = value

    def to_json(self, protector=None, for_display=True):
        encoded = base64.b64encode(self.value or b"").decode("ascii")
        return {
            **self._base_json(),
            "value": f"data:image/jpeg;base64,{encoded}",
        }


class SingleSelectItem(ConfigItem):
    def __init__(
        self,
        name: str,
        options: dict[str, str],
        value: str | None = None,
    ) -> None:
        super().__init__(name, "inputselect")
        self.options = options
        self.value = value

    def to_json(self, protector=None, for_display=True):
        return {
            **self._base_json(),
            "value": self.value,
            "options": dict(self.options),
        }

    def from_json(self, data, protector=None):
        self.value = data.get("value")


class MultiSelectItem(ConfigItem):
    def __init__(
        self,
        name: str,
        options: dict[str, str],
        values: list[str] | None = None,
    ) -> None:
        super().__init__(name, "inputcheckbox")
        self.options = options
        self.values = list(values or [])

    def to_json(self, protector=None, for_display=True):
        return {
            **self._base_json(),
            "values": list(self.values),
            "options": dict(self.options),
        }

    def from_json(self, data, protector=None):
        values = data.get("values")
        if values is not None:
            self.values = [str(value) for value in values]


class PasswordItem(ConfigItem):
    def __init__(self, name: str, value: str | None = None) -> None:
        super().__init__(name, "password")
        self.value = value

    def to_json(self, protector=None, for_display=True):
        if not self.value:
            shown = ""
        elif for_display:
            shown = PASSWORD_PLACEHOLDER
        else:
            shown = protector.protect(self.value) if protector else self.value
        return {**self._base_json(), "value": shown}

    def from_json(self, data, protector=None):
        value = data.get("value")
        if value != PASSWORD_PLACEHOLDER:
            self.value = protector.unprotect(value) if protector else value


class TagsItem(ConfigItem):
    """A free list of lower-case tags (used to group indexers)."""

    def __init__(
        self,
        name: str,
        char_set: str | None = None,
        separator: str = ",",
    ) -> None:
        super().__init__(name, "inputtags")
        self.values: list[str] = []
        self.separator = separator
        self.pattern = f"^[{char_set}]+$" if char_set else None
        self.delimiters = f"[^{char_set}]+" if char_set else None

    def to_json(self, protector=None, for_display=True):
        data = {**self._base_json(), "value": self.separator.join(self.values)}
        if for_display:
            data["separator"] = self.separator
            if self.delimiters:
                data["delimiters"] = self.delimiters
            if self.pattern:
                data["pattern"] = self.pattern
        return data

    def from_json(self, data, protector=None):
        value = data.get("value")
        if value is None:
            return
        splitter = self.delimiters or f"{re.escape(self.separator)}+"
        tags = [t.strip().lower() for t in re.split(splitter, value)]
        if self.pattern:
            tags = [t for t in tags if re.match(self.pattern, t)]
        self.values = list(dict.fromkeys(tags))
