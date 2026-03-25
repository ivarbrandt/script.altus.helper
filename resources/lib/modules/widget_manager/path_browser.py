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
    ("Video Addons", "addons://sources/video", "videos"),
    ("Music Addons", "addons://sources/music", "music"),
    ("Program Addons", "addons://sources/executable", "programs"),
    ("Picture Addons", "addons://sources/image", "pictures"),
    ("Game Addons", "addons://sources/game", "games"),
    ("Video Library", "__video_library__", "videos"),
    ("Music Library", "__music_library__", "music"),
    ("Live TV (PVR)", "__pvr_tv__", "videos"),
    ("Radio (PVR)", "__pvr_radio__", "music"),
    ("Pictures", "__pictures__", "pictures"),
    ("Games", "__games__", "games"),
    ("Video Playlists", "special://profile/playlists/video/", "videos"),
    ("Music Playlists", "special://profile/playlists/music/", "music"),
    ("Skin Playlists", "__skin_playlists__", "videos"),
    ("Video Sources", "sources://video/", "videos"),
    ("Music Sources", "sources://music/", "music"),
    ("Favourites", "favourites://", "videos"),
    ("Installed Addons", "__installed_addons__", "addons"),
]

# ── Library sub-menus ──

VIDEO_LIBRARY_NODES = [
    ("Movies", "videodb://movies/titles/"),
    ("Movie Genres", "videodb://movies/genres/"),
    ("Movie Years", "videodb://movies/years/"),
    ("Movie Actors", "videodb://movies/actors/"),
    ("Movie Directors", "videodb://movies/directors/"),
    ("Movie Studios", "videodb://movies/studios/"),
    ("Movie Countries", "videodb://movies/countries/"),
    ("Movie Sets", "videodb://movies/sets/"),
    ("Movie Tags", "videodb://movies/tags/"),
    ("TV Shows", "videodb://tvshows/titles/"),
    ("TV Show Genres", "videodb://tvshows/genres/"),
    ("TV Show Years", "videodb://tvshows/years/"),
    ("TV Show Actors", "videodb://tvshows/actors/"),
    ("TV Show Studios", "videodb://tvshows/studios/"),
    ("TV Show Tags", "videodb://tvshows/tags/"),
    ("Recently Added Movies", "videodb://recentlyaddedmovies/"),
    ("Recently Added Episodes", "videodb://recentlyaddedepisodes/"),
    ("Recently Added Music Videos", "videodb://recentlyaddedmusicvideos/"),
    ("In Progress Movies", "videodb://inprogressmovies/"),
    ("In Progress TV Shows", "videodb://inprogresstvshows/"),
    ("Music Videos", "videodb://musicvideos/titles/"),
    ("Music Video Genres", "videodb://musicvideos/genres/"),
    ("Music Video Years", "videodb://musicvideos/years/"),
    ("Music Video Artists", "videodb://musicvideos/artists/"),
    ("Music Video Albums", "videodb://musicvideos/albums/"),
    ("Music Video Studios", "videodb://musicvideos/studios/"),
    ("Music Video Tags", "videodb://musicvideos/tags/"),
    ("Video Library Root", "library://video/"),
    ("Music Video Library Root", "library://video/musicvideos/"),
]

MUSIC_LIBRARY_NODES = [
    ("Artists", "musicdb://artists/"),
    ("Albums", "musicdb://albums/"),
    ("Songs", "musicdb://songs/"),
    ("Genres", "musicdb://genres/"),
    ("Years", "musicdb://years/"),
    ("Recently Added Albums", "musicdb://recentlyaddedalbums/"),
    ("Recently Played Albums", "musicdb://recentlyplayedalbums/"),
    ("Recently Played Songs", "musicdb://recentlyplayedsongs/"),
    ("Top 100 Songs", "musicdb://top100/songs/"),
    ("Top 100 Albums", "musicdb://top100/albums/"),
    ("Compilations", "musicdb://compilations/"),
    ("Music Library Root", "library://music/"),
]

# ── PVR sub-menus ──

PVR_TV_NODES = [
    ("TV Categories", "pvr://tv/"),
    ("TV Channels (Last Played)", "pvr://channels/tv/*?view=lastplayed"),
    ("TV Channels", "pvr://channels/tv/"),
    ("TV Recordings", "pvr://recordings/tv/active?view=flat"),
    ("TV Timers", "pvr://timers/tv/timers/?view=hidedisabled"),
    ("TV Channel Groups", "pvr://channels/tv"),
    ("TV Saved Searches", "pvr://search/tv/savedsearches"),
]

PVR_RADIO_NODES = [
    ("Radio Categories", "pvr://radio/"),
    ("Radio Channels (Last Played)", "pvr://channels/radio/*?view=lastplayed"),
    ("Radio Channels", "pvr://channels/radio/"),
    ("Radio Recordings", "pvr://recordings/radio/active?view=flat"),
    ("Radio Timers", "pvr://timers/radio/timers/?view=hidedisabled"),
    ("Radio Channel Groups", "pvr://channels/radio"),
    ("Radio Saved Searches", "pvr://search/radio/savedsearches"),
]

# ── Pictures sub-menu ──

