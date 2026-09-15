# -*- coding: utf-8 -*-
"""
Migrates data from the old custom_paths table to the new sections/widgets schema.
Runs once automatically on first launch after update.
Also supports importing configs from other skins (Nimbus, FENtastic).
Reshapes configs for home walls: stacked widgets become sections of their own,
node Category widgets become section submenus, and display types walls don't
have are remapped.
"""
import json
import sqlite3 as database
import xbmc, xbmcvfs, xbmcgui

from modules.widget_manager.config_manager import ConfigManager

old_database_path = xbmcvfs.translatePath(
    "special://profile/addon_data/script.altus.helper/cpath_cache.db"
)

# Skins whose cpath_cache.db can be imported into Altus.
# type_map converts display types that don't exist in Altus to their closest equivalent.
IMPORTABLE_SKINS = [
    {
        "name": "Nimbus",
        "addon_id": "script.nimbus.helper",
        "path": "special://profile/addon_data/script.nimbus.helper/cpath_cache.db",
        "type_map": {
            "WidgetListPoster": "WidgetListSmallPoster",
        },
    },
    {
        "name": "FENtastic",
        "addon_id": "script.fentastic.helper",
        "path": "special://profile/addon_data/script.fentastic.helper/cpath_cache.db",
        "type_map": {
            "WidgetListPoster": "WidgetListSmallPoster",
            "WidgetListBigPoster": "WidgetListPoster",
            "WidgetListLandscape": "WidgetListSmallLandscape",
            "WidgetListBigLandscape": "WidgetListLandscape",
            "WidgetListEpisodes": "WidgetListSmallLandscape",
            "WidgetListBigEpisodes": "WidgetListLandscape",
        },
    },
]

# Old hardcoded section keys → default names, onclick templates, and old skin settings
OLD_SECTION_MAP = {
    "movie": {
        "name": "Movies",
        "onclick": "ActivateWindow(Videos,{path},return)",
        "old_skin_setting": "HomeMenuNoMovieButton",
    },
    "tvshow": {
        "name": "TV Shows",
        "onclick": "ActivateWindow(Videos,{path},return)",
        "old_skin_setting": "HomeMenuNoTVShowButton",
    },
    "custom1": {
        "name": "Custom 1",
        "onclick": "ActivateWindow(Videos,{path},return)",
        "old_skin_setting": "HomeMenuNoCustom1Button",
    },
    "custom2": {
        "name": "Custom 2",
        "onclick": "ActivateWindow(Videos,{path},return)",
        "old_skin_setting": "HomeMenuNoCustom2Button",
    },
    "custom3": {
        "name": "Custom 3",
        "onclick": "ActivateWindow(Videos,{path},return)",
        "old_skin_setting": "HomeMenuNoCustom3Button",
    },
}

OLD_SECTION_ORDER = ["movie", "tvshow", "custom1", "custom2", "custom3"]

# Display types home walls don't have, mapped to the wall that replaces them.
# Flix variants exist for horizontal rows (reflection, slide-under), which a
# wall has no use for.
WALL_TYPE_MAP = {
    "WidgetListSmallPosterFlix": "WidgetListSmallPoster",
    "WidgetListLandscapeFlix": "WidgetListLandscape",
    "WidgetListSmallLandscapeFlix": "WidgetListSmallLandscape",
    "WidgetListBigPoster": "WidgetListPoster",
    "WidgetListFavourites": "WidgetListSquare",
}

# Category widgets over these listing nodes become submenus of their section:
# a wall of category tiles is just a list of places to go. Any other Category
# widget (genres, studios, playlists) lists content folders and becomes a
# poster wall instead.
CATEGORY_NODE_PREFIXES = ("library://", "addons://", "sources://")
CATEGORY_NODE_PATHS = ("pvr://tv/", "pvr://radio/")

