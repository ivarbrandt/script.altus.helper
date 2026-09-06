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


def create_default_widgets(profile=None):
    """Insert all library-source catalog entries."""
    cm = ConfigManager(profile)
    try:
        for entry in CATALOG:
            if entry.get("source_label") != _LIBRARY_LABEL:
                continue
            cm.add_widget_from_catalog(entry)
    finally:
        cm.close()


def seed_profile_config(profile, from_profile=None):
    """Give a profile a search config by copying an existing one.

    The widget profiles that predate search have no search config, so landing
    on one would otherwise mean an empty config with no search widgets. Config
    seeds; history deliberately does NOT — carrying search terms across
    profiles is the leak that forking history exists to prevent, so a profile
    with no history file simply starts empty.

    from_profile picks the source:
      None  copy from whatever is active right now. The switch route uses this,
            called BEFORE Skin.SetString so it still resolves to the outgoing
            profile.
      ""    copy from the unnamed default. The startup path needs this: there
            the skin string already names the TARGET, so resolving the source
            dynamically would point at the very file being created and the copy
            would silently no-op.

    Returns True if a file was created.
    """
    import xbmcvfs
    from modules.search_manager.config_manager import _get_db_path, profile_db_path

    if not profile:
        return False
    dest = profile_db_path(profile)
    if xbmcvfs.exists(dest):
        return False
    src = _get_db_path() if from_profile is None else profile_db_path(from_profile)
    if not xbmcvfs.exists(src) or src == dest:
        return False
    return bool(xbmcvfs.copy(src, dest))


def save_unnamed_as(profile):
    """Give ``profile`` a copy of the unnamed config AND history.

    Backs the "your current config is unsaved — save it first?" prompt, which
    otherwise only copies widget_config and would preserve half a profile.

    Unlike seed_profile_config this DOES copy history: seeding never carries
    terms across because it bridges two different contexts, but this is the
    same context being given a name. Dropping the history while telling the
    user their config was saved would be the surprising behaviour.
    """
    import xbmcvfs
    from modules.search_utils import profile_history_path

    if not profile:
        return
    seed_profile_config(profile, from_profile="")
    dest = profile_history_path(profile)
    src = profile_history_path("")
    if src != dest and xbmcvfs.exists(src) and not xbmcvfs.exists(dest):
        xbmcvfs.copy(src, dest)


def apply_profile(profile):
    """Point search at ``profile``: seed defaults if empty, rebuild the widget
    XML, and republish the history properties.

    Call AFTER Skin.SetString with the name passed explicitly — the builtin is
    async, so anything resolving the profile from the skin string here would
    still act on the previous one. Pass "" for the unnamed default.
    """
    from modules.search_manager.xml_generator import generate_and_reload
    from modules.search_utils import SPaths

    ensure_search_config(profile)
    # reload_skin=False: the widget-side generate_and_reload already schedules
    # the single ReloadSkin for this switch, and two would race each other.
    generate_and_reload(active_config=profile, reload_skin=False)
    SPaths(profile=profile).refresh_search_history()


def ensure_search_config(profile=None):
    """If the DB is empty, seed it with library defaults.

    ``profile`` targets a specific profile's config; pass it from routes that
    just called Skin.SetString, which is async (see config_manager._get_db_path).

    Returns True if defaults were just created.
    """
    cm = ConfigManager(profile)
    empty = cm.is_empty()
    cm.close()
    if not empty:
        return False
    create_default_widgets(profile)
    return True
