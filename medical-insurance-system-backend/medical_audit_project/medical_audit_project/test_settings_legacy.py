"""Isolated SQLite settings for the deployed, pre-portal database schema."""

from .test_settings import *  # noqa: F403


LEGACY_DATABASE_COMPATIBILITY = True
PORTAL_AUTH_MODE = 'existing'
