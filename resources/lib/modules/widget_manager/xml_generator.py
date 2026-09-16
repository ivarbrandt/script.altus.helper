# -*- coding: utf-8 -*-
"""
XML Generation Engine for the widget management system.
Reads config from ConfigManager and generates:
  - script-altus-home_walls.xml   (per-section tab row + one wall per widget)
  - script-altus-main_menu.xml    (all sections as main menu items)
  - script-altus-submenus.xml     (per-section submenu lists for home screen)
"""
import xbmc, xbmcvfs, xbmcgui
from threading import Thread

from modules.widget_manager.config_manager import ConfigManager

MAIN_MENU_XML_FILE = "special://skin/xml/script-altus-main_menu.xml"
HOME_WALLS_XML_FILE = "special://skin/xml/script-altus-home_walls.xml"
SUBMENUS_XML_FILE = "special://skin/xml/script-altus-submenus.xml"
# Base ID for all widget-related controls. Each section occupies a 100-ID range:
#   section base = BASE_ID + (section_position - 1) * 100
#   group = base, tab row = base + 2, walls group = base + 3
#   widget list_id (its wall) = base + 10 + widget_position
# Supports up to 60 sections (3000-8999) and 89 widgets per section.
BASE_ID = 3000

# Wall include for each stored display type. Walls have no Flix or big
# poster variants; migration remaps those, but a saved profile loaded without
# migrating can still carry them, so they map here too. Anything unknown falls
# back to a poster wall.
WALL_INCLUDES = {
    "WidgetListPoster": "HomeWallPoster",
    "WidgetListBigPoster": "HomeWallPoster",
    "WidgetListSmallPoster": "HomeWallSmallPoster",
    "WidgetListSmallPosterFlix": "HomeWallSmallPoster",
    "WidgetListLandscape": "HomeWallLandscape",
    "WidgetListLandscapeFlix": "HomeWallLandscape",
    "WidgetListSmallLandscape": "HomeWallSmallLandscape",
    "WidgetListSmallLandscapeFlix": "HomeWallSmallLandscape",
    "WidgetListSquare": "HomeWallSquare",
    "WidgetListFavourites": "HomeWallSquare",
    "WidgetListCategory": "HomeWallCategory",
    "WidgetListPVR": "HomeWallPVR",
}

# Hardcoded icon overrides for specific widget paths. Keyed by widget path,
# value is emitted as the `icon` param on the include.
HARDCODED_WIDGET_ICONS = {
    "special://videoplaylists/": "$VAR[WidgetPlaylistIconVar]",
    "videodb://movies/genres/": "$VAR[WidgetGenreIconVar]",
    "videodb://tvshows/studios/": "$VAR[WidgetStudioIconVar]",
    "videodb://musicvideos/studios/": "$VAR[WidgetStudioIconVar]",
}


def _escape_ampersand(text):
    """Ensure & is escaped as &amp; for XML, but don't double-escape."""
    if "&amp;" not in text:
        return text.replace("&", "&amp;")
    return text


def _compute_section_base(section_position):
    """Compute the base ID for a section's 100-ID range."""
    return BASE_ID + (section_position - 1) * 100


def _compute_group_id(section_position):
    """Compute the group control ID for a section."""
    return _compute_section_base(section_position)


def _compute_row_id(section_position):
    """Compute the tab row control ID for a section (base + 2)."""
    return _compute_section_base(section_position) + 2


def _compute_walls_id(section_position):
    """Compute the walls group control ID for a section (base + 3)."""
    return _compute_section_base(section_position) + 3


def _compute_submenu_list_id(section_position):
    """Compute the submenu list control ID for a section (base + 50)."""
    return _compute_section_base(section_position) + 50


def _compute_list_id(section_position, widget_position):
    """Compute a unique control ID for a widget.

    Format: section_base + 10 + widget_pos
    e.g. section 1, widget 1 → 3000 + 10 + 1 = 3011
    """
    return _compute_section_base(section_position) + 10 + widget_position


