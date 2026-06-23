"""Search DSL exceptions."""
from __future__ import annotations


class SearchError(Exception):
    """Base class for search DSL errors."""


class SearchSyntaxError(SearchError):
    """Malformed query, unknown field, or invalid value."""
