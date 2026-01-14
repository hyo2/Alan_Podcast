"""
Middleware modules for the application.
"""

from .internal_auth import InternalAuthMiddleware

__all__ = ["InternalAuthMiddleware"]