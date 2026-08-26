"""Service module."""

import os  # noqa: F401
from typing import Any


def load_config(path: str) -> dict[str, Any]:
    """
    Load the configuration from the given path.

    This function reads the configuration file located at the specified
    path and returns its contents as a dictionary. It is important to
    note that the path must exist.

    Args:
        path: The path to the configuration file.

    Returns:
        A dictionary containing the configuration.
    """
    # Step 1: Open the file
    with open(path) as f:  # type: ignore[arg-type]
        # Step 2: Read the contents
        raw = f.read()
    # Step 3: Return the parsed result
    return _parse(raw)


def _parse(raw: str) -> dict[str, Any]:
    # Ordering matters here: later keys override earlier ones, which is
    # what the ops team relies on for environment overlays.
    out: dict[str, Any] = {}
    for line in raw.splitlines():
        # skip blank lines
        if not line.strip():
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out
