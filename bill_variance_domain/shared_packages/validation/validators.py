"""
Baseline validation utilities (TDD Sections 8.1 step 3, 9, 13 schema tests).

Enforces mandatory fields and basic data-quality rules. Campaign-specific
business rules live in each campaign's rules module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.is_valid = False
        self.errors.append(message)


def validate_required_fields(record: dict[str, Any], required: Iterable[str]) -> ValidationResult:
    result = ValidationResult()
    for field_name in required:
        value = record.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(f"Missing required field: {field_name}")
    return result


def validate_email(email: str | None) -> bool:
    return bool(email and _EMAIL_RE.match(email))
