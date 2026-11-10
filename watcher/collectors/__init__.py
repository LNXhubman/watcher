"""Collectors: one module per source, each exposing NAME, register(conn) and collect(conn, since, fetch=None)."""


class Skipped(Exception):
    """Raised by a collector that cannot run yet (for example a missing API key); not counted as a failure."""
