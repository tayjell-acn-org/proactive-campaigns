"""Baseline validation utilities shared across campaigns."""
from .validators import (
    ValidationResult,
    validate_required_fields,
    validate_email,
)

__all__ = [
    "ValidationResult",
    "validate_required_fields",
    "validate_email",
]