def _wall_include(widget):
    """Pick the wall include for a widget.

    A stacked widget still here couldn't be migrated (its folder didn't list),
    so its wall shows the folder itself as categories.
    """
    if widget["is_stacked"]:
        return "HomeWallCategory"
    return WALL_INCLUDES.get(widget["display_type"], "HomeWallPoster")


def _build_tab_item_xml(widget, list_id):
    """Generate the tab row item for one widget.

    The item id is the widget position, which is what the wall's
    Container(row).HasFocus() visibility matches. Clicking opens the widget's
    content in its own window. Tabs of walls that ended up empty hide.
    """
    from modules.widget_manager.path_browser import build_onclick

    return """
          <item id="{item_id}">
            <label>{label}</label>
            <onclick>{onclick}</onclick>
            <property name="wall_id">$NUMBER[{list_id}]</property>
            <visible>Integer.IsGreater(Container({list_id}).NumItems,0) | Container({list_id}).IsUpdating</visible>
          </item>""".format(
        item_id=widget["position"],
        label=_escape_ampersand(widget["label"]),
        onclick=_escape_ampersand(build_onclick(widget["path"], widget["target"])),
        list_id=list_id,
    )


MANUAL_LOADING_SETTING = "Skin.HasSetting(HomeWalls.ManualLoading)"


def _shown_wall_property(row_id):
    """Home window property holding the list id of the wall a section shows
    in manual tab loading. Set by the tab row's down action; empty means the
    section's first wall."""
    return "altus_wall_%s" % row_id


def _wall_has_items(list_id):
    """A wall is usable while it holds items or is still fetching them. This
    is what the tab's own visibility uses, so it matches whether the tab for
    this wall is in the row."""
    return "[Integer.IsGreater(Container({list_id}).NumItems,0) | Container({list_id}).IsUpdating]".format(
        list_id=list_id,
    )


def _stored_wall_shown(row_id, section_list_ids):
    """True while some wall in the section satisfies the stored property.

    False means nothing has been entered yet, or what was entered has gone
    empty, and the section falls back to the first tab's wall. The tab row
    marks the open tab off the same condition, so the marker follows the
    handoff instead of lagging on the tab that emptied.
    """
    prop = "Window(Home).Property(%s)" % _shown_wall_property(row_id)
    return " | ".join(
        "[String.IsEqual({prop},{sibling}) + {has_items}]".format(
            prop=prop,
            sibling=sibling,
            has_items=_wall_has_items(sibling),
        )
        for sibling in section_list_ids
    )


def _wall_visible_condition(widget, list_id, row_id, section_list_ids):
    """Visibility of one wall for both tab loading modes.

    Auto shows the wall of the highlighted tab. Manual shows the wall last
    entered from the tab row, so highlighting a tab doesn't show (and
    allocate) its wall.

    The stored wall can go empty later (its widget stopped returning items),
    which hides its tab but leaves the property naming it. So a stored wall
    only shows while it still has items, and the first tab's wall takes over
    whenever no wall in the section satisfies the stored property: nothing
    stored yet, or what was stored is gone. That needs every wall in the
    section, since a wall can't otherwise tell an empty stored wall from one
    that is simply not itself.
    """
    prop = "Window(Home).Property(%s)" % _shown_wall_property(row_id)
    stored = "[String.IsEqual({prop},{list_id}) + {has_items}]".format(
        prop=prop,
        list_id=list_id,
        has_items=_wall_has_items(list_id),
    )
    first = "[![{stored_shown}] + String.IsEqual(Container({row_id}).ListItemAbsolute(0).Property(wall_id),{list_id})]".format(
        stored_shown=_stored_wall_shown(row_id, section_list_ids),
        list_id=list_id,
        row_id=row_id,
    )
    manual = "[{stored} | {first}]".format(stored=stored, first=first)
    return "[!{setting} + Container({row_id}).HasFocus({item_id})] | [{setting} + {manual}]".format(
        setting=MANUAL_LOADING_SETTING,
        row_id=row_id,
        item_id=widget["position"],
        manual=manual,
    )


