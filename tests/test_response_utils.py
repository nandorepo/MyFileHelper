from __future__ import annotations
from datetime import timezone
from flask import Flask
from modules.response_utils import error_response, normalize_bool, ok_response, parse_utc
def test_normalize_bool_supports_common_truthy_values() -> None:
    assert normalize_bool("true")
    assert normalize_bool("YES")
    assert normalize_bool("1")
    assert normalize_bool(None, default=True)
def test_normalize_bool_defaults_to_false_for_other_values() -> None:
    assert not normalize_bool("false")
    assert not normalize_bool("0")
    assert not normalize_bool("off")
def test_parse_utc_handles_isoz_and_invalid() -> None:
    dt = parse_utc("2026-03-27T10:20:30Z")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert parse_utc("invalid-datetime") is None
def test_ok_response_uses_canonical_success_envelope() -> None:
    app = Flask(__name__)
    with app.app_context():
        response, status = ok_response({"value": 1}, status=201)
    assert status == 201
    assert response.get_json() == {"code": 0, "message": "ok", "data": {"value": 1}}
def test_error_response_uses_canonical_error_envelope() -> None:
    app = Flask(__name__)
    with app.app_context():
        response, status = error_response("boom", 400, 12345)
    assert status == 400
    assert response.get_json() == {"code": 12345, "message": "boom", "data": None}
