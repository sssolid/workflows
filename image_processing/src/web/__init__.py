# ===== src/web/__init__.py =====
"""Web interface for the Crown Automotive Image Processing System."""

from .app import create_app, main

__all__ = ['create_app', 'main']