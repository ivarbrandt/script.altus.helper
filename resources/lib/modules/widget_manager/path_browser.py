# -*- coding: utf-8 -*-
"""
Browsable path selector for the widget manager.
Supports video/music/program addons, library nodes, PVR, playlists, sources,
games, pictures, favourites, and more.
"""
import json
import xbmc
import xbmcgui

dialog = xbmcgui.Dialog()
ListItem = xbmcgui.ListItem

# ── Root categories ──

ROOT_CATEGORIES = [
    ("Addons", "__addons__", "videos"),
    ("Library", "__library__", "videos"),
    ("PVR", "__pvr__", "videos"),
    ("Playlists", "__playlists__", "videos"),
    ("Sources", "__sources__", "videos"),
    ("Favourites", "favourites://", "videos"),
    ("Games", "__games__", "games"),
    ("Weather", "__weather__", "videos"),
]

# ── Addon sub-menus ──

ADDON_NODES = [
    ("Categories", "addons://", "addonbrowser"),
    ("Video Addons", "addons://sources/video", "videos"),
    ("Music Addons", "addons://sources/music", "music"),
    ("Program Addons", "addons://sources/executable", "programs"),
    ("Picture Addons", "addons://sources/image", "pictures"),
    ("Game Addons", "addons://sources/game", "games"),
    ("Installed Addons", "__installed_addons__", "addons"),
]

# ── Library sub-menus ──

LIBRARY_NODES = [
    ("Video Library", "__video_library__", "videos"),
    ("Music Library", "__music_library__", "music"),
    ("Pictures", "__pictures__", "pictures"),
]

VIDEO_LIBRARY_NODES = [
    ("Movies", "__video_movies__", "videos"),
    ("TV Shows", "__video_tvshows__", "videos"),
    ("Music Videos", "__video_musicvideos__", "videos"),
    ("Categories", "library://video/"),
]

VIDEO_MOVIES_NODES = [
    ("Categories", "library://video/movies/"),
    ("Titles", "videodb://movies/titles/"),
    ("Genres", "videodb://movies/genres/"),
    ("Years", "videodb://movies/years/"),
    ("Actors", "videodb://movies/actors/"),
    ("Directors", "videodb://movies/directors/"),
    ("Studios", "videodb://movies/studios/"),
    ("Countries", "videodb://movies/countries/"),
    ("Sets", "videodb://movies/sets/"),
    ("Tags", "videodb://movies/tags/"),
    ("Recently Added", "videodb://recentlyaddedmovies/"),
    ("In Progress", "videodb://inprogressmovies/"),
]

VIDEO_TVSHOWS_NODES = [
    ("Categories", "library://video/tvshows/"),
    ("Titles", "videodb://tvshows/titles/"),
    ("Genres", "videodb://tvshows/genres/"),
    ("Years", "videodb://tvshows/years/"),
    ("Actors", "videodb://tvshows/actors/"),
    ("Studios", "videodb://tvshows/studios/"),
    ("Tags", "videodb://tvshows/tags/"),
    ("Recently Added Episodes", "videodb://recentlyaddedepisodes/"),
    ("In Progress", "videodb://inprogresstvshows/"),
]

VIDEO_MUSICVIDEOS_NODES = [
    ("Categories", "library://video/musicvideos/"),
    ("Titles", "videodb://musicvideos/titles/"),
    ("Genres", "videodb://musicvideos/genres/"),
    ("Years", "videodb://musicvideos/years/"),
    ("Artists", "videodb://musicvideos/artists/"),
    ("Albums", "videodb://musicvideos/albums/"),
    ("Studios", "videodb://musicvideos/studios/"),
    ("Tags", "videodb://musicvideos/tags/"),
    ("Recently Added", "videodb://recentlyaddedmusicvideos/"),
]

MUSIC_LIBRARY_NODES = [
    ("Artists", "musicdb://artists/"),
    ("Albums", "musicdb://albums/"),
    ("Songs", "musicdb://songs/"),
    ("Genres", "musicdb://genres/"),
    ("Years", "musicdb://years/"),
    ("Recently Added", "musicdb://recentlyaddedalbums/"),
    ("Recently Played", "musicdb://recentlyplayedalbums/"),
    ("Recently Played Songs", "musicdb://recentlyplayedsongs/"),
    ("Top 100 Songs", "musicdb://top100/songs/"),
    ("Top 100 Albums", "musicdb://top100/albums/"),
    ("Compilations", "musicdb://compilations/"),
    ("Categories", "library://music/"),
]

# ── PVR sub-menus ──