# JSON-RPC's Files.GetDirectory refuses the add-ons root and pvr:// paths
# (CFileUtils::RemoteAccessAllowed), so their entries are mirrored from Kodi
# 21's own root lists (CAddonsDirectory RootDirectory, CPVRGUIDirectory
# GetRootDirectory): same string ids, icons and target windows. Available
# updates is kept even though Kodi only lists it while updates exist; the
# transient downloading and recently updated entries are left out. Search needs
# no special handling: an empty addons://search/ path opens the keyboard.
_PVR_ROOT = [
    (19069, "Guide", "DefaultPVRGuide.png"),
    (19019, "Channels", "DefaultPVRChannels.png"),
    (19017, "Recordings", "DefaultPVRRecordings.png"),
    (19040, "Timers", "DefaultPVRTimers.png"),
    (19138, "TimerRules", "DefaultPVRTimerRules.png"),
    (137, "Search", "DefaultPVRSearch.png"),
]
CATEGORY_NODE_ENTRIES = {
    "addons://": [
        ("$LOCALIZE[24998]", "ActivateWindow(AddonBrowser,addons://user/,return)", "DefaultAddonsInstalled.png"),
        ("$LOCALIZE[24043]", "ActivateWindow(AddonBrowser,addons://outdated/,return)", "DefaultAddonsUpdates.png"),
        ("$LOCALIZE[24033]", "ActivateWindow(AddonBrowser,addons://repos/,return)", "DefaultAddonsRepo.png"),
        ("$LOCALIZE[24041]", "InstallFromZip", "DefaultAddonsZip.png"),
        ("$LOCALIZE[137]", "ActivateWindow(AddonBrowser,addons://search/,return)", "DefaultAddonsSearch.png"),
    ],
    "pvr://tv/": [
        ("$LOCALIZE[%d]" % sid, "ActivateWindow(TV%s)" % window, icon)
        for sid, window, icon in _PVR_ROOT
    ],
    "pvr://radio/": [
        ("$LOCALIZE[%d]" % sid, "ActivateWindow(Radio%s)" % window, icon)
        for sid, window, icon in _PVR_ROOT
    ],
}


def _old_table_exists(db_path=None):
    """Check if the old custom_paths table exists and has data."""
    path = db_path or old_database_path
    if not xbmcvfs.exists(path):
        return False
    try:
        dbcon = database.connect(path, timeout=20)
        result = dbcon.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_paths'"
        ).fetchone()
        if not result:
            dbcon.close()
            return False
        count = dbcon.execute("SELECT COUNT(*) FROM custom_paths").fetchone()[0]
        dbcon.close()
        return count > 0
    except Exception:
        return False


def _read_old_data(db_path=None):
    """Read all rows from the old custom_paths table."""
    path = db_path or old_database_path
    dbcon = database.connect(path, timeout=20)
    rows = dbcon.execute("SELECT * FROM custom_paths").fetchall()
    dbcon.close()
    data = {}
    for row in rows:
        data[row[0]] = {
            "cpath_setting": row[0],
            "cpath_path": row[1],
            "cpath_header": row[2],
            "cpath_type": row[3],
            "cpath_label": row[4],
        }
    return data


def _parse_stacked_info(cpath_type, cpath_label):
    """Determine if a widget is stacked and extract the stacked display type.

    Old format: cpath_type stores the child display type with "Stacked" suffix.
        e.g. "WidgetListSmallPosterStacked"
    The parent type is always WidgetListCategoryStacked.
    Non-stacked types never end with "Stacked".
    """
    is_stacked = 1 if (cpath_type or "").endswith("Stacked") else 0
    stacked_type = ""
    if is_stacked:
        # Strip "Stacked" suffix to get the base child display type
        # e.g. "WidgetListSmallPosterStacked" → "WidgetListSmallPoster"
        stacked_type = cpath_type[:-7] if cpath_type.endswith("Stacked") else cpath_type
    return is_stacked, stacked_type


def _map_type(cpath_type, type_map):
    """Map a display type using the provided mapping.

    Handles both base types (WidgetListLandscape) and stacked variants
    (WidgetListLandscapeStacked) using the same base mapping.
    """
    if not type_map or not cpath_type:
        return cpath_type
    if cpath_type in type_map:
        return type_map[cpath_type]
    if cpath_type.endswith("Stacked"):
        base = cpath_type[:-7]
        if base in type_map:
            return type_map[base] + "Stacked"
    return cpath_type


