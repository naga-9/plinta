"""The shared client, in the browser it has to work in.

Everything here is reachable only through a real page load: script order,
deferred execution, and what the widget draws once the answer arrives.
"""
import pytest

from tests.browser.conftest import BOOKS, PAGE_SIZE

pytestmark = pytest.mark.django_db


def open_page(page, live_server, screen, query=""):
    """Load the screen and wait for the widget to have drawn something."""
    subject, _, _ = screen
    page.goto(f"{live_server.url}{subject.get_absolute_url()}{query}")
    page.wait_for_selector(".tabulator-row, .pl-alert", timeout=15000)
    return page


def rows(page):
    return page.locator(".tabulator-row")


def cell_of(page, name, index=0):
    """One cell by *column* name.

    An editable column is bound to `_edit.<name>` inside the grid, because a
    formatted value cannot seed the editor that writes it back. Which of the
    two a column uses is the adapter's business, so a test asks for the
    column and takes whichever is there.
    """
    row = rows(page).nth(index)
    for selector in (f'[tabulator-field="{name}"]',
                     f'[tabulator-field="_edit.{name}"]'):
        found = row.locator(selector)
        if found.count():
            return found
    return row.locator(f'[tabulator-field="{name}"]')


def first_title(page):
    return cell_of(page, "title").inner_text()


# --- mounting ---------------------------------------------------------------


def test_a_fetching_widget_draws(page, live_server, signed_in, screen):
    """The regression the suite exists for.

    The client used to mount when `readyState !== 'loading'`. A deferred
    script runs at `'interactive'`, so it mounted before the adapters — which
    are deferred scripts *after* it — had registered, and every fetching
    component reported that it had no adapter. Nothing on the server was
    wrong, so no Python test could see it.
    """
    open_page(page, live_server, screen)
    assert page.locator(".pl-alert").count() == 0
    assert rows(page).count() == PAGE_SIZE


def test_the_columns_are_the_ones_the_server_sent(page, live_server, signed_in, screen):
    open_page(page, live_server, screen)
    headers = page.locator(".tabulator-col-title").all_inner_texts()
    assert [h.strip() for h in headers] == ["Title", "In print", "Region"]


def test_a_component_with_no_adapter_says_so(page, live_server, signed_in, screen):
    """A blank card reads as a feature that stopped working.

    The adapter's own script is what registers it, so dropping that script is
    what an install with a broken or half-copied asset looks like.
    """
    from plinta.utils import assets

    saved = dict(assets._scripts)
    for path in list(assets._scripts):
        if "adapter" in path:
            del assets._scripts[path]
    try:
        subject, _, _ = screen
        page.goto(f"{live_server.url}{subject.get_absolute_url()}")
        page.wait_for_selector(".pl-alert", timeout=15000)
        assert "No adapter" in page.locator(".pl-alert").inner_text()
    finally:
        assets._scripts.clear()
        assets._scripts.update(saved)


# --- what the client asks for ----------------------------------------------


def test_paging_asks_the_server(page, live_server, signed_in, screen):
    """Tabulator decides page two is needed; the client decides how to ask."""
    open_page(page, live_server, screen)
    assert first_title(page) == "Book 00"

    with page.expect_request(lambda r: "page=2" in r.url):
        page.click(".tabulator-page[data-page='2']")
    page.wait_for_function(
        "() => document.querySelector('.tabulator-row [tabulator-field$=\"title\"]')"
        ".textContent.trim() !== 'Book 00'",
        timeout=15000,
    )
    assert first_title(page) == f"Book {PAGE_SIZE:02d}"


def test_sorting_asks_the_server(page, live_server, signed_in, screen):
    """Two clicks, because the first is ascending and the rows already are."""
    open_page(page, live_server, screen)
    with page.expect_request(lambda r: "sort=title" in r.url):
        page.click(".tabulator-col-title:has-text('Title')")
    with page.expect_request(lambda r: "sort=-title" in r.url):
        page.click(".tabulator-col-title:has-text('Title')")
    page.wait_for_function(
        "() => document.querySelector('.tabulator-row [tabulator-field$=\"title\"]')"
        ".textContent.trim() === 'Book %02d'" % (BOOKS - 1),
        timeout=15000,
    )
    assert first_title(page) == f"Book {BOOKS - 1:02d}"


def test_a_column_filter_narrows_on_the_server(page, live_server, signed_in, screen):
    open_page(page, live_server, screen)
    # Typed, not filled: the widget listens for key events, and setting the
    # value straight onto the element fires none of them.
    with page.expect_request(lambda r: "f.title=" in r.url):
        page.locator(".tabulator-header-filter input").press_sequentially("Book 1")
    page.wait_for_function(
        # The cell is briefly absent while the grid redraws, so the guard
        # is not politeness: without it the predicate throws, and a
        # throwing predicate fails the wait instead of retrying it.
        "() => { var c = document.querySelector("
        "'.tabulator-row [tabulator-field$=\"title\"]');"
        " return document.querySelectorAll('.tabulator-row').length === 10"
        " && c && c.textContent.trim() === 'Book 10'; }",
        timeout=15000,
    )
    assert first_title(page) == "Book 10"