PVR_NODES = [
    ("Live TV", "__pvr_tv__", "videos"),
    ("Radio", "__pvr_radio__", "music"),
]

PVR_TV_NODES = [
    ("Categories", "pvr://tv/", "videos"),
    ("Recent Channels", "pvr://channels/tv/*?view=lastplayed", "tvchannels"),
    ("TV Channels", "pvr://channels/tv/", "tvchannels"),
    ("Recordings", "pvr://recordings/tv/active?view=flat", "tvrecordings"),
    ("Timers", "pvr://timers/tv/timers/?view=hidedisabled", "tvtimers"),
    ("Channel Groups", "pvr://channels/tv", "tvguide"),
    ("Saved Searches", "pvr://search/tv/savedsearches", "tvsearch"),
    ("New Channels", "pvr://channels/tv/*?view=dateadded", "tvchannels"),
]

PVR_RADIO_NODES = [
    ("Categories", "pvr://radio/", "music"),
    ("Recent Channels", "pvr://channels/radio/*?view=lastplayed", "radiochannels"),
    ("Radio Channels", "pvr://channels/radio/", "radiochannels"),
    ("Recordings", "pvr://recordings/radio/active?view=flat", "radiorecordings"),
    ("Timers", "pvr://timers/radio/timers/?view=hidedisabled", "radiotimers"),
    ("Channel Groups", "pvr://channels/radio", "radioguide"),
    ("Saved Searches", "pvr://search/radio/savedsearches", "radiosearch"),
    ("New Channels", "pvr://channels/radio/*?view=dateadded", "radiochannels"),
]

# ── Pictures sub-menu ──

PICTURES_NODES = [
    ("Sources", "sources://pictures/"),
]

# ── Playlists sub-menu ──

PLAYLIST_NODES = [
    ("Video Playlists", "special://profile/playlists/video/", "videos"),
    ("Music Playlists", "special://profile/playlists/music/", "music"),
    ("Skin Playlists", "__skin_playlists__", "videos"),
]

# ── Sources sub-menu ──

SOURCES_NODES = [
    ("Video Sources", "sources://video/", "videos"),
    ("Music Sources", "sources://music/", "music"),
    ("Picture Sources", "sources://pictures/", "pictures"),
]

# ── Games sub-menu ──

GAMES_NODES = [
    ("Game Addons", "addons://sources/game/"),
]

# ── Skin playlists ──

SKIN_PLAYLIST_NODES = [
    ("Random Albums", "special://skin/playlists/random_albums.xsp"),
    ("Random Artists", "special://skin/playlists/random_artists.xsp"),
    ("Unplayed Albums", "special://skin/playlists/unplayed_albums.xsp"),
    ("Most Played", "special://skin/playlists/mostplayed_albums.xsp"),
    ("Unwatched", "special://skin/playlists/unwatched_musicvideos.xsp"),
    (
        "Random Music Video Artists",
        "special://skin/playlists/random_musicvideo_artists.xsp",
    ),
    ("Random Music Videos", "special://skin/playlists/random_musicvideos.xsp"),
]

# ── Installed addons (direct widget paths from Home.xml group 8001) ──

INSTALLED_ADDONS_NODES = [
    ("All Addons", "addons://", "addons"),
    ("Video Addons", "addons://sources/video/", "videos"),
    ("Music Addons", "addons://sources/audio/", "music"),
    ("Game Addons", "addons://sources/game/", "games"),
    ("Program Addons", "addons://sources/executable/", "programs"),
    ("Android Apps", "androidapp://sources/apps/", "programs"),
    ("Picture Addons", "addons://sources/image/", "pictures"),
    ("Recently Updated", "addons://recently_updated/", "addons"),
    ("Outdated Addons", "addons://outdated/", "addons"),
]

# ── Submenu routing ──

# Submenus whose items are final widget paths (not browsable further)
_DIRECT_SUBMENUS = {"__installed_addons__"}

_SUBMENU_MAP = {
    "__addons__": ADDON_NODES,
    "__library__": LIBRARY_NODES,
    "__pvr__": PVR_NODES,
    "__playlists__": PLAYLIST_NODES,
    "__sources__": SOURCES_NODES,
    "__video_library__": VIDEO_LIBRARY_NODES,
    "__video_movies__": VIDEO_MOVIES_NODES,
    "__video_tvshows__": VIDEO_TVSHOWS_NODES,
    "__video_musicvideos__": VIDEO_MUSICVIDEOS_NODES,
    "__music_library__": MUSIC_LIBRARY_NODES,
    "__pvr_tv__": PVR_TV_NODES,
    "__pvr_radio__": PVR_RADIO_NODES,
    "__pictures__": PICTURES_NODES,
    "__games__": GAMES_NODES,
    "__skin_playlists__": SKIN_PLAYLIST_NODES,
    "__installed_addons__": INSTALLED_ADDONS_NODES,
}

