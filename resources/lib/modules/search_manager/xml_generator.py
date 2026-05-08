# -*- coding: utf-8 -*-
"""
XML generator for search widgets.

Reads ``search_config.db`` via ``ConfigManager`` and writes
``script-altus-search_widgets.xml`` into the skin's xml/ directory. The file
contains a single ``<include name="SearchWidgets">`` with one or two
``<include content="...">`` blocks per visible widget (one for non-stacked,
parent + child for stacked).

list_id allocation
------------------
Parents:        3010, 3011, 3012, ... 3099 (4-digit, 90 slots)
Stacked child:  ``"{parent}1"`` → 30101, 30111, 30121, ... (5-digit)

Children never collide with parents (different digit counts) and parents
never collide with each other. 90 parent slots is far above realistic
search-widget counts.

URL handling
------------
``url_template`` in the DB is the raw Kodi-resolvable URL with literal ``&``
separators and embedded ``$INFO[...]`` for the query property. This generator
XML-escapes ``&`` → ``&amp;`` when emitting into skin XML — bare ``&`` in
``content_path`` parses as malformed and the directory load fails silently
(confirmed during P1 smoke testing).

Stacked widgets
---------------
Parent gets ``content_path = url_template`` and ``child_id = "{list_id}1"``.
Child gets ``content_path = $INFO[Window(1121).Property(altus.{list_id}.path)]``
and ``widget_header = $INFO[Window(1121).Property(altus.{list_id}.label)]`` —
matching the existing pattern in ``Includes_Search.xml``. The shared
``widget_monitor`` (``script.altus.helper/resources/lib/modules/widget_utils.py``)
populates these properties when the parent list's focus changes; no
search-specific init is needed.
"""

import xml.sax.saxutils as saxutils

import xbmc
import xbmcgui
import xbmcvfs

from modules.search_manager.config_manager import ConfigManager


GENERATED_PATH = "special://skin/xml/script-altus-search_widgets.xml"
INCLUDE_NAME = "SearchWidgets"

BASE_LIST_ID = 3010
LIST_ID_STEP = 1   # 4-digit parents 3010..3099; stacked children "{parent}1" are 5-digit


def _escape(value):
    """XML-escape an attribute value (handles &, <, >, ", ')."""
    if value is None:
        return ""
    return saxutils.escape(str(value), {'"': "&quot;", "'": "&apos;"})


def _resolve_stacked_child_type(base_type):
    """Append 'Stacked' suffix unless the type already ends with it."""
    if not base_type:
        return None
    return base_type if base_type.endswith("Stacked") else base_type + "Stacked"


def _widget_block(widget, list_id):
    """Render one widget into one or two <include> blocks.

    Non-stacked: a single parent include.
    Stacked: parent include + linked child include.
    """
    url = _escape(widget["url_template"])
    label = _escape(widget["label"])
    display_type = widget["display_type"]
    target = widget["target"]
    is_stacked = bool(widget.get("is_stacked"))

    if not is_stacked:
        return (
            f'    <include content="{display_type}">\n'
            f'      <param name="content_path" value="{url}"/>\n'
            f'      <param name="widget_header" value="{label}"/>\n'
            f'      <param name="widget_target" value="{target}"/>\n'
            f'      <param name="list_id" value="{list_id}"/>\n'
            f'    </include>\n'
        )

    child_id = "%s1" % list_id
    child_type = _resolve_stacked_child_type(widget.get("stacked_type"))
    parent = (
        f'    <include content="{display_type}">\n'
        f'      <param name="content_path" value="{url}"/>\n'
        f'      <param name="widget_header" value="{label}"/>\n'
        f'      <param name="widget_target" value="{target}"/>\n'
        f'      <param name="list_id" value="{list_id}"/>\n'
        f'      <param name="child_id" value="{child_id}"/>\n'
        f'    </include>\n'
    )
    if not child_type:
        return parent
    child_path = _escape(f"$INFO[Window(1121).Property(altus.{list_id}.path)]")
    child_label = _escape(f"$INFO[Window(1121).Property(altus.{list_id}.label)]")
    child = (
        f'    <include content="{child_type}">\n'
        f'      <param name="content_path" value="{child_path}"/>\n'
        f'      <param name="widget_header" value="{child_label}"/>\n'
        f'      <param name="widget_target" value="{target}"/>\n'
        f'      <param name="list_id" value="{child_id}"/>\n'
        f'      <param name="parent_id" value="{list_id}"/>\n'
        f'    </include>\n'
    )
    return parent + child


def _build_xml(widgets):
    """Compose the full XML document. Hidden widgets are skipped here so the
    generated file never carries dead weight."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<includes>\n',
        f'  <include name="{INCLUDE_NAME}">\n',
    ]
    list_id = BASE_LIST_ID
    for w in widgets:
        if not w.get("visible"):
            continue
        parts.append(_widget_block(w, list_id))
        list_id += LIST_ID_STEP
    parts.append('  </include>\n')
    parts.append('</includes>\n')
    return "".join(parts)


def generate_and_reload(active_config=None, reload_skin=True):
    """Read DB → render XML → write to skin/xml/ → reload skin.

    Args:
        active_config: reserved for P10 profile support; passed through to
            avoid the async ``Skin.SetString`` race that auto-save would hit
            otherwise. Currently unused.
        reload_skin: set False from tests/scripts that just want the file
            written without a skin reload.

    Returns:
        Number of visible widgets emitted.
    """
    cm = ConfigManager()
    widgets = cm.get_all_widgets()
    cm.close()

    xml = _build_xml(widgets)
    path = xbmcvfs.translatePath(GENERATED_PATH)
    with xbmcvfs.File(path, "w") as f:
        f.write(xml)

    if reload_skin:
        # Defer the actual reload until the user has left the addon-browser /
        # skin-settings parent window (10035). Reloading while that window is
        # still up tears it down mid-animation. Mirrors widget-manager's
        # _reload_skin pattern.
        while xbmcgui.getCurrentWindowId() == 10035:
            xbmc.sleep(500)
        xbmc.executebuiltin("ReloadSkin()")

    visible_count = sum(1 for w in widgets if w.get("visible"))
    return visible_count
