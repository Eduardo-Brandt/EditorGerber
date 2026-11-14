"""Errors that must be shown instead of silently changing fabrication data."""


class GerberError(ValueError):
    """Invalid or unsupported Gerber input."""


class UnsupportedGerberError(GerberError):
    """A construct needs a backend not implemented in this release."""


class SaveError(GerberError):
    """Export failed validation or would lose information."""
