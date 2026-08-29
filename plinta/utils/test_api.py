"""The envelope shape, and what parse_request does with bad input."""
import json

import pytest
from pydantic import BaseModel

from plinta.utils.api import EnvelopeError, EnvelopeOK, json_response, parse_request


class Payload(BaseModel):
    name: str
    count: int = 1


def body(response):
    return json.loads(response.content)


def test_success_carries_no_data_key_when_there_is_none():
    assert body(json_response()) == {"success": True}


def test_success_with_data():
    assert body(json_response(data={"pk": 7})) == {"success": True, "data": {"pk": 7}}


def test_errors_flip_success_and_default_to_400():
    response = json_response(errors={"name": ["required"]})
    assert response.status_code == 400
    assert body(response) == {"success": False, "errors": {"name": ["required"]}}


def test_a_string_error_is_keyed_general():
    assert body(json_response(errors="nope"))["errors"] == {"_general": ["nope"]}


def test_explicit_status_wins():
    assert json_response(errors="gone", status=404).status_code == 404
    assert json_response(data={}, status=201).status_code == 201


def test_data_is_omitted_not_nulled():
    """A client checking `"data" in r` must not see a null."""
    assert "data" not in body(json_response())


class FakeRequest:
    def __init__(self, raw: bytes, content_type: str = "application/json"):
        self.body = raw
        self.content_type = content_type


def test_parse_request_returns_the_validated_schema():
    payload, err = parse_request(FakeRequest(b'{"name": "x", "count": 3}'), Payload)
    assert err is None
    assert (payload.name, payload.count) == ("x", 3)


def test_parse_request_applies_schema_defaults():
    payload, _ = parse_request(FakeRequest(b'{"name": "x"}'), Payload)
    assert payload.count == 1


def test_parse_request_keys_errors_by_field():
    payload, err = parse_request(FakeRequest(b'{"count": 3}'), Payload)
    assert payload is None
    assert "name" in body(err)["errors"]
    assert err.status_code == 400


def test_malformed_json_is_a_general_error():
    _, err = parse_request(FakeRequest(b"{not json"), Payload)
    assert "_general" in body(err)["errors"]


def test_an_empty_body_is_parsed_as_an_empty_object():
    """So a schema whose fields all have defaults accepts an empty POST."""

    class AllDefaults(BaseModel):
        count: int = 0

    payload, err = parse_request(FakeRequest(b""), AllDefaults)
    assert err is None and payload.count == 0


@pytest.mark.parametrize(
    "content_type",
    ["application/x-www-form-urlencoded", "multipart/form-data", "text/plain"],
)
def test_a_body_that_is_not_json_is_415(content_type):
    """One content type, so there is never a second contract for one endpoint."""
    payload, err = parse_request(FakeRequest(b'{"name": "x"}', content_type), Payload)
    assert payload is None
    assert err.status_code == 415
    assert content_type in body(err)["errors"]["_general"][0]


def test_a_charset_parameter_is_ignored():
    _, err = parse_request(
        FakeRequest(b'{"name": "x"}', "application/json; charset=utf-8"), Payload
    )
    assert err is None


def test_a_request_with_no_content_type_is_parsed():
    """Django reports "" for a GET-shaped request; the body still decides."""
    payload, err = parse_request(FakeRequest(b'{"name": "x"}', ""), Payload)
    assert err is None and payload.name == "x"


@pytest.mark.parametrize(
    ("envelope", "expected"),
    [
        (EnvelopeOK(), {"success": True, "data": None}),
        (EnvelopeError(errors="x"), {"success": False, "errors": "x"}),
    ],
)
def test_envelope_schemas_match_the_wire_shape(envelope, expected):
    assert envelope.model_dump() == expected
