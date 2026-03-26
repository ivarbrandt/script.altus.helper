# -*- coding: utf-8 -*-
"""
XML Generation Engine for the new widget management system.
Reads config from ConfigManager and generates:
  - script-altus-widgets.xml  (all widgets in one include, single grouplist)
  - script-altus-main_menu.xml (all sections as main menu items)
"""
import xbmc
import xbmcgui
import xbmcvfs
from threading import Thread

from modules.widget_manager.config_manager import ConfigManager

WIDGETS_XML_FILE = "special://skin/xml/script-altus-widgets.xml"
MAIN_MENU_XML_FILE = "special://skin/xml/script-altus-main_menu.xml"

# Base list ID for widgets. Section and widget positions create unique IDs:
#   list_id = BASE_LIST_ID + (section_position * 100) + widget_position
# Supports up to 99 widgets per section and up to ~190 sections.
BASE_LIST_ID = 19000


def _escape_ampersand(text):
    """Ensure & is escaped as &amp; for XML, but don't double-escape."""
    if "&amp;" not in text:
        return text.replace("&", "&amp;")
    return text


def _compute_list_id(section_position, widget_position):
    """Compute a unique control ID for a widget.

    Format: BASE + (section_pos * 100) + widget_pos
    e.g. section 1, widget 3 → 19000 + 100 + 3 = 19103
    """
    return BASE_LIST_ID + (section_position * 100) + widget_position


def _build_widget_xml(widget, list_id, section_visible):
    """Generate XML for a single non-stacked widget."""
    xml = """
    <include content="{display_type}">
      <param name="content_path" value="{path}"/>
      <param name="widget_header" value="{label}"/>
      <param name="widget_target" value="{target}"/>
      <param name="list_id" value="{list_id}"/>
      <param name="section_visible" value="{section_visible}"/>""".format(
        display_type=widget["display_type"],
        path=_escape_ampersand(widget["path"]),
        label=_escape_ampersand(widget["label"]),
        target=widget["target"],
        list_id=list_id,
        section_visible=section_visible,
    )
    if widget.get("sortby"):
        xml += '\n      <param name="sortby" value="%s"/>' % widget["sortby"]
    if widget.get("sortorder"):
        xml += '\n      <param name="sortorder" value="%s"/>' % widget["sortorder"]
    xml += "\n    </include>"
    return xml


def _resolve_stacked_child_type(stacked_type):
    """Resolve the child include name for a stacked widget.

    All stacked children need a 'Stacked' suffix appended to their base type.
    e.g. WidgetListSmallPoster → WidgetListSmallPosterStacked
         WidgetListSmallPosterFlix → WidgetListSmallPosterFlixStacked
    Already-suffixed types are left unchanged.
    """
    if stacked_type.endswith("Stacked"):
        return stacked_type
    return stacked_type + "Stacked"


def _build_stacked_widget_xml(widget, list_id, section_visible):
    """Generate XML for a stacked widget (parent category + child content)."""
    child_id = "%s1" % list_id
    child_type = _resolve_stacked_child_type(widget["stacked_type"])
    return """
    <include content="WidgetListCategoryStacked">
      <param name="content_path" value="{path}"/>
      <param name="widget_header" value="{label}"/>
      <param name="widget_target" value="{target}"/>
      <param name="list_id" value="{list_id}"/>
      <param name="child_id" value="{child_id}"/>
      <param name="section_visible" value="{section_visible}"/>
    </include>
    <include content="{child_type}">
      <param name="content_path" value="$INFO[Window(Home).Property(altus.{list_id}.path)]"/>
      <param name="widget_header" value="$INFO[Window(Home).Property(altus.{list_id}.label)]"/>
      <param name="widget_target" value="{target}"/>
      <param name="list_id" value="{child_id}"/>
      <param name="parent_id" value="{list_id}"/>
      <param name="section_visible" value="{section_visible}"/>
    </include>""".format(
        path=_escape_ampersand(widget["path"]),
        label=_escape_ampersand(widget["label"]),
        target=widget["target"],
        list_id=list_id,
        child_id=child_id,
        child_type=child_type,
        section_visible=section_visible,
    )


