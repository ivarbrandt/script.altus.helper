# -*- coding: utf-8 -*-
"""
First-run default population for the search-widget DB.

Seeds ``search_config.db`` with the eight library catalog entries (no plugin
providers — those are opt-in via Preset paths in the Add dialog). Mirrors
``widget_manager.default_config`` in shape: an empty DB always gets seeded.
P10 profiles will be the way users preserve a deliberately-empty config.
"""

from modules.search_manager.catalog import CATALOG
from modules.search_manager.config_manager import ConfigManager


_LIBRARY_LABEL = "LIBRARY"


def create_default_widgets():
    """Insert all library-source catalog entries."""
    cm = ConfigManager()
    try:
        for entry in CATALOG:
            if entry.get("source_label") != _LIBRARY_LABEL:
                continue
            cm.add_widget_from_catalog(entry)
    finally:
        cm.close()


def ensure_search_config():
    """If the DB is empty, seed it with library defaults.

    Returns True if defaults were just created.
    """
    cm = ConfigManager()
    empty = cm.is_empty()
    cm.close()
    if not empty:
        return False
    create_default_widgets()
    return True
