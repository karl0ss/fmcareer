"""Type aliases shared across fmcareer.

The collected career is JSON-ready data: dicts of strings, numbers, lists and dicts. Its
shape is documented where it is built (collect.py) and checked by the tests; here it is
named, not spelt out field by field.
"""

from collections.abc import Callable
from typing import Any

type Record = dict[str, Any]
"""One JSON-ready record: a season, a transfer, a player's line, the whole career."""

type Step = Callable[[str], None]
"""Reports progress: called once per step with what is happening."""

type ImageKey = tuple[str, int]
"""An image a report can show: ("club", club uid), ("person", unique id), ("comp", database id)."""
