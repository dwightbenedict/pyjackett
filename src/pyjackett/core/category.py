"""A single Torznab category and its sub categories."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(eq=False)
class TorznabCategory:
    """A Torznab category; equality is defined by the numeric id only."""

    id: int
    name: str
    subcategories: list[TorznabCategory] = field(default_factory=list)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TorznabCategory) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def contains(self, other: TorznabCategory) -> bool:
        """Return True if ``other`` is this category or one of its children."""
        return self == other or other in self.subcategories

    def copy_without_subcategories(self) -> TorznabCategory:
        return TorznabCategory(self.id, self.name)

    def to_dict(self) -> dict[str, object]:
        return {"ID": self.id, "Name": self.name}