# ── Window map for onclick construction ──

WINDOW_MAP = {
    "videos": "Videos",
    "music": "Music",
    "programs": "Programs",
    "pictures": "Pictures",
    "games": "Games",
    "files": "Files",
    "addons": "AddonBrowser",
    "addonbrowser": "AddonBrowser",
    "tvchannels": "TVChannels",
    "tvguide": "TVGuide",
    "tvrecordings": "TVRecordings",
    "tvtimers": "TVTimers",
    "tvsearch": "TVChannels",
    "radiochannels": "RadioChannels",
    "radioguide": "RadioChannels",
    "radiorecordings": "RadioRecordings",
    "radiotimers": "RadioTimers",
    "radiosearch": "RadioChannels",
}

# Special onclick overrides for paths that need non-standard window targets
_ONCLICK_OVERRIDES = {
    "pvr://channels/tv": "ActivateWindow(TVGuide)",
    "pvr://channels/radio": "ActivateWindow(RadioChannels)",
    "pvr://channels/tv/": "ActivateWindow(TVChannels)",
    "pvr://channels/radio/": "ActivateWindow(RadioChannels)",
    "favourites://": "ActivateWindow(favouritesbrowser)",
    "sources://pictures/": "ActivateWindow(Pictures)",
    "library://music/": "ActivateWindow(Music,root,return)",
    "library://video/": "ActivateWindow(Videos,root)",
}


def browse(include_weather=True):
    """
    Main entry point. Shows root category picker, then recursive path browser.
    Returns dict {"label", "path", "target", "display_type"} or None if cancelled.
    display_type is auto-assigned when possible, None when user should be prompted.

    Args:
        include_weather: If False, Weather is excluded from the root categories.
            Pass False when browsing for widget paths (Weather widgets are hardcoded).
    """
    categories = (
        ROOT_CATEGORIES
        if include_weather
        else [c for c in ROOT_CATEGORIES if c[1] != "__weather__"]
    )
    idx = dialog.select("Choose content source", [c[0] for c in categories])
    if idx < 0:
        return None
    label, path, target = categories[idx]
    # Weather is a special section — no browsable path, hardcoded widgets in skin XML
    if path == "__weather__":
        return {"label": "Weather", "path": "", "target": "", "display_type": ""}
    nodes = _SUBMENU_MAP.get(path)
    if nodes is not None:
        result = _browse_submenu(nodes, target)
    else:
        result = _browse_path(path=path, label=label)
        if result:
            result["target"] = target
    if result:
        result["display_type"] = _auto_display_type(result["path"], result["target"])
    return result


def build_onclick(path, target):
    """Build an onclick action string from a path and target.

    Checks for special overrides first (PVR guide, favourites, etc.),
    then falls back to ActivateWindow(Window,path,return).
    """
    # Check for exact match overrides
    override = _ONCLICK_OVERRIDES.get(path)
    if override:
        return override
    # Check prefix-based overrides for PVR paths
    if path.startswith("pvr://"):
        if "channels/tv/" in path:
            return "ActivateWindow(TVChannels)"
        if "channels/radio" in path:
            return "ActivateWindow(RadioChannels)"
        if "recordings/tv" in path:
            return "ActivateWindow(TVRecordings)"
        if "recordings/radio" in path:
            return "ActivateWindow(RadioRecordings)"
        if "timers/tv" in path:
            return "ActivateWindow(TVTimers)"
        if "timers/radio" in path:
            return "ActivateWindow(RadioTimers)"
        if "search/tv" in path:
            return "ActivateWindow(TVSearch)"
        if "search/radio" in path:
            return "ActivateWindow(RadioChannels)"
        # Generic PVR fallback
        return "ActivateWindow(TVChannels)"
    if path.startswith("addons://"):
        return "ActivateWindow(1100,%s,return)" % path
    if path.startswith("androidapp://"):
        return "StartAndroidActivity(%s)" % path
    window = WINDOW_MAP.get(target, "Videos")
    return "ActivateWindow(%s,%s,return)" % (window, path)


# ── Internal helpers ──