def _migrate_data(old_data, cm, migrate_skin_settings=False, type_map=None):
    """Core migration logic: create sections and widgets from old cpath data.

    Args:
        old_data: dict from _read_old_data()
        cm: open ConfigManager instance
        migrate_skin_settings: if True, migrate old visibility skin settings
        type_map: optional dict mapping source display types to Altus equivalents
    Returns:
        True if any sections were created.
    """
    created = False
    for old_section_key in OLD_SECTION_ORDER:
        info = OLD_SECTION_MAP[old_section_key]
        main_menu_key = "%s.main_menu" % old_section_key
        main_menu = old_data.get(main_menu_key)
        widgets = {k: v for k, v in old_data.items()
                   if k.startswith("%s.widget." % old_section_key)}
        if not main_menu and not widgets:
            continue
        onclick = ""
        name = info["name"]
        if main_menu:
            path = main_menu["cpath_path"]
            onclick = info["onclick"].format(path=path)
            if main_menu["cpath_header"]:
                name = main_menu["cpath_header"]
        section_id = cm.add_section(
            name=name,
            onclick=onclick,
        )
        created = True
        if migrate_skin_settings:
            old_setting = info["old_skin_setting"]
            if xbmc.getCondVisibility("Skin.HasSetting(%s)" % old_setting):
                xbmc.executebuiltin("Skin.SetBool(HomeMenuNoSection_%s)" % section_id)
        sorted_widgets = sorted(
            widgets.values(),
            key=lambda w: int(w["cpath_setting"].split(".")[-1]),
        )
        for widget_data in sorted_widgets:
            cpath_type = _map_type(widget_data["cpath_type"] or "", type_map)
            cpath_label = widget_data["cpath_label"] or ""
            is_stacked, stacked_type = _parse_stacked_info(cpath_type, cpath_label)
            if is_stacked:
                display_type = "WidgetListCategoryStacked"
            else:
                display_type = cpath_type
            cm.add_widget(
                section_id=section_id,
                path=widget_data["cpath_path"],
                label=widget_data["cpath_header"],
                display_type=display_type,
                is_stacked=is_stacked,
                stacked_type=stacked_type,
                target="videos",
            )
    return created


def _wall_type(display_type):
    """Map a display type (optionally Stacked-suffixed) to the one its wall uses."""
    if display_type and display_type.endswith("Stacked"):
        display_type = display_type[:-7]
    return WALL_TYPE_MAP.get(display_type, display_type)


def _list_directory(path):
    """Items of a path via JSON-RPC, or None if the listing failed."""
    command = {
        "jsonrpc": "2.0",
        "id": "script.altus.helper",
        "method": "Files.GetDirectory",
        "params": {
            "directory": path,
            "media": "files",
            "properties": ["title", "file", "thumbnail"],
        },
    }
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(command)))
    except Exception:
        return None
    result = response.get("result")
    if result is None:
        return None
    return result.get("files") or []


def _list_subfolders(path):
    """Subfolders of a stacked widget's path, or None if the listing failed.

    Only directories count, matching what a stacked widget's child could load.
    """
    items = _list_directory(path)
    if items is None:
        return None
    return [f for f in items if f.get("filetype") == "directory"]


def _with_slash(path):
    """Path with one trailing slash; rstrip would eat the "//" of "addons://"."""
    return path if path.endswith("/") else path + "/"


def _is_category_node(path):
    if path.startswith(CATEGORY_NODE_PREFIXES):
        return True
    return _with_slash(path) in CATEGORY_NODE_PATHS


def _list_sources(media):
    """A media type's sources via Files.GetSources, or None if that failed."""
    command = {
        "jsonrpc": "2.0",
        "id": "script.altus.helper",
        "method": "Files.GetSources",
        "params": {"media": media},
    }
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(command)))
    except Exception:
        return None
    result = response.get("result")
    if result is None:
        return None
    return result.get("sources") or []


