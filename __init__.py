"""pybinbot package.

This package exposes the internal modules ``shared`` and ``models``.
Third-party libraries are intentionally **not** imported at package import
time to avoid side effects and slow or hanging imports during testing.
"""

from . import shared, models  # type: ignore[import]

__all__ = ["shared", "models"]