def _build_wall_xml(widget, list_id, row_id, section_list_ids):
    """Generate the wall include call for one widget."""
    xml = """
        <include content="{include}">
          <param name="list_id" value="{list_id}"/>
          <param name="row_id" value="{row_id}"/>
          <param name="visible" value="{visible}"/>
          <param name="content_path" value="{path}"/>
          <param name="widget_target" value="{target}"/>""".format(
        include=_wall_include(widget),
        list_id=list_id,
        row_id=row_id,
        visible=_wall_visible_condition(widget, list_id, row_id, section_list_ids),
        path=_escape_ampersand(widget["path"]),
        target=widget["target"],
    )
    if widget.get("sortby"):
        xml += '\n          <param name="sortby" value="%s"/>' % widget["sortby"]
    if widget.get("sortorder"):
        xml += '\n          <param name="sortorder" value="%s"/>' % widget["sortorder"]
    if widget.get("limit_num"):
        xml += '\n          <param name="limit" value="%s"/>' % widget["limit_num"]
    icon = HARDCODED_WIDGET_ICONS.get(widget["path"])
    if icon:
        xml += '\n          <param name="icon" value="%s"/>' % icon
    if widget["path"].startswith("addons://"):
        xml += '\n          <param name="fallback_icon" value="DefaultAddon.png"/>'
    xml += "\n        </include>"
    return xml


def _build_wall_section_xml(section_pos, widgets):
    """Generate one section: header, tab row and a wall per widget.

    The group's defaultcontrol is the tab row, not always, so coming back from
    the main menu restores whichever of row or wall had focus last.
    """
    group_id = _compute_group_id(section_pos)
    row_id = _compute_row_id(section_pos)
    walls_id = _compute_walls_id(section_pos)
    tabs = ""
    walls = ""
    section_list_ids = [
        _compute_list_id(section_pos, widget["position"]) for widget in widgets
    ]
    for widget in widgets:
        list_id = _compute_list_id(section_pos, widget["position"])
        tabs += _build_tab_item_xml(widget, list_id)
        walls += _build_wall_xml(widget, list_id, row_id, section_list_ids)
    return """
    <control type="group" id="{group_id}">
      <visible>String.IsEqual(Container(9000).ListItem.Property(menu_id),{group_id})</visible>
      <defaultcontrol>{row_id}</defaultcontrol>
      <include content="Section_Visible_Right_Delayed">
        <param name="menu_id" value="{group_id}"/>
      </include>
      <include content="HomeWallHeader">
        <param name="section_id" value="{group_id}"/>
        <param name="row_id" value="{row_id}"/>
      </include>
      <control type="fixedlist" id="{row_id}">
        <include content="HomeWallTabRow">
          <param name="row_id" value="{row_id}"/>
          <param name="walls_id" value="{walls_id}"/>
          <param name="fallback" value="![{stored_shown}]"/>
        </include>
        <content>{tabs}
        </content>
      </control>
      <control type="group" id="{walls_id}">
        <include content="HomeWallsGroup">
          <param name="walls_id" value="{walls_id}"/>
          <param name="row_id" value="{row_id}"/>
        </include>{walls}
      </control>
    </control>""".format(
        group_id=group_id,
        row_id=row_id,
        walls_id=walls_id,
        stored_shown=_stored_wall_shown(row_id, section_list_ids),
        tabs=tabs,
        walls=walls,
    )


def generate_home_walls_xml(config):
    """Generate the home screen sections as tab rows and walls.

    Hidden sections, hidden widgets and the weather section (hardcoded in
    Home.xml) are skipped, as is any section left without visible widgets.

    Args:
        config: dict from ConfigManager.get_full_config()
    Returns:
        XML string with the HomeWalls include.
    """
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<includes>\n  <include name="HomeWalls">'
    for section_id in sorted(
        config, key=lambda sid: config[sid]["section"]["position"]
    ):
        section_data = config[section_id]
        section = section_data["section"]
        if section.get("visible") == "false":
            continue
        if section["name"] == "$LOCALIZE[8]":
            continue
        widgets = [
            w for w in section_data["widgets"] if w.get("visible") != "false"
        ]
        if not widgets:
            continue
        xml += _build_wall_section_xml(section["position"], widgets)
    xml += "\n  </include>\n</includes>"
    return xml