def _category_entries(widget):
    """(label, onclick, icon) submenu entries for a node Category widget.

    Returns None when the node can't be listed right now, so the caller leaves
    the widget for the next run.
    """
    from modules.widget_manager.path_browser import build_onclick

    path = widget["path"]
    fixed = CATEGORY_NODE_ENTRIES.get(_with_slash(path))
    if fixed is not None:
        return list(fixed)
    if path.startswith("sources://") and not path.startswith("sources://video"):
        # Only video sources pass RemoteAccessAllowed; the rest come from
        # Files.GetSources, which lists the same user sources.
        media = path[len("sources://"):].strip("/")
        sources = _list_sources(media)
        if sources is None:
            return None
        return [
            (s["label"], build_onclick(s["file"], widget["target"]), "")
            for s in sources
        ]
    items = _list_directory(path)
    if items is None:
        return None
    return [
        (i["label"], build_onclick(i["file"], widget["target"]), i.get("thumbnail", ""))
        for i in items
    ]


def _expand_stacked_widgets(cm):
    """Turn every stacked widget into a section with one tab per subfolder.

    New sections go directly after their parent section, in widget order, and
    inherit its icon. A widget whose folder can't be listed right now (addon
    missing or disabled, network not up yet at startup) is left untouched so
    the next run retries it; converting it to a fallback would be permanent.
    A folder that lists fine but has no subfolders becomes a plain widget of
    that folder instead.
    """
    from modules.widget_manager.path_browser import build_onclick

    for section in cm.get_sections():
        stacked = [w for w in cm.get_widgets(section["id"]) if w["is_stacked"]]
        inserted = 0
        for widget in stacked:
            folders = _list_subfolders(widget["path"])
            if folders is None:
                continue
            tab_type = _wall_type(widget["stacked_type"] or "WidgetListPoster")
            if not folders:
                cm.update_widget(
                    widget["id"], is_stacked=0, stacked_type="", display_type=tab_type
                )
                continue
            hidden = section["visible"] == "false" or widget["visible"] == "false"
            new_id = cm.add_section(
                widget["label"],
                onclick=build_onclick(widget["path"], widget["target"]),
                icon=section["icon"],
                visible="false" if hidden else "",
            )
            inserted += 1
            parent_position = cm.get_section(section["id"])["position"]
            cm.reorder_section(new_id, parent_position + inserted)
            for folder in folders:
                cm.add_widget(
                    section_id=new_id,
                    path=folder["file"],
                    label=folder["label"],
                    display_type=tab_type,
                    target=widget["target"],
                )
            cm.remove_widget(widget["id"])


def _convert_category_widgets(cm):
    """Move node Category widgets into their section's submenu.

    Each entry becomes a submenu after the existing ones, built the way the
    manager's multi-add builds them: label, onclick and icon. A hidden widget
    gives hidden entries. As with stacked widgets, a node that can't be listed
    right now is left for the next run. Category widgets over anything else
    become poster walls.
    """
    for section in cm.get_sections():
        for widget in cm.get_widgets(section["id"]):
            if widget["is_stacked"] or widget["display_type"] != "WidgetListCategory":
                continue
            if not _is_category_node(widget["path"]):
                cm.update_widget(widget["id"], display_type="WidgetListPoster")
                continue
            entries = _category_entries(widget)
            if entries is None:
                continue
            visible = "false" if widget["visible"] == "false" else ""
            for label, onclick, icon in entries:
                cm.add_submenu(
                    section["id"], label, onclick=onclick, icon=icon, visible=visible
                )
            cm.remove_widget(widget["id"])


def _remap_wall_types(cm):
    """Rewrite display types walls don't have, in both type columns."""
    for old, new in WALL_TYPE_MAP.items():
        cm.dbcur.execute(
            "UPDATE widgets SET display_type = ? WHERE display_type = ?", (new, old)
        )
        cm.dbcur.execute(
            "UPDATE widgets SET stacked_type = ? WHERE stacked_type = ?", (new, old)
        )
    cm.dbcon.commit()


def migrate_to_walls(cm=None):
    """Reshape the active widget config for home walls.

    Safe to run any number of times: with no stacked widgets, Category widgets
    or wall-less display types left, it changes nothing. Pass an open ConfigManager to
    reuse it; otherwise one is opened and closed here.
    """
    own = cm is None
    if own:
        cm = ConfigManager()
    try:
        _expand_stacked_widgets(cm)
        _convert_category_widgets(cm)
        _remap_wall_types(cm)
    finally:
        if own:
            cm.close()


