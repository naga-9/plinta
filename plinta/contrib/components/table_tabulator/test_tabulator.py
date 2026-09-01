"""The interactive table, and the client it proves."""
import json
import pathlib

import pytest

from plinta.components.base import Mode
from plinta.components.registry import get
from plinta.utils.assets import scripts, stylesheets

PACKAGE = pathlib.Path(__file__).resolve().parent


def test_it_sits_beside_cores_own():
    """`capability_implementation`, so neither is privileged in the registry."""
    assert get("table_tabulator")
    assert get("table_plinta")


def test_it_fetches_by_default_and_may_be_inlined():
    """Fetch is what the vendor is for; inline is Tabulator's own local
    pagination, which a five-row related grid wants."""
    component = get("table_tabulator")
    assert component.mode == Mode.FETCH
    assert component.supported_modes == frozenset({Mode.INLINE, Mode.FETCH})


def test_it_does_not_share_cores_config():
    """The two draw differently, so a block moving between them is validated
    at save rather than silently keeping keys the new one ignores."""
    from plinta.components.base import ConfigError

    with pytest.raises(ConfigError):
        get("table_tabulator").validate({"striped": True})


def test_the_vendor_is_in_the_package():
    vendor = PACKAGE / "static" / "plinta" / "tabulator"
    assert (vendor / "tabulator.min.js").exists()
    assert (vendor / "tabulator_simple.min.css").exists()
    assert (PACKAGE / "LICENSE-tabulator").read_text(encoding="utf-8").strip()


def test_the_adapter_loads_after_the_vendor_and_the_client():
    """It registers with one and calls into the other."""
    paths = [s.path for s in scripts()]
    assert paths.index("plinta/tabulator/tabulator.min.js") < paths.index(
        "plinta/tabulator/adapter.js"
    )
    assert "plinta/tabulator/tabulator_simple.min.css" in [
        s.path for s in stylesheets()
    ]


def test_the_mount_carries_its_url_and_config():
    """The page hands over the URL: only it knows which placement this is, and
    the feed is placement-scoped."""
    component = get("table_tabulator")
    html = component.render(
        component.config_schema(page_size=25),
        None,
        data_url="/pages/1/blocks/2/data/",
    )
    assert 'data-plinta-mount="table_tabulator"' in html
    assert 'data-plinta-url="/pages/1/blocks/2/data/"' in html
    body = json.loads(html.split(">", 2)[2].split("</script>")[0]
                      .replace("\u003c", "<").replace("\u003e", ">")
                      .replace("\u0026", "&"))
    assert body["config"]["page_size"] == 25
    assert "rows" not in body, "fetch mode asks for its rows"


def test_the_payload_cannot_close_its_own_tag():
    """A value containing `</script>` would end the tag it sits in."""
    component = get("table_tabulator")
    html = component.render(
        component.config_schema(empty_text="</script><img src=x onerror=alert(1)>"),
        None,
        data_url="/x/",
    )
    assert "</script><img" not in html
    assert "\u003c" in html