def _build_menu_item_xml(section, group_id, submenu_list_id=None, has_walls=True):
    """Generate XML for a single main menu item.

    Each section automatically gets a visibility condition tied to its DB id,
    allowing users to show/hide sections via skin settings.
    Weather sections get special multi-onclick handling and id=weather.
    menu_id is the group ID, so SetFocus lands on the section's default
    control (its tab row), matching how weather (15000) works.
    A section without visible widgets generates no group, so its item is
    marked no_walls and Home's onright leaves focus on the menu. menu_id stays,
    since its submenu list is still tied to it.
    """
    if section["name"] == "$LOCALIZE[8]":
        xml = """
    <item>
      <label>$LOCALIZE[8]</label>
      <onclick condition="!String.IsEmpty(Weather.Plugin) + String.IsEmpty(Window(Home).Property(weather_cycling))">SetProperty(weather_cycling,true,home)</onclick>
      <onclick condition="!String.IsEmpty(Weather.Plugin) + String.IsEmpty(Window(Home).Property(weather_cycling))">ReplaceWindow(Weather)</onclick>
      <onclick condition="!String.IsEmpty(Weather.Plugin)">Notification(Weather, Cycling to next location..., 2000)</onclick>
      <onclick condition="!String.IsEmpty(Weather.Plugin)">Weather.LocationNext</onclick>
      <onclick condition="String.IsEmpty(Weather.Plugin)">ReplaceWindow(servicesettings,weather)</onclick>
      <property name="menu_id">$NUMBER[15000]</property>
      <property name="id">weather</property>
      <property name="icon">$VAR[WeatherFanartCodeIcon]</property>
    </item>"""
    else:
        icon_prop = ""
        if section.get("icon"):
            icon_prop = '\n      <property name="icon">{icon}</property>'.format(
                icon=_escape_ampersand(section["icon"])
            )
        submenu_prop = ""
        if submenu_list_id:
            submenu_prop = '\n      <property name="submenu_id">$NUMBER[{id}]</property>'.format(
                id=submenu_list_id
            )
        walls_prop = ""
        if not has_walls:
            walls_prop = '\n      <property name="no_walls">true</property>'
        xml = """
    <item>
      <label>{name}</label>
      <onclick>{onclick}</onclick>
      <property name="menu_id">$NUMBER[{menu_id}]</property>
      <property name="id">widgets</property>{icon_prop}{submenu_prop}{walls_prop}
    </item>""".format(
            name=_escape_ampersand(section["name"]),
            onclick=_escape_ampersand(section["onclick"]),
            menu_id=group_id,
            icon_prop=icon_prop,
            submenu_prop=submenu_prop,
            walls_prop=walls_prop,
        )
    return xml


def generate_main_menu_xml(config):
    """Generate the main menu include file from config.

    Args:
        config: dict from ConfigManager.get_full_config()
    Returns:
        XML string with all section menu items in a single include.
    """
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<includes>\n  <include name="MainMenuItems">'
    for section_id in sorted(
        config, key=lambda sid: config[sid]["section"]["position"]
    ):
        section_data = config[section_id]
        section = section_data["section"]
        if section.get("visible") == "false":
            continue
        group_id = _compute_group_id(section["position"])
        # Check for visible submenus
        visible_submenus = [
            s for s in section_data.get("submenus", [])
            if s.get("visible") != "false"
        ]
        submenu_list_id = (
            _compute_submenu_list_id(section["position"])
            if visible_submenus else None
        )
        has_walls = any(
            w.get("visible") != "false" for w in section_data["widgets"]
        )
        xml += _build_menu_item_xml(section, group_id, submenu_list_id, has_walls)
    xml += "\n  </include>\n</includes>"
    return xml


