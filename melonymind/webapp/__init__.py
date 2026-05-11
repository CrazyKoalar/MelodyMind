"""Local web annotation tool for melody-ranker training data."""

from .config import AppConfig
from .server import create_app

__all__ = ["AppConfig", "create_app"]