def _build_menu_item_xml(section, first_widget_list_id):
    """Generate XML for a single main menu item.

    Each section automatically gets a visibility condition tied to its DB id,
    allowing users to show/hide sections via skin settings.
    Weather sections get special multi-onclick handling and id=weather.
    """
    auto_visible = "!Skin.HasSetting(HomeMenuNoSection_%s)" % section["id"]
    if section["name"] == "Weather":
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
      <visible>{visible}</visible>
    </item>""".format(
            visible=auto_visible,
        )
    else:
        xml = """
    <item>
      <label>{name}</label>
      <onclick>{onclick}</onclick>
      <property name="menu_id">$NUMBER[{menu_id}]</property>
      <property name="id">movies</property>
      <visible>{visible}</visible>
    </item>""".format(
            name=_escape_ampersand(section["name"]),
            onclick=_escape_ampersand(section["onclick"]),
            menu_id=first_widget_list_id,
            visible=auto_visible,
        )
    return xml


def generate_widgets_xml(config):
    """Generate the single widgets include file from config.

    Args:
        config: dict from ConfigManager.get_full_config()
    Returns:
        XML string with all widgets in a single include.
    """
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<includes>\n  <include name="AllWidgets">'
    for section_id in sorted(config, key=lambda sid: config[sid]["section"]["position"]):
        section_data = config[section_id]
        section = section_data["section"]
        if section.get("visible") == "false":
            continue
        widgets = section_data["widgets"]
        if not widgets:
            continue
        # Compute section visibility condition tied to menu selection
        visible_widgets = [w for w in widgets if w.get("visible") != "false"]
        if visible_widgets:
            first_widget_list_id = _compute_list_id(section["position"], visible_widgets[0]["position"])
        else:
            first_widget_list_id = _compute_list_id(section["position"], 1)
        section_visible = "String.IsEqual(Container(9000).ListItem.Property(menu_id),%s)" % first_widget_list_id
        for widget in widgets:
            if widget.get("visible") == "false":
                continue
            list_id = _compute_list_id(section["position"], widget["position"])
            if widget["is_stacked"]:
                xml += _build_stacked_widget_xml(widget, list_id, section_visible)
            else:
                xml += _build_widget_xml(widget, list_id, section_visible)
    xml += "\n  </include>\n</includes>"
    return xml


def generate_main_menu_xml(config):
    """Generate the main menu include file from config.

    Args:
        config: dict from ConfigManager.get_full_config()
    Returns:
        XML string with all section menu items in a single include.
    """
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<includes>\n  <include name="MainMenuItems">'
    for section_id in sorted(config, key=lambda sid: config[sid]["section"]["position"]):
        section_data = config[section_id]
        section = section_data["section"]
        if section.get("visible") == "false":
            continue
        widgets = section_data["widgets"]
        # menu_id points to the first visible widget's list_id so SetFocus lands there
        visible_widgets = [w for w in widgets if w.get("visible") != "false"]
        if visible_widgets:
            first_widget_list_id = _compute_list_id(section["position"], visible_widgets[0]["position"])
        else:
            first_widget_list_id = _compute_list_id(section["position"], 1)
        xml += _build_menu_item_xml(section, first_widget_list_id)
    xml += "\n  </include>\n</includes>"
    return xml


def _write_xml(file_path, content):
    """Write XML content to a skin file."""
    with xbmcvfs.File(file_path, "w") as f:
        f.write(content)


def _files_get_directory(directory):
    """Fetch directory listing via JSON-RPC, returning plugin directories."""
    import json
    command = {
        "jsonrpc": "2.0",
        "id": "script.altus.helper",
        "method": "Files.GetDirectory",
        "params": {"directory": directory, "media": "files",
                    "properties": ["title", "file", "thumbnail"]},
    }
    try:
        response = xbmc.executeJSONRPC(json.dumps(command))
        result = json.loads(response).get("result", None)
        return [
            i for i in result.get("files")
            if i["file"].startswith("plugin://") and i["filetype"] == "directory"
        ]
    except Exception:
        return None


def _init_stacked_widgets(config):
    """Pre-load the first category for all stacked widgets.

    For each stacked widget, fetches the first item from its content path
    and sets window properties so the child list has content on startup.
    """
    window = xbmcgui.Window(10000)
    for section_id in sorted(config, key=lambda sid: config[sid]["section"]["position"]):
        section = config[section_id]["section"]
        if section.get("visible") == "false":
            continue
        for widget in config[section_id]["widgets"]:
            if not widget["is_stacked"] or widget.get("visible") == "false":
                continue
            list_id = _compute_list_id(section["position"], widget["position"])
            try:
                items = _files_get_directory(widget["path"])
                if not items:
                    continue
                first_item = items[0]
                window.setProperty("altus.%s.label" % list_id, first_item["label"])
                window.setProperty("altus.%s.path" % list_id, first_item["file"])
            except Exception:
                continue


def _reload_skin():
    """Reload the skin to pick up XML changes.

    Mirrors the old reload logic: prevents duplicate reloads, waits for
    addon browser dialog to close, and reinitializes stacked widgets.
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
    cm = ConfigManager()
    config = cm.get_full_config()
    cm.close()
    _init_stacked_widgets(config)


def generate_and_reload():
    """Full rebuild: read config, generate all XML files, reload skin."""
    cm = ConfigManager()
    config = cm.get_full_config()
    cm.close()
    widgets_xml = generate_widgets_xml(config)
    menu_xml = generate_main_menu_xml(config)
    _write_xml(WIDGETS_XML_FILE, widgets_xml)
    _write_xml(MAIN_MENU_XML_FILE, menu_xml)
    Thread(target=_reload_skin).start()