def _auto_display_type(path, target):
    """Determine display type from path and target.

    Returns an internal display type name when auto-assignable,
    or None when the user should be prompted (video content).
    """
    # PVR paths
    if path.startswith("pvr://"):
        # Top-level category browsers
        if path in ("pvr://tv/", "pvr://radio/"):
            return "WidgetListCategory"
        # Channel groups (for guide-style display)
        if path in ("pvr://channels/tv", "pvr://channels/radio"):
            return "WidgetListSquare"
        # Channels, recordings, timers → PVR layout
        return "WidgetListPVR"
    # Addon root categories → Category Other
    if path == "addons://":
        return "WidgetListCategory"
    # Addon / installed addon paths → Square
    if path.startswith("addons://") or path.startswith("androidapp://"):
        return "WidgetListSquare"
    # Favourites → Square
    if path.startswith("favourites://"):
        return "WidgetListFavourites"
    # Music library content → Square (album/artist artwork is square)
    if path.startswith("musicdb://"):
        return "WidgetListSquare"
    # Music library root → Category Other
    if path == "library://music/" or path.startswith("library://music/"):
        return "WidgetListCategory"
    # Music skin playlists → Square
    if target == "music":
        return "WidgetListSquare"
    # Picture sources → Category Other
    if path.startswith("sources://pictures/") or target == "pictures":
        return "WidgetListCategory"
    # Games → Square
    if target == "games":
        return "WidgetListSquare"
    # Programs → Square
    if target == "programs":
        return "WidgetListSquare"
    # Video library node paths (library://video/*/) → Category Other
    if path.startswith("library://video/"):
        return "WidgetListCategory"
    if path.startswith("sources://video/"):
        return "WidgetListCategory"
    if path.startswith("special://videoplaylists"):
        return "WidgetListCategory"
    # videodb category browsers (genres, studios, years, etc.) → Category Other
    if path.startswith("videodb://"):
        _CAT_SUFFIXES = (
            "genres/",
            "studios/",
            "years/",
            "actors/",
            "directors/",
            "countries/",
            "tags/",
            "artists/",
            "albums/",
        )
        for suffix in _CAT_SUFFIXES:
            if path.endswith(suffix):
                return "WidgetListCategory"
    # Video content (videodb://, plugin://, playlists) → prompt user
    return None


def _browse_submenu(nodes, target, direct=False):
    """Show a sub-menu of predefined nodes, then browse or return the selected one.

    Args:
        direct: If True, selected items are returned as final widget paths
            without further browsing (e.g. Installed Addons items).
    """
    idx = dialog.select("Choose category", [n[0] for n in nodes])
    if idx < 0:
        return None
    node = nodes[idx]
    label, path = node[0], node[1]
    # 3-tuple nodes have their own target override
    node_target = node[2] if len(node) > 2 else target
    # Check if this node leads to another submenu (multi-level nesting)
    sub_nodes = _SUBMENU_MAP.get(path)
    if sub_nodes is not None:
        return _browse_submenu(sub_nodes, node_target, direct=path in _DIRECT_SUBMENUS)
    # Paths that should be browsed into via _browse_path
    browsable = not direct and (
        path.startswith("videodb://")
        or path.startswith("musicdb://")
        or path.startswith("library://")
        or path.startswith("sources://")
        or path.startswith("special://profile/playlists/")
        or path.startswith("addons://sources/")
        or path.startswith("pvr://")
        or path.startswith("plugin://")
        or path.startswith("favourites://")
        or path.startswith("androidapp://")
    )
    if not browsable:
        return {"label": label, "path": path, "thumbnail": "", "target": node_target}
    result = _browse_path(path=path, label=label)
    if result:
        result["target"] = node_target
    return result


