"""The full configuration form of one indexer."""

from __future__ import annotations

from typing import Any

from pyjackett.domain.config_items import (
    ConfigItem,
    HiddenStringItem,
    Protector,
    StringItem,
    TagsItem,
)

TAG_CHAR_SET = "A-Za-z0-9\\-\\._~"


class ConfigurationData:
    """Standard items (site link, cookie, tags, ...) plus dynamic ones."""

    def __init__(self) -> None:
        self.cookie_header = HiddenStringItem("CookieHeader")
        self.last_error = HiddenStringItem("LastError")
        self.site_link = StringItem("Site Link")
        self.tags = TagsItem("Tags", char_set=TAG_CHAR_SET)
        self._dynamic: dict[str, ConfigItem] = {}

    # ---- dynamic items ----------------------------------------------------

    def add_dynamic(self, key: str, item: ConfigItem) -> None:
        self._dynamic[key] = item

    def get_dynamic(self, key: str) -> ConfigItem | None:
        return self._dynamic.get(key)

    def dynamic_items(self) -> dict[str, ConfigItem]:
        return self._dynamic

    # ---- ordering -----------------------------------------------------------

    def all_items(self) -> list[ConfigItem]:
        """Site link first, tags last, everything else in between."""
        return [
            self.site_link,
            self.cookie_header,
            self.last_error,
            *self._dynamic.values(),
            self.tags,
        ]

    def _items_for(self, for_display: bool) -> list[ConfigItem]:
        if for_display:
            return [i for i in self.all_items() if i.can_be_shown]
        return [i for i in self.all_items() if i.can_be_saved]

    # ---- serialization ------------------------------------------------------

    def to_json(
        self, protector: Protector | None = None, for_display: bool = True
    ) -> list[dict[str, Any]]:
        rendered = (
            item.to_json(protector, for_display)
            for item in self._items_for(for_display)
        )
        return [data for data in rendered if data is not None]

    def load_values(
        self,
        stored: list[dict[str, Any]] | None,
        protector: Protector | None = None,
    ) -> None:
        """Copy the values of matching ids from ``stored`` into the items."""
        if not stored:
            return
        by_id = {entry.get("id"): entry for entry in stored}
        for item in self.all_items():
            if item.can_be_saved and item.id in by_id:
                item.from_json(by_id[item.id], protector)
