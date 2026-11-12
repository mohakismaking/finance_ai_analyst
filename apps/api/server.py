"""ASGI server entry point for local and deployed environments."""

from .main import create_app_from_environment

app = create_app_from_environment()