def _browse_path(path, label="", thumbnail=""):
    """
    Browse a path via JSON-RPC Files.GetDirectory with a navigation stack.
    Returns dict {"label", "path", "thumbnail"} or None.
    """
    # Stack of (path, label, thumbnail) for back navigation
    stack = []
    cur_path, cur_label, cur_thumb = path, label, thumbnail
    while True:
        _show_busy()
        results = _get_directory(cur_path) or []
        _hide_busy()
        items = []
        is_addon_root = (
            cur_path.startswith("addons://sources/") or cur_path == "addons://"
        )
        # "Use this path" option (skip for addon source roots)
        if not is_addon_root:
            use_label = _clean(cur_label) or cur_path
            li = ListItem(
                "[B]%s[/B]" % use_label,
                "Use as widget path",
                offscreen=True,
            )
            if cur_thumb:
                li.setArt({"icon": cur_thumb})
            li.setProperty(
                "item",
                json.dumps(
                    {"label": cur_label, "path": cur_path, "thumbnail": cur_thumb}
                ),
            )
            items.append(li)
        # Separate directories, file items, and next-page entries
        dirs = []
        next_pages = []
        file_items = []
        for r in results:
            if r.get("filetype") == "directory":
                raw = r.get("label", "")
                if _is_next_page(raw):
                    next_pages.append(r)
                else:
                    dirs.append(r)
            else:
                file_items.append(r)
        # Show directories first (browsable)
        for r in dirs:
            clean = _clean(r["label"])
            li = ListItem("%s" % clean, "Browse path...", offscreen=True)
            if r.get("thumbnail"):
                li.setArt({"icon": r["thumbnail"]})
            li.setProperty(
                "item",
                json.dumps(
                    {
                        "label": r["label"],
                        "path": r["file"],
                        "thumbnail": r.get("thumbnail", ""),
                        "filetype": "directory",
                    }
                ),
            )
            items.append(li)
        # Then show content items (non-browsable)
        for r in file_items:
            clean = _clean(r["label"])
            file_path = r.get("file", "")
            li = ListItem("%s" % clean, file_path, offscreen=True)
            if r.get("thumbnail"):
                li.setArt({"icon": r["thumbnail"]})
            li.setProperty(
                "item",
                json.dumps(
                    {
                        "label": r["label"],
                        "path": file_path,
                        "thumbnail": r.get("thumbnail", ""),
                        "filetype": "file",
                    }
                ),
            )
            items.append(li)
        # Next page at the bottom
        for r in next_pages:
            clean = _clean(r["label"])
            li = ListItem(
                "[B]%s[/B]" % (clean or "Next page"), "Load more...", offscreen=True
            )
            if r.get("thumbnail"):
                li.setArt({"icon": r["thumbnail"]})
            li.setProperty(
                "item",
                json.dumps(
                    {
                        "label": r["label"],
                        "path": r["file"],
                        "thumbnail": r.get("thumbnail", ""),
                        "filetype": "directory",
                    }
                ),
            )
            items.append(li)
        if not items:
            # Nothing at all — return path directly
            return {
                "label": _clean(cur_label),
                "path": cur_path,
                "thumbnail": cur_thumb,
            }
        choice = dialog.select("Choose path", items, useDetails=True)
        if choice < 0:
            if stack:
                cur_path, cur_label, cur_thumb = stack.pop()
            else:
                return None
            continue
        selected = json.loads(items[choice].getProperty("item"))
        if selected["path"] == cur_path:
            # User chose "Use as path"
            selected["label"] = _clean(selected["label"])
            return selected
        if selected.get("filetype") == "file":
            # Content item selected — re-show the same directory
            continue
        # Directory — push current onto stack and browse into it
        stack.append((cur_path, cur_label, cur_thumb))
        cur_path = selected["path"]
        cur_label = selected["label"]
        cur_thumb = selected.get("thumbnail", "")


def _get_directory(path):
    """Fetch all items from a Kodi path via JSON-RPC.

    Returns a list of dicts, each with a 'filetype' key ('directory' or 'file')
    so callers can distinguish browsable folders from content items.
    """
    command = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Files.GetDirectory",
        "params": {
            "directory": path,
            "media": "files",
            "properties": ["title", "file", "thumbnail"],
        },
    }
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(command)))
        files = response.get("result", {}).get("files") or []
    except Exception:
        return []
    # Addon paths: only show plugin:// entries
    if path.startswith("plugin://") or path.startswith("addons://"):
        return [f for f in files if f.get("file", "").startswith("plugin://")]
    return files


def _is_next_page(raw_label):
    """Detect pagination entries from Kodi addons."""
    low = raw_label.lower().replace("[b]", "").replace("[/b]", "").strip()
    if "next page" in low or "next >>" in low:
        return True
    # Matches labels like ">> Next", ">>", or ending with ">>"
    stripped = raw_label.rstrip()
    if stripped.endswith(">>"):
        return True
    return False


def _clean(label):
    """Strip Kodi formatting tags from a label."""
    if not label:
        return label
    label = label.replace("[B]", "").replace("[/B]", "").replace(" >>", "")
    while "[COLOR" in label:
        start = label.find("[COLOR")
        end = label.find("]", start) + 1
        if end == 0:
            break
        label = label[:start] + label[end:]
    label = label.replace("[/COLOR]", "")
    return label.strip()


def _show_busy():
    xbmc.executebuiltin("ActivateWindow(busydialognocancel)")


def _hide_busy():
    xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
    xbmc.executebuiltin("Dialog.Close(busydialog)")
