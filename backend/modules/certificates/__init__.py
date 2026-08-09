"""Public certificate verification. Issuing lives in core/certificates."""

from backend.modules.certificates.router import router

__all__ = ["router"]
