"""An audit trail, built entirely by listening.

In v1 this was stages 12 to 14 of the write pipeline, which is why `blocks`
imported it. Here it subscribes, and nothing in core mentions it: uninstall the
app and the writes carry on unaudited, with no guard anywhere to remove.
"""
