# -*- coding: utf-8 -*-
import xbmc
from xbmcgui import Window
from xbmc import sleep, getInfoLabel
from xbmcvfs import translatePath
from xbmcaddon import Addon
import json
import os

# from modules.logger import logger

window = Window(10000)

ADDON_DATA_PATH = translatePath("special://userdata/addon_data/script.altus.helper")
PROFILE_PATH = os.path.join(ADDON_DATA_PATH, "current_profile.json")
VERSION_PATH = os.path.join(ADDON_DATA_PATH, "installed_version.json")
WIDGET_CONFIG_PATH = os.path.join(ADDON_DATA_PATH, "widget_config.db")


def check_for_update(skin_id):
    """Migrate and rebuild once when the skin version changes.

    The window property is only a cache for the service's 10 second checks.
    It is empty after every Kodi start, so the last seen version is also kept
    in a file; otherwise an update that landed while Kodi was closed would be
    recorded as current on the first check and never migrated.
    """
    installed_version = Addon(id=skin_id).getAddonInfo("version")
    property_version = window.getProperty("%s.installed_version" % skin_id)
    if property_version == installed_version:
        return
    recorded_version = property_version or _read_recorded_version(skin_id)
    if recorded_version == installed_version:
        window.setProperty("%s.installed_version" % skin_id, installed_version)
        return
    if not recorded_version and not os.path.exists(WIDGET_CONFIG_PATH):
        # Fresh install: first-run setup builds the config, nothing to migrate.
        return set_installed_version(skin_id, installed_version)
    # A version change, or an existing config with no recorded version yet
    # (installs from before the file existed). Both steps of migrate() are
    # safe to repeat, so treating the second case as an update costs nothing.
    from modules.widget_manager.migration import migrate
    from modules.widget_manager.xml_generator import generate_and_reload
    from modules.search_manager.xml_generator import (
        generate_and_reload as generate_search_xml,
    )

    migrate()
    set_installed_version(skin_id, installed_version)
    sleep(1000)
    # Search widgets are rendered from the search config too; opening it
    # converts any row types the update retired, and the rewrite keeps the
    # generated file from naming includes the new skin no longer has.
    generate_search_xml(reload_skin=False)
    generate_and_reload()


def _read_recorded_version(skin_id):
    try:
        with open(VERSION_PATH, "r") as f:
            return json.load(f).get(skin_id)
    except (OSError, ValueError, AttributeError):
        return None


def set_installed_version(skin_id, installed_version):
    window.setProperty("%s.installed_version" % skin_id, installed_version)
    try:
        with open(VERSION_PATH, "r") as f:
            versions = json.load(f)
        if not isinstance(versions, dict):
            versions = {}
    except (OSError, ValueError):
        versions = {}
    versions[skin_id] = installed_version
    if not os.path.exists(ADDON_DATA_PATH):
        os.makedirs(ADDON_DATA_PATH)
    with open(VERSION_PATH, "w") as f:
        json.dump(versions, f)


def set_current_profile(skin_id, current_profile):
    if not os.path.exists(ADDON_DATA_PATH):
        os.makedirs(ADDON_DATA_PATH)
    with open(PROFILE_PATH, "w") as f:
        json.dump(current_profile, f)
    window.setProperty("%s.current_profile" % skin_id, current_profile)


def get_profile_count():
    json_query = xbmc.executeJSONRPC(
        '{"jsonrpc": "2.0", "method": "Profiles.GetProfiles", "id": 1}'
    )
    json_response = json.loads(json_query)
    if "result" in json_response and "profiles" in json_response["result"]:
        return len(json_response["result"]["profiles"])
    return 0


def check_for_profile_change(skin_id):
    current_profile = getInfoLabel("System.ProfileName")
    if get_profile_count() <= 1:
        set_current_profile(skin_id, current_profile)
        return
    try:
        with open(PROFILE_PATH, "r") as f:
            saved_profile = json.load(f)
    except FileNotFoundError:
        saved_profile = None
    if not saved_profile:
        set_current_profile(skin_id, current_profile)
        return
    if saved_profile == current_profile:
        return
    from modules.widget_manager.xml_generator import generate_and_reload

    set_current_profile(skin_id, current_profile)
    xbmc.sleep(200)
    generate_and_reload()
