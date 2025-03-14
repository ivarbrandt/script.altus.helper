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

PROFILE_PATH = os.path.join(
    translatePath("special://userdata/addon_data/script.altus.helper"),
    "current_profile.json",
)


def log_error(function_name, error):
    """Enhanced error logging function"""
    import traceback

    error_details = traceback.format_exc()
    xbmc.log(f"Error in {function_name}: {str(error)}", level=xbmc.LOGERROR)
    xbmc.log(f"Error details: {error_details}", level=xbmc.LOGERROR)


def check_for_update(skin_id):
    property_version = window.getProperty("%s.installed_version" % skin_id)
    installed_version = Addon(id=skin_id).getAddonInfo("version")

    xbmc.log(
        f"Checking for update: Property version: {property_version}, Installed version: {installed_version}",
        level=xbmc.LOGINFO,
    )

    # If property version not set or matches current, just return
    if not property_version:
        return set_installed_version(skin_id, installed_version)
    if property_version == installed_version:
        return

    # Update the version property first
    set_installed_version(skin_id, installed_version)
    xbmc.log("Version property updated, sleeping...", level=xbmc.LOGINFO)

    # Delay to ensure property is set
    sleep(1000)

    # Import and run remake_all_cpaths
    try:
        xbmc.log("Importing cpath_maker...", level=xbmc.LOGINFO)
        from modules.cpath_maker import remake_all_cpaths, starting_widgets

        xbmc.log("Running remake_all_cpaths...", level=xbmc.LOGINFO)
        remake_all_cpaths(silent=True)
        xbmc.log("remake_all_cpaths completed successfully", level=xbmc.LOGINFO)
    except Exception as e:
        log_error("remake_all_cpaths", e)

    # Refresh search history separately with error handling
    try:
        xbmc.log("Importing search_utils...", level=xbmc.LOGINFO)
        from modules.search_utils import SPaths

        xbmc.log("Creating SPaths instance...", level=xbmc.LOGINFO)
        spaths = SPaths()
        # Call refresh_search_history only if it exists
        if hasattr(spaths, "refresh_search_history"):
            xbmc.log("Running refresh_search_history...", level=xbmc.LOGINFO)
            spaths.refresh_search_history()
            xbmc.log(
                "refresh_search_history completed successfully", level=xbmc.LOGINFO
            )
        else:
            xbmc.log(
                "refresh_search_history method not found on SPaths instance!",
                level=xbmc.LOGWARNING,
            )
    except Exception as e:
        log_error("refresh_search_history", e)

    # Start widgets separately with error handling
    try:
        if "starting_widgets" in locals():
            xbmc.log("Running starting_widgets...", level=xbmc.LOGINFO)
            starting_widgets()
            xbmc.log("starting_widgets completed successfully", level=xbmc.LOGINFO)
        else:
            xbmc.log("starting_widgets function not available!", level=xbmc.LOGWARNING)
    except Exception as e:
        log_error("starting_widgets", e)

    xbmc.log("check_for_update completed", level=xbmc.LOGINFO)


# def check_for_update(skin_id):
#     property_version = window.getProperty("%s.installed_version" % skin_id)
#     installed_version = Addon(id=skin_id).getAddonInfo("version")
#     if not property_version:
#         return set_installed_version(skin_id, installed_version)
#     if property_version == installed_version:
#         return
#     from modules.cpath_maker import remake_all_cpaths, starting_widgets
#     from modules.search_utils import SPaths

#     set_installed_version(skin_id, installed_version)
#     sleep(1000)
#     remake_all_cpaths(silent=True)
#     spaths = SPaths()
#     spaths.refresh_search_history()
#     starting_widgets()


def set_installed_version(skin_id, installed_version):
    window.setProperty("%s.installed_version" % skin_id, installed_version)


def set_current_profile(skin_id, current_profile):
    dir_path = os.path.dirname(PROFILE_PATH)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
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
    if get_profile_count() <= 1:
        return
    current_profile = getInfoLabel("System.ProfileName")
    saved_profile = window.getProperty("%s.current_profile" % skin_id)
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
    from modules.cpath_maker import remake_all_cpaths

    set_current_profile(skin_id, current_profile)
    xbmc.sleep(200)
    remake_all_cpaths(silent=True)


# def check_for_profile_change(skin_id):
#     current_profile = getInfoLabel("System.ProfileName")
#     saved_profile = window.getProperty("%s.current_profile" % skin_id)
#     try:
#         with open(PROFILE_PATH, "r") as f:
#             saved_profile = json.load(f)
#     except FileNotFoundError:
#         saved_profile = None
#     if not saved_profile:
#         set_current_profile(skin_id, current_profile)
#         return
#     if saved_profile == current_profile:
#         return
#     from modules.cpath_maker import remake_all_cpaths

#     set_current_profile(skin_id, current_profile)
#     sleep(200)
#     remake_all_cpaths(silent=True)