def generate_submenus_xml(config):
    """Generate per-section submenu list includes for the home screen.

    Each section with visible submenus gets a list at the same screen position,
    with visibility tied to Container(9000).ListItem.Property(menu_id).
    Only one submenu list is visible at a time.

    Args:
        config: dict from ConfigManager.get_full_config()
    Returns:
        XML string with the HomeSubmenus include.
    """
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<includes>\n  <include name="HomeSubmenus">'
    for section_id in sorted(
        config, key=lambda sid: config[sid]["section"]["position"]
    ):
        section_data = config[section_id]
        section = section_data["section"]
        if section.get("visible") == "false":
            continue
        if section["name"] == "$LOCALIZE[8]":
            continue
        submenus = [
            s for s in section_data.get("submenus", [])
            if s.get("visible") != "false"
        ]
        if not submenus:
            continue
        section_pos = section["position"]
        group_id = _compute_group_id(section_pos)
        submenu_list_id = _compute_submenu_list_id(section_pos)
        # Build item entries for each submenu
        items_xml = ""
        for sub in submenus:
            icon_prop = ""
            if sub.get("icon"):
                icon_prop = '\n          <property name="icon">{icon}</property>'.format(
                    icon=sub["icon"]
                )
            items_xml += """
        <item>
          <label>{label}</label>
          <onclick>{onclick}</onclick>{icon_prop}
        </item>""".format(
                label=_escape_ampersand(sub["label"]),
                onclick=_escape_ampersand(sub.get("onclick", "")),
                icon_prop=icon_prop,
            )
        xml += """
    <control type="group">
      <visible>String.IsEqual(Container(9000).ListItem.Property(menu_id),{group_id})</visible>
      <control type="list" id="{submenu_list_id}">
        <include content="SubmenuListCommon">
          <param name="list_id" value="{submenu_list_id}"/>
        </include>
        <content>{items_xml}
        </content>
      </control>
    </control>""".format(
            group_id=group_id,
            submenu_list_id=submenu_list_id,
            items_xml=items_xml,
        )
    xml += "\n  </include>\n</includes>"
    return xml


def _write_xml(file_path, content):
    """Write XML content to a skin file."""
    with xbmcvfs.File(file_path, "w") as f:
        f.write(content)


def _reload_skin():
    """Reload the skin to pick up XML changes.

    Prevents duplicate reloads and waits for addon browser dialog to close.
    """
    window = xbmcgui.Window(10000)
    if window.getProperty("altus.clear_path_refresh") == "true":
        return
    window.setProperty("altus.clear_path_refresh", "true")
    while xbmcgui.getCurrentWindowId() == 10035:
        xbmc.sleep(500)
    window.setProperty("altus.clear_path_refresh", "")
    xbmc.sleep(200)
    xbmc.executebuiltin("ReloadSkin()")


def _auto_save_profile(active_config=None):
    """Auto-save the active widget config to its profile file.

    Args:
        active_config: explicit profile name to save as. When provided
            (even as empty string), this avoids reading the skin string
            (which is set asynchronously and may still hold a stale value).
            Pass None to read from the skin string, "" to skip saving.
    """
    if active_config is not None:
        active = active_config
    else:
        active = xbmc.getInfoLabel(
            "Skin.String(altus_active_widget_config)"
        )
    if active:
        from modules.widget_manager.config_manager import save_config_as

        save_config_as(active)


def generate_and_reload(active_config=None):
    """Full rebuild: read config, generate all XML files, reload skin.

    Args:
        active_config: explicit profile name for auto-save. Pass this when
            Skin.SetString was just called and may not have taken effect yet.
    """
    cm = ConfigManager()
    config = cm.get_full_config()
    cm.close()
    home_walls_xml = generate_home_walls_xml(config)
    menu_xml = generate_main_menu_xml(config)
    submenus_xml = generate_submenus_xml(config)
    _write_xml(HOME_WALLS_XML_FILE, home_walls_xml)
    _write_xml(MAIN_MENU_XML_FILE, menu_xml)
    _write_xml(SUBMENUS_XML_FILE, submenus_xml)
    _auto_save_profile(active_config)
    _clear_shown_wall_properties(config)
    Thread(target=_reload_skin).start()


def _clear_shown_wall_properties(config):
    """Forget which wall each section shows in manual tab loading.

    Widget positions (and so list ids) can change with the rebuild, which
    would leave a section pointing at a wall that no longer exists; cleared,
    every section starts back on its first wall.
    """
    window = xbmcgui.Window(10000)
    for section_data in config.values():
        row_id = _compute_row_id(section_data["section"]["position"])
        window.clearProperty(_shown_wall_property(row_id))