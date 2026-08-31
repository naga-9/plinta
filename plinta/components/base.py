"""What every component is: config in, HTML out.

    render(config, user, **context) -> str

The config arriving is **already final**. A component does not fetch its own
configuration, does not merge a personalisation delta, and does not know whose
view it is rendering. Resolving that happens one layer up, in `blocks`.
"""
from __future__ import annotations

from collections.abc import Callable
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


class Padding(StrEnum):
    """How much room the card gives a component's own markup.

    Declared rather than styled by the component, because the padding lives on
    the card's body — the shell's element, which the component renders
    *inside* and cannot reach. A component that wrapped itself in a padded div
    would be a second box competing with the card's own scrolling.

    A name from the scale rather than a length: a raw `13px` is the same
    defect a raw `#f0f0f0` is.
    """

    #: Room to read. What most things want.
    DEFAULT = "default"
    #: None: the component's own markup goes edge to edge. A table's cells
    #: already carry padding, and the card's would double it at the rim.
    NONE = "none"
    #: Half. For markup that is dense on purpose but not edge to edge.
    TIGHT = "tight"


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

    With no columns named, the **default set** is drawn: the permitted columns
    marked `visible`. That is what "shown by default" means — a column can be
    left out of the default and still be asked for by name, because the
    permission and not the flag is what decides whether it may be seen.
    """
    names = getattr(config, "columns", None)
    if not names:
        return [f for f in permitted if getattr(f, "visible", True)]
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

    #: The default. A block may override it, within ``supported_modes``.
    mode: ClassVar[Mode] = Mode.FETCH

    #: Which modes this component can actually draw in. A component with no
    #: client adapter cannot be fetched; one that embeds a finished blob may
    #: have nothing to fetch. None means both.
    supported_modes: ClassVar[frozenset[Mode] | None] = None

    #: How much room the card gives it. Most things want room to read; a
    #: table draws to the edge because its cells are already padded.
    padding: ClassVar[Padding] = Padding.DEFAULT

    #: Whether this component reads a model. False for a **content**
    #: component — text, an unconditional banner — whose config *is* its data.
    #: Declared here rather than listed in core, so a third party's own text
    #: component can say so too; a set of names in core would leave them
    #: demanding a DataSource with no way to refuse.
    needs_data: ClassVar[bool] = True

    def supports(self, mode: Mode) -> bool:
        """Whether this component can draw in ``mode``."""
        return self.supported_modes is None or mode in self.supported_modes

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
        self,
        config: ComponentConfig,
        user,
        *,
        datasource: DataSource,
        narrow: Callable[[Any], Any] | None = None,
    ) -> tuple[Any, list[DataSourceField]]:
        """The rows and columns this component may draw.

        Both come from `datasources` with the user passed, so the narrowing
        happened below and nothing here can widen it. The joins a field
        renderer declared are collected on the way (§7.8), so a component
        written tomorrow gets them without knowing they exist.

        ``narrow`` narrows the rows further. It is opaque here: the caller
        composes whatever it means, which is how a block applies its locked
        filter without a component learning that blocks exist.
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
        return (narrow(rows) if narrow else rows), fields

    def render(self, config: ComponentConfig, user, **context: Any) -> str:
        """Draw this component as HTML."""
        raise NotImplementedError
