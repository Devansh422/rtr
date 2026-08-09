"""Site-wide search over the shared index. Reads one table, imports no module."""

from backend.modules.search.router import router

__all__ = ["router"]
