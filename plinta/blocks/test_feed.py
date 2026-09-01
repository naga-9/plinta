"""The rows a fetching widget asks for."""

from plinta.blocks.feed import column, requested


class Query(dict):
    """Enough of a QueryDict for `requested`."""

    def get(self, name, default=None):
        return dict.get(self, name, default)


class Field:
    def __init__(self, name, sorter="string", filterable=False, fmt="", width=None):
        self.field_name = name
        self.label = name.title()
        self.sorter = sorter
        self.filterable = filterable
        self.format = fmt
        self.width = width


# --- what the client may ask for ---------------------------------------------


def test_paging_and_ordering_are_read():
    asked = requested(Query(page="3", size="25", sort="-price,title"))
    assert asked["page"] == 3
    assert asked["size"] == 25
    assert asked["sort"] == ["-price", "title"]


def test_nonsense_paging_falls_back():
    """A hand-edited URL must not 500 a widget."""
    asked = requested(Query(page="banana", size="-5"))
    assert asked["page"] == 1
    assert asked["size"] == 0


def test_column_filters_are_namespaced():
    """`f.` so they cannot collide with page/size/sort, or be mistaken for the
    page's own filter bar. v1 used Tabulator's `filter[0][field]` and had to
    skip keys by prefix for the same reason, named after one vendor."""
    asked = requested(Query(**{"f.title": "dune", "f.region": "3", "page": "2"}))
    assert asked["filters"] == {"title": "dune", "region": "3"}


def test_an_empty_column_filter_is_not_a_filter():
    assert requested(Query(**{"f.title": ""}))["filters"] == {}


def test_nothing_asked_is_the_defaults():
    asked = requested(Query())
    assert (asked["page"], asked["size"], asked["sort"], asked["filters"]) == (
        1, 0, [], {}
    )


# --- what a column tells an adapter ------------------------------------------


def test_a_column_says_what_it_supports():
    """A filter box on a column that cannot be filtered is a control that does
    nothing, and a sorter needs to know what it is comparing."""
    drawn = column(Field("price", sorter="number", filterable=True))
    assert drawn["type"] == "number"
    assert drawn["align"] == "right"
    assert drawn["filterable"] is True


def test_filterable_is_the_columns_own_header():
    """Not the page's filter bar — a PageFilter row is that decision, and it
    may name a path that is not a column at all."""
    assert column(Field("title"))["filterable"] is False
    assert column(Field("title", filterable=True))["filterable"] is True


def test_long_text_says_it_wraps():
    assert column(Field("notes", fmt="textarea"))["wrap"] is True
    assert column(Field("title"))["wrap"] is False


def test_a_width_travels():
    assert column(Field("title", width=120))["width"] == 120