def migrate():
    """Bring the widget config up to date. Returns True if custom_paths data was migrated.

    Runs the one-time custom_paths import, then reshapes whatever config is
    active for walls. The walls step repeats safely, so every caller of
    migrate() gets it, including configs that finished the old migration
    long ago.
    """
    result = _migrate_custom_paths()
    migrate_to_walls()
    return result


def _migrate_custom_paths():
    """Migrate old custom_paths data to the new schema. Returns True if migration ran."""
    if not _old_table_exists():
        return False
    old_data = _read_old_data()
    if not old_data:
        return False
    cm = ConfigManager()
    count = cm.dbcur.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    if count > 0:
        cm.close()
        return False
    result = _migrate_data(old_data, cm, migrate_skin_settings=True)
    cm.close()
    return result


def import_from_skin():
    """Scan for importable skin configs and let the user choose one to import.

    Replaces the current Altus widget config with the imported data.
    """
    available = []
    for skin in IMPORTABLE_SKINS:
        db_path = xbmcvfs.translatePath(skin["path"])
        if _old_table_exists(db_path):
            available.append((skin["name"], db_path, skin.get("type_map", {})))
    if not available:
        xbmcgui.Dialog().ok(
            "Import Widget Config",
            "No importable widget configurations found.[CR][CR]"
            "Looked for configs from: %s" % ", ".join(s["name"] for s in IMPORTABLE_SKINS),
        )
        return False
    if len(available) == 1:
        chosen_name, chosen_path, chosen_type_map = available[0]
    else:
        names = [name for name, _, _ in available]
        idx = xbmcgui.Dialog().select("Select a skin to import from", names)
        if idx < 0:
            return False
        chosen_name, chosen_path, chosen_type_map = available[idx]
    if not xbmcgui.Dialog().yesno(
        "Import Widget Config",
        "Import widget configuration from [B]%s[/B]?[CR][CR]"
        "This will replace your current Altus widget setup." % chosen_name,
    ):
        return False
    # Auto-save current config before overwriting
    from modules.widget_manager.config_manager import save_config_as, get_active_config, sanitize_config_name
    active = get_active_config()
    if active:
        save_config_as(active)
    else:
        if xbmcgui.Dialog().yesno(
            "Import Widget Config",
            "Your current profile is unsaved and will be lost.[CR][CR]"
            "Save it first?",
        ):
            name = sanitize_config_name(xbmcgui.Dialog().input("Enter a name for your current profile"))
            if name:
                save_config_as(name)
    old_data = _read_old_data(chosen_path)
    if not old_data:
        xbmcgui.Dialog().ok("Import Widget Config", "Failed to read data from %s config." % chosen_name)
        return False
    cm = ConfigManager()
    # Clear existing config
    for section in cm.get_sections():
        cm.remove_section(section["id"])
    result = _migrate_data(old_data, cm, type_map=chosen_type_map)
    if result:
        migrate_to_walls(cm)
    cm.close()
    if result:
        # Other skins carry no search config, so an import would otherwise fall
        # through to catalog defaults and silently replace the user's search
        # widgets. The imported skin contributes home widgets only — seed search
        # from what's active so it survives the import. Must run BEFORE
        # Skin.SetString, while the source still resolves to the outgoing
        # profile.
        from modules.search_manager.default_config import (
            apply_profile,
            seed_profile_config,
        )

        seed_profile_config(chosen_name)
        xbmc.executebuiltin("Skin.SetString(altus_active_widget_config,%s)" % chosen_name)
        save_config_as(chosen_name)
        # Name passed explicitly — Skin.SetString above is async, so resolving
        # it from the skin string would still read the previous profile.
        apply_profile(chosen_name)
        from modules.widget_manager.xml_generator import generate_and_reload
        generate_and_reload(active_config=chosen_name)
        xbmcgui.Dialog().ok(
            "Import Widget Config",
            "Successfully imported widget configuration from [B]%s[/B]." % chosen_name,
        )
    else:
        xbmcgui.Dialog().ok("Import Widget Config", "No sections or widgets found in %s config." % chosen_name)
    return result
