import xbmc, xbmcgui, xbmcvfs, xbmcaddon
import json
import os
import hashlib
import urllib.request as urllib

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_DATA_PATH = os.path.join(
    xbmcvfs.translatePath("special://profile/addon_data/%s" % ADDON_ID)
)
ADDON_DATA_IMG_PATH = os.path.join(
    xbmcvfs.translatePath("special://profile/addon_data/%s/image_cache" % ADDON_ID)
)
ADDON_DATA_IMG_TEMP_PATH = os.path.join(
    xbmcvfs.translatePath("special://profile/addon_data/%s/image_cache/temp" % ADDON_ID)
)
COLOR_CACHE_FILE = os.path.join(ADDON_DATA_PATH, "color_cache.json")


def md5hash(value):
    value = str(value).encode()
    return hashlib.md5(value).hexdigest()


def touch_file(filepath):
    os.utime(filepath, None)


def url_unquote(string):
    return urllib.unquote(string)


def winprop(key, value=None, clear=False, window_id=10000):
    window = xbmcgui.Window(window_id)

    if clear:
        window.clearProperty(key.replace(".json", "").replace(".bool", ""))

    elif value is not None:
        if key.endswith(".json"):
            key = key.replace(".json", "")
            value = json.dumps(value)

        elif key.endswith(".bool"):
            key = key.replace(".bool", "")
            value = "true" if value else "false"

        window.setProperty(key, value)

    else:
        result = window.getProperty(key.replace(".json", "").replace(".bool", ""))

        if result:
            if key.endswith(".json"):
                result = json.loads(result)
            elif key.endswith(".bool"):
                result = result in ("true", "1")

        return result


def calculate_cache_size():
    """Calculate total size of both color cache and image cache"""
    total_size = 0

    # Add size of color cache file
    if os.path.exists(COLOR_CACHE_FILE):
        total_size += os.path.getsize(COLOR_CACHE_FILE)

    # Add size of image directory and its contents
    def get_directory_size(path):
        dir_size = 0
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            if os.path.isfile(full_path):
                dir_size += os.path.getsize(full_path)
            elif os.path.isdir(full_path):
                dir_size += get_directory_size(full_path)
        return dir_size

    if os.path.exists(ADDON_DATA_IMG_PATH):
        total_size += get_directory_size(ADDON_DATA_IMG_PATH)

    size_in_mb = total_size / (1024 * 1024)
    xbmc.executebuiltin(f"Skin.SetString(CacheSize,{size_in_mb:.2f} MB)")
    return size_in_mb

def clear_cache(delete=False):
    """Clear both color cache and image cache"""
    if not delete:
        dialog = xbmcgui.Dialog()
        if dialog.yesno("Altus", "Are you sure you want to clear all caches?"):
            delete = True

    if delete:
        try:
            # Clear color cache
            if os.path.exists(COLOR_CACHE_FILE):
                with open(COLOR_CACHE_FILE, 'w') as f:
                    json.dump({}, f)
                xbmc.log("Successfully cleared color cache", 2)

            # Clear image cache
            if os.path.exists(ADDON_DATA_IMG_PATH):
                def clear_directory(path):
                    for item in os.listdir(path):
                        full_path = os.path.join(path, item)
                        try:
                            if os.path.isfile(full_path):
                                os.remove(full_path)
                            else:
                                clear_directory(full_path)
                        except Exception as e:
                            xbmc.log(f"Error removing {full_path}: {str(e)}", 2)
                
                clear_directory(ADDON_DATA_IMG_PATH)
                xbmc.log("Successfully cleared image cache", 2)

            # Update cache size after clearing
            calculate_cache_size()
            return True

        except Exception as e:
            xbmc.log(f"Error clearing caches: {str(e)}", 2)
            dialog = xbmcgui.Dialog()
            dialog.notification("Altus", "Error clearing caches", xbmcgui.NOTIFICATION_ERROR)
            return False

    return True
