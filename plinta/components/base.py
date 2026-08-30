"""What every component is: config in, HTML out.

    render(config, user, **context) -> str

The config arriving is **already final**. A component does not fetch its own
configuration, does not merge a personalisation delta, and does not know whose
view it is rendering. Resolving that happens one layer up, in `blocks`.
"""
from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic import Field as PydanticField

if TYPE_CHECKING:
    from plinta.datasources.models import DataSource, DataSourceField


class Mode(StrEnum):
    """When ``get_data`` runs."""

    #: During page render; the rows are embedded in the HTML.
    INLINE = "inline"
    #: The page returns a mount point and the client asks for the data.
    FETCH = "fetch"


class ComponentConfig(BaseModel):
    """Base for a component's configuration schema.

    ``extra='forbid'``, so a typo is rejected when the block is saved rather
    than ignored when it renders.
    """

    model_config = ConfigDict(extra="forbid")

    #: Which columns to draw, in order. Empty means every permitted one, in
    #: the DataSource's order. This is where a saved view's column choice
    #: arrives, already merged (§8.2).
    columns: list[str] = PydanticField(default_factory=list)


class ConfigError(Exception):
    """A block's config does not match its component's schema."""

    def __init__(self, component: str, errors: Any):
        self.component = component
        self.errors = errors
        super().__init__(f"invalid config for {component!r}: {errors}")


def choose_columns(
    permitted: list[DataSourceField], config: ComponentConfig
) -> list[DataSourceField]:
    """The columns to draw, in the order the config asks for them.

    A config **narrows and reorders**; it can never widen. A name the viewer
    may not see is dropped rather than honoured, which is the same fail-closed
    rule an undeclared column already follows (§5.7) — so a saved view cannot
    become a way to ask for a column someone revoked.
    """
    names = getattr(config, "columns", None)
    if not names:
        return permitted
    by_name = {f.field_name: f for f in permitted}
    return [by_name[name] for name in names if name in by_name]


class Component:
    """One kind of widget.

    Subclasses declare a config schema, a default mode, and how to draw.
    """

    #: Shown in the picker when a block chooses a component.
    label: ClassVar[str] = ""

    #: Pydantic, with ``extra='forbid'``.
    config_schema: ClassVar[type[ComponentConfig]] = ComponentConfig

    #: Overridable per block (§7.3).
    mode: ClassVar[Mode] = Mode.FETCH

    def validate(self, config: dict[str, Any]) -> ComponentConfig:
        """Parse ``config`` against the schema.

        Raises:
            ConfigError: it does not match. Raised at save time, which is why
                the schema can afford to be strict.
        """
        try:
            return self.config_schema.model_validate(config or {})
        except ValidationError as exc:
            raise ConfigError(type(self).__name__, exc.errors()) from exc

    def get_data(
        self, config: ComponentConfig, user, *, datasource: DataSource
    ) -> tuple[Any, list[DataSourceField]]:
        """The rows and columns this component may draw.

        Both come from `datasources` with the user passed, so the narrowing
        happened below and nothing here can widen it. The joins a field
        renderer declared are collected on the way (§7.8), so a component
        written tomorrow gets them without knowing they exist.
        """
        from plinta.datasources import services
        from plinta.renderers.fields import joins_for

        fields = choose_columns(services.get_available_fields(datasource, user), config)
        select, prefetch = joins_for(fields)
        rows = services.get_queryset(
            datasource,
            user,
            columns=[f.field_name for f in fields],
            extra_select=sorted(select),
            extra_prefetch=sorted(prefetch),
        )
        return rows, fields

    def render(self, config: ComponentConfig, user, **context: Any) -> str:
        """Draw this component as HTML."""
        raise NotImplementedError
