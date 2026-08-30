"""The output contract: rows and fields in, output out.

A renderer never queries. Rows arrive already filtered by row policy, fields
already filtered by field permission, which is what makes this layer
structurally incapable of widening access.
"""