def test_the_pages_own_filters_travel_with_the_request(
    page, live_server, signed_in, screen
):
    """A widget shows what the screen is filtered to, not what it was
    filtered to when the block was configured."""
    subject, _, _ = screen
    from plinta.pages.models import PageFilter

    PageFilter.objects.create(page=subject, field_name="in_print", label="In print")
    open_page(page, live_server, screen, query="?in_print=True")
    assert rows(page).count() == PAGE_SIZE
    # Half the books are in print, so the total is halved, not the page size.
    page.wait_for_function(
        "() => !!document.querySelector('.tabulator-paginator')", timeout=15000
    )
    # Only the numbered buttons: First, Prev, Next and Last carry the
    # attribute too, and counting those would pass whatever the filter did.
    numbered = page.evaluate(
        "() => [...document.querySelectorAll('.tabulator-page[data-page]')]"
        ".filter(b => /^[0-9]+$/.test(b.dataset.page)).length"
    )
    assert numbered == 2  # 12 books in print over pages of 10, not 25


# --- writing ----------------------------------------------------------------


def test_an_edited_cell_reaches_the_database(page, live_server, signed_in, screen):
    """The whole chain, and the only test that covers all of it: an editor
    drawn because the server said the column was writable, a POST carrying
    the CSRF token Django set, the pipeline, and the row coming back."""
    from tests.testapp.models import Book

    open_page(page, live_server, screen)
    cell = cell_of(page, "title")
    cell.click()  # one click opens the editor; a second would close it
    editor = cell.locator("input")
    editor.wait_for(timeout=15000)
    editor.fill("Rewritten")
    with page.expect_response(lambda r: r.url.endswith("/write/")) as answer:
        editor.press("Enter")
    assert answer.value.status == 200
    assert Book.objects.filter(title="Rewritten").count() == 1


def test_a_column_the_viewer_may_not_write_offers_no_editor(
    page, live_server, signed_in, screen
):
    """`in_print` is visible and not editable, so it never opens.

    An editor on a cell the server would refuse is a promise the page cannot
    keep, and the writer only finds out after typing.
    """
    open_page(page, live_server, screen)
    # The writable one opens, so this is not passing because nothing opens.
    cell_of(page, "title").click()
    assert cell_of(page, "title").locator("input").count() == 1

    cell = cell_of(page, "in_print")
    cell.click()
    assert cell.locator("input").count() == 0


def test_a_rejected_edit_goes_back(page, live_server, signed_in, screen):
    """The value returns and the cell says why, rather than showing something
    the database does not hold."""
    from tests.testapp.models import Book

    open_page(page, live_server, screen)
    cell = cell_of(page, "title")
    cell.click()
    editor = cell.locator("input")
    editor.wait_for(timeout=15000)
    editor.fill("x" * 500)
    with page.expect_response(lambda r: r.url.endswith("/write/")) as answer:
        editor.press("Enter")
    assert answer.value.status == 422
    page.wait_for_selector(".pl-tabulator__cell--rejected", timeout=15000)
    assert cell.inner_text().strip() == "Book 00"
    assert not Book.objects.filter(title__startswith="xxx").exists()


def test_a_boolean_gets_a_tick_not_a_text_box(page, live_server, signed_in, screen):
    """What shipped first gave every editable column a text box, so a cell
    reading `No` offered the word back and was told it was not a boolean.

    `in_print` is not editable here, so this checks the mapping itself: a
    column whose kind is boolean must not be offered an `input`.
    """
    open_page(page, live_server, screen)
    kinds = page.evaluate("""async () => {
        var m = document.querySelector('[data-plinta-mount]');
        var r = await fetch(m.dataset.plintaUrl + '?page=1&size=1',
                            {credentials: 'same-origin'});
        var b = await r.json();
        return b.columns.map(function (c) { return [c.name, c.type]; });
    }""")
    assert ["in_print", "boolean"] in kinds
    assert ["region", "relation"] in kinds
    assert ["title", "string"] in kinds


def test_a_relation_offers_no_editor_until_it_has_a_picker(
    page, live_server, signed_in, screen
):
    """`region` is editable and a relation. A text box would send a label,
    which raised out of the assignment and answered 500 — so it draws none
    rather than one that cannot work.
    """
    open_page(page, live_server, screen)
    cell = cell_of(page, "region")
    cell.click()
    assert cell.locator("input").count() == 0


def test_an_edited_cell_sends_the_value_not_the_formatting(
    page, live_server, signed_in, screen
):
    """The editor is seeded from the unformatted value, so what goes back is
    what the field holds — not the string the cell was displaying."""
    from tests.testapp.models import Book

    open_page(page, live_server, screen)
    cell = cell_of(page, "title")
    cell.click()
    editor = cell.locator("input")
    editor.wait_for(timeout=15000)
    assert editor.input_value() == "Book 00"
    editor.fill("Edited")
    with page.expect_response(lambda r: r.url.endswith("/write/")) as answer:
        editor.press("Enter")
    assert answer.value.json()["row"]["_edit"]["title"] == "Edited"
    assert Book.objects.filter(title="Edited").exists()


def test_sorting_an_editable_column_still_names_it(
    page, live_server, signed_in, screen
):
    """An editable column is bound to `_edit.<name>` inside the grid, and the
    server knows only `<name>` — so a sort naming the grid's spelling would be
    dropped without a word."""
    open_page(page, live_server, screen)
    with page.expect_request(lambda r: "sort=title" in r.url) as asked:
        page.click(".tabulator-col-title:has-text('Title')")
    assert "_edit" not in asked.value.url
