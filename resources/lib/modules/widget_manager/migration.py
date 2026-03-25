# -*- coding: utf-8 -*-
"""
Migrates data from the old custom_paths table to the new sections/widgets schema.
Runs once automatically on first launch after update.
"""
import sqlite3 as database
import xbmc
import xbmcvfs

from modules.widget_manager.config_manager import ConfigManager

old_database_path = xbmcvfs.translatePath(
    "special://profile/addon_data/script.altus.helper/cpath_cache.db"
)

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


def _old_table_exists():
    """Check if the old custom_paths table exists and has data."""
    try:
        dbcon = database.connect(old_database_path, timeout=20)
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


def _read_old_data():
    """Read all rows from the old custom_paths table."""
    dbcon = database.connect(old_database_path, timeout=20)
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


def migrate():
    """Migrate old custom_paths data to the new schema. Returns True if migration ran."""
    if not _old_table_exists():
        return False
    old_data = _read_old_data()
    if not old_data:
        return False
    cm = ConfigManager()
    # DEV: wipe new DB so we can re-migrate after old config changes
    cm.dbcur.execute("DELETE FROM widgets")
    cm.dbcur.execute("DELETE FROM submenus")
    cm.dbcur.execute("DELETE FROM sections")
    cm.dbcur.execute("DELETE FROM sqlite_sequence")
    cm.dbcon.commit()
    # Create sections and migrate widgets
    section_ids = {}
    for old_section_key in OLD_SECTION_ORDER:
        info = OLD_SECTION_MAP[old_section_key]
        # Check if this old section has a main menu entry
        main_menu_key = "%s.main_menu" % old_section_key
        main_menu = old_data.get(main_menu_key)
        # Check if this old section has any widgets
        widgets = {k: v for k, v in old_data.items()
                   if k.startswith("%s.widget." % old_section_key)}
        # Skip sections with no menu and no widgets
        if not main_menu and not widgets:
            continue
        # Build onclick from main menu path if available
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
        section_ids[old_section_key] = section_id
        # Migrate old visibility skin setting to new format
        old_setting = info["old_skin_setting"]
        if xbmc.getCondVisibility("Skin.HasSetting(%s)" % old_setting):
            xbmc.executebuiltin("Skin.SetBool(HomeMenuNoSection_%s)" % section_id)
        # Migrate widgets for this section
        sorted_widgets = sorted(
            widgets.values(),
            key=lambda w: int(w["cpath_setting"].split(".")[-1]),
        )
        for widget_data in sorted_widgets:
            cpath_type = widget_data["cpath_type"] or ""
            cpath_label = widget_data["cpath_label"] or ""
            is_stacked, stacked_type = _parse_stacked_info(cpath_type, cpath_label)
            # For stacked widgets, display_type is WidgetListCategoryStacked (the parent)
            # For non-stacked, display_type is cpath_type directly
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
    cm.close()
    return True
