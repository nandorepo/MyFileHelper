from __future__ import annotations
from modules import error_codes
def test_error_code_catalog_contains_unique_codes() -> None:
    codes = list(error_codes.ERROR_CODE_CATALOG.keys())
    assert len(codes) == len(set(codes))
def test_error_code_catalog_matches_exported_constants() -> None:
    exported_codes = {
        value
        for name, value in vars(error_codes).items()
        if name.isupper() and name not in {"ERROR_CODE_CATALOG"} and isinstance(value, int)
    }
    assert exported_codes == set(error_codes.ERROR_CODE_CATALOG.keys())
def test_error_code_catalog_entries_have_required_fields() -> None:
    required = {"name", "http_status", "scope", "description"}
    for meta in error_codes.ERROR_CODE_CATALOG.values():
        assert required.issubset(meta.keys())