PICTURES_NODES = [
    ("Picture Sources", "sources://pictures/"),
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
    ("Most Played Albums", "special://skin/playlists/mostplayed_albums.xsp"),
    ("Unwatched Music Videos", "special://skin/playlists/unwatched_musicvideos.xsp"),
    ("Random Music Video Artists", "special://skin/playlists/random_musicvideo_artists.xsp"),
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

_SUBMENU_MAP = {
    "__video_library__": VIDEO_LIBRARY_NODES,
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


def browse():
    """
    Main entry point. Shows root category picker, then recursive path browser.
    Returns dict {"label", "path", "target", "display_type"} or None if cancelled.
    display_type is auto-assigned when possible, None when user should be prompted.
    """
    idx = dialog.select("Choose content source", [c[0] for c in ROOT_CATEGORIES])
    if idx < 0:
        return None
    label, path, target = ROOT_CATEGORIES[idx]
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
        if "channels/tv" in path:
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
            return "ActivateWindow(TVChannels)"
        if "search/radio" in path:
            return "ActivateWindow(RadioChannels)"
        # Generic PVR fallback
        return "ActivateWindow(TVChannels)"
    if path.startswith("addons://"):
        return "ActivateWindow(AddonBrowser,%s,return)" % path
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
            return "WidgetListCategoryOther"
        # Channel groups (for guide-style display)
        if path in ("pvr://channels/tv", "pvr://channels/radio"):
            return "WidgetListSquareNoInfo"
        # Channels, recordings, timers → PVR layout
        return "WidgetListPVR"
    # Addon / installed addon paths → Square
    if path.startswith("addons://") or path.startswith("androidapp://"):
        return "WidgetListSquareNoInfo"
    # Favourites → Square
    if path.startswith("favourites://"):
        return "WidgetListSquareNoInfo"
    # Music library content → Square (album/artist artwork is square)
    if path.startswith("musicdb://"):
        return "WidgetListSquare"
    # Music library root → Category Other
    if path == "library://music/" or path.startswith("library://music/"):
        return "WidgetListCategoryOther"
    # Music skin playlists → Square
    if target == "music":
        return "WidgetListSquare"
    # Picture sources → Category Other
    if path.startswith("sources://pictures/") or target == "pictures":
        return "WidgetListCategoryOther"
    # Games → Square
    if target == "games":
        return "WidgetListSquare"
    # Programs → Square
    if target == "programs":
        return "WidgetListSquareNoInfo"
    # Video library/source root paths → Category Other
    if path in ("library://video/", "library://video/musicvideos/"):
        return "WidgetListCategoryOther"
    if path.startswith("sources://video/"):
        return "WidgetListCategoryOther"
    if path.startswith("special://videoplaylists"):
        return "WidgetListCategoryOther"
    # Video content (videodb://, plugin://, playlists) → prompt user
    return None


def _browse_submenu(nodes, target):
    """Show a sub-menu of predefined nodes, then browse or return the selected one."""
    idx = dialog.select("Choose category", [n[0] for n in nodes])
    if idx < 0:
        return None
    node = nodes[idx]
    label, path = node[0], node[1]
    # 3-tuple nodes have their own target override
    node_target = node[2] if len(node) > 2 else target
    # Direct-return paths — these are used as widget content paths, not browsed into
    # Only library/source paths need recursive browsing
    browsable = (
        path.startswith("videodb://")
        or path.startswith("musicdb://")
        or path.startswith("library://")
        or path.startswith("sources://")
        or path.startswith("special://profile/playlists/")
    )
    if not browsable:
        return {"label": label, "path": path, "thumbnail": "", "target": node_target}
    result = _browse_path(path=path, label=label)
    if result:
        result["target"] = node_target
    return result


def _browse_path(path, label="", thumbnail=""):
    """
    Recursively browse a path via JSON-RPC Files.GetDirectory.
    Returns dict {"label", "path", "thumbnail"} or None.
    """
    _show_busy()
    results = _get_directory(path)
    _hide_busy()
    if results is None:
        results = []
    items = []
    is_addon_root = path.startswith("addons://sources/") or path == "addons://"
    # "Use this path" option (skip for addon source roots)
    if not is_addon_root:
        use_label = _clean(label) or path
        li = ListItem(
            "[B]%s[/B]" % use_label,
            "Use as widget path",
            offscreen=True,
        )
        if thumbnail:
            li.setArt({"icon": thumbnail})
        li.setProperty(
            "item",
            json.dumps({"label": label, "path": path, "thumbnail": thumbnail}),
        )
        items.append(li)
    for r in results:
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
                }
            ),
        )
        items.append(li)
    if not items:
        # Nothing browsable and no "use" option — return path directly
        return {"label": _clean(label), "path": path, "thumbnail": thumbnail}
    choice = dialog.select("Choose path", items, useDetails=True)
    if choice < 0:
        return None
    selected = json.loads(items[choice].getProperty("item"))
    if selected["path"] == path:
        # User chose "Use as path"
        selected["label"] = _clean(selected["label"])
        return selected
    # Browse deeper
    return _browse_path(
        path=selected["path"],
        label=selected["label"],
        thumbnail=selected.get("thumbnail", ""),
    )


def _get_directory(path):
    """Fetch browsable subdirectories from a Kodi path via JSON-RPC."""
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
    # Addon paths: only show plugin:// directories
    if path.startswith("plugin://") or path.startswith("addons://"):
        return [
            f
            for f in files
            if f.get("file", "").startswith("plugin://")
            and f.get("filetype") == "directory"
        ]
    # All other paths: show any directory entries
    return [f for f in files if f.get("filetype") == "directory"]


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
