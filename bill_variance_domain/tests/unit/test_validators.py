"""Unit tests for shared validation utilities."""
from shared_packages.validation import validate_email, validate_required_fields


def test_validate_email():
    assert validate_email("user@example.com") is True
    assert validate_email("bad-email") is False
    assert validate_email("") is False
    assert validate_email(None) is False


def test_validate_required_fields_all_present():
    result = validate_required_fields({"ban": "1", "email": "a@b.com"}, ["ban", "email"])
    assert result.is_valid is True
    assert result.errors == []


def test_validate_required_fields_missing():
    result = validate_required_fields({"ban": "", "email": None}, ["ban", "email"])
    assert result.is_valid is False
    assert len(result.errors) == 2
