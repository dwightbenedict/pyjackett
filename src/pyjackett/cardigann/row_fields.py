"""Extracts the ``search.fields`` of one result row into a release."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pyjackett.cardigann.definition import SearchBlock, SelectorBlock
from pyjackett.cardigann.release_fields import FieldContext, parse_field
from pyjackett.cardigann.template import Variables, apply_template
from pyjackett.core.category_mappings import CategoryMappings
from pyjackett.core.release import ReleaseInfo
from pyjackett.utils.text import is_blank

OPTIONAL_FIELDS = frozenset(
    {
        "imdb",
        "imdbid",
        "tmdbid",
        "rageid",
        "tvdbid",
        "tvmazeid",
        "traktid",
        "doubanid",
        "poster",
        "genre",
        "description",
    }
)


@dataclass(frozen=True)
class FieldSpec:
    """A ``fields`` entry: ``name|modifier|modifier`` plus its selector."""

    key: str
    block: SelectorBlock
    name: str = field(init=False)
    modifiers: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        name, *modifiers = self.key.split("|")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "modifiers", tuple(modifiers))

    @property
    def is_optional(self) -> bool:
        return (
            self.key in OPTIONAL_FIELDS
            or "optional" in self.modifiers
            or self.block.optional
        )

    @property
    def variable(self) -> str:
        return f".Result.{self.name}"


def field_specs(search: SearchBlock) -> list[FieldSpec]:
    return [FieldSpec(key, block) for key, block in (search.fields or [])]


Extractor = Callable[[FieldSpec, bool], str | None]


@dataclass
class RowParser:
    """Turns the fields of a row into a :class:`ReleaseInfo`."""

    specs: list[FieldSpec]
    categories: CategoryMappings
    indexer_id: str

    def parse_row(
        self,
        extract: Extractor,
        variables: Variables,
        search_url: str,
    ) -> ReleaseInfo:
        """Run every field; ``extract`` reads the raw value of one field."""
        release = ReleaseInfo()
        for spec in self.specs:
            self._parse_one(spec, release, extract, variables, search_url)
        return release

    def _parse_one(self, spec, release, extract, variables, search_url):
        value = None
        try:
            value = extract(spec, not spec.is_optional)
            if spec.is_optional and is_blank(value):
                value = apply_template(spec.block.default, variables)
                if is_blank(value):
                    variables[spec.variable] = None
                    return
            context = FieldContext(
                release,
                self.categories,
                search_url,
                self.indexer_id,
                list(spec.modifiers),
            )
            variables[spec.variable] = parse_field(value, spec.name, context)
        except Exception as error:
            if spec.variable not in variables or spec.is_optional:
                variables[spec.variable] = None
            if spec.is_optional:
                return
            raise RuntimeError(
                f"Error while parsing field={spec.key}, "
                f"selector={spec.block.selector}, "
                f"value={'<null>' if value is None else value}: {error}"
            ) from error
