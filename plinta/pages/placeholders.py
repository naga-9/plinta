"""The tokens a page contributes.

One: the row a detail page is about. It is registered here rather than in
`utils` because a record is a page's idea — `utils` holds the registry and
knows nothing that has one.
"""
from plinta.utils.placeholders import register_placeholder

#: What a placement writes to filter on the page's record.
#:
#:     PageBlock(context_filter={"book_id": "__RECORD__"})
#:
#: Resolved per request, so one placement serves every record the page shows.
TOKEN = "record"


def register() -> None:
    """Register the token. Called from `AppConfig.ready()`."""

    def record(context):
        """The primary key of the row this page is about, or None.

        None rather than a blank: a filter on None matches rows whose field
        is null, which is at least a defensible answer, where a blank string
        would match nothing and look like a broken page.
        """
        return getattr(context.record, "pk", None)

    register_placeholder(TOKEN, record)
