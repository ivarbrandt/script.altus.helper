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
from urllib.parse import quote

import xbmc
import xbmcgui
import xbmcvfs

from modules.search_manager.config_manager import ConfigManager


GENERATED_PATH = "special://skin/xml/script-altus-search_widgets.xml"
INCLUDE_NAME = "SearchWidgets"

BASE_LIST_ID = 3010
LIST_ID_STEP = 1   # 4-digit parents 3010..3099; stacked children "{parent}1" are 5-digit

# Resting-state values for ``altus.search.widget.<list_id>.path``.
# INITIAL_PATH (empty string) is used at service startup — Kodi treats it as
# "no source", so containers stay dormant with zero IsUpdating flash on first
# reveal of window 1121. NOOP_URL is used on mid-session input clear: a real
# (but empty) plugin fetch is required to flush stale items from a container
# that already loaded results; an empty string at that point is a no-op and
# the stale items remain.
INITIAL_PATH = ""
NOOP_URL = "plugin://script.altus.helper/?mode=noop_empty"


def widget_path_property(list_id):
    """Window(home) property name that drives a parent widget's content_path.
    live_search.py writes either NOOP_URL (resting state) or the resolved
    plugin URL (after debounced fire) to this property."""
    return "altus.search.widget.%s.path" % list_id


def iter_visible_widgets_with_ids():
    """Yield (list_id, widget_row) for every visible widget, in the same order
    and with the same id allocation that ``_build_xml`` uses. Single source of
    truth for the parent list_id mapping; consumed by both xml_generator (for
    XML emit) and live_search.py (for path-property writes)."""
    cm = ConfigManager()
    try:
        widgets = cm.get_all_widgets()
    finally:
        cm.close()
    list_id = BASE_LIST_ID
    for w in widgets:
        if not w.get("visible"):
            continue
        yield list_id, w
        list_id += LIST_ID_STEP

FILTER_GENERATED_PATH = "special://skin/xml/script-altus-search_kind_filter.xml"
FILTER_INCLUDE_NAME = "SearchKindFilter"
# Pill IDs: 9701 = "All", 9702..N = one per distinct kind in widget-position
# order. Stays well clear of keyboard range (9201..9605) and the filter-panel
# grouplist itself (9700) in Custom_1121_SearchResults.xml.
FILTER_BASE_BUTTON_ID = 9701


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


def _filter_visible_clause(kind):
    """Visibility clause for a widget given its kind. True when the filter is
    'all' / empty (no filter active) OR contains this widget's @-delimited
    kind token. Multi-select uses @Kind1@@Kind2@ concatenation. We can't use
    [Kind] brackets here because brackets inside ``String.Contains`` get
    parsed by Kodi as grouping expressions (not literal characters) and the
    contains check then never matches. ``@`` has no special meaning in Kodi
    conditions and avoids substring collisions ("Music" in "Music Videos").
    Wired into the WidgetList* defs via the ``filter_visible`` param
    (default 'true' so home widgets are unaffected)."""
    return (
        "String.IsEqual(Window(home).Property(altus.search.filter.kind),all) | "
        "String.IsEmpty(Window(home).Property(altus.search.filter.kind)) | "
        "String.Contains(Window(home).Property(altus.search.filter.kind),@%s@)"
        % kind
    )


def _widget_block(widget, list_id):
    """Render one widget into one or two <include> blocks.

    Non-stacked: a single parent include.
    Stacked: parent include + linked child include.

    Parent ``content_path`` resolves through a Window(home) property
    (``altus.search.widget.{list_id}.path``) so live_search.py can swap the
    container between a noop URL (resting / cleared state) and the real
    resolved plugin URL (active query). This drives the container directly
    to NumItems=0 on clear, eliminating the stale-flash on re-typing that
    pure visibility gating couldn't fix.
    """
    parent_path = _escape(
        "$INFO[Window(home).Property(%s)]" % widget_path_property(list_id)
    )
    label = _escape(widget["label"])
    display_type = widget["display_type"]
    target = widget["target"]
    is_stacked = bool(widget.get("is_stacked"))
    filter_clause = _escape(_filter_visible_clause(widget["kind"]))

    if not is_stacked:
        return (
            f'    <include content="{display_type}">\n'
            f'      <param name="content_path" value="{parent_path}"/>\n'
            f'      <param name="widget_header" value="{label}"/>\n'
            f'      <param name="widget_target" value="{target}"/>\n'
            f'      <param name="list_id" value="{list_id}"/>\n'
            f'      <param name="filter_visible" value="{filter_clause}"/>\n'
            f'    </include>\n'
        )

    child_id = "%s1" % list_id
    child_type = _resolve_stacked_child_type(widget.get("stacked_type"))
    parent = (
        f'    <include content="{display_type}">\n'
        f'      <param name="content_path" value="{parent_path}"/>\n'
        f'      <param name="widget_header" value="{label}"/>\n'
        f'      <param name="widget_target" value="{target}"/>\n'
        f'      <param name="list_id" value="{list_id}"/>\n'
        f'      <param name="child_id" value="{child_id}"/>\n'
        f'      <param name="filter_visible" value="{filter_clause}"/>\n'
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
        f'      <param name="filter_visible" value="{filter_clause}"/>\n'
        f'    </include>\n'
    )
    return parent + child


def _build_xml():
    """Compose the full XML document. Hidden widgets are skipped here so the
    generated file never carries dead weight."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<includes>\n',
        f'  <include name="{INCLUDE_NAME}">\n',
    ]
    for list_id, w in iter_visible_widgets_with_ids():
        parts.append(_widget_block(w, list_id))
    parts.append('  </include>\n')
    parts.append('</includes>\n')
    return "".join(parts)


def _filter_button_block(label, button_id, onclick_action, selected_condition):
    """Render one filter pill via the SearchKindFilterButton skin include.
    Styling lives in the static include; this generator just wires per-pill
    onclick + selected expressions."""
    return (
        f'    <include content="SearchKindFilterButton">\n'
        f'      <param name="control_id" value="{button_id}"/>\n'
        f'      <param name="label" value="{_escape(label)}"/>\n'
        f'      <param name="onclick_action" value="{_escape(onclick_action)}"/>\n'
        f'      <param name="selected_condition" value="{_escape(selected_condition)}"/>\n'
        f'    </include>\n'
    )


def _all_pill():
    """Special-case 'All' pill: clears the filter property to 'all' (sentinel
    meaning no filter active). Selected when prop is 'all' or empty."""
    onclick = "SetProperty(altus.search.filter.kind,all,home)"
    selected = (
        "String.IsEqual(Window(home).Property(altus.search.filter.kind),all) | "
        "String.IsEmpty(Window(home).Property(altus.search.filter.kind))"
    )
    return _filter_button_block("All", FILTER_BASE_BUTTON_ID, onclick, selected)


def _kind_pill(kind, button_id):
    """Per-kind pill: toggles bracketed kind token in the filter property via
    helper RunScript route. Selected when the bracketed token is present."""
    onclick = (
        "RunScript(script.altus.helper,mode=toggle_search_filter&kind=%s)"
        % quote(kind, safe="")
    )
    selected = (
        "String.Contains(Window(home).Property(altus.search.filter.kind),@%s@)"
        % kind
    )
    return _filter_button_block(kind, button_id, onclick, selected)


def _build_filter_xml(kinds):
    """Compose the filter-panel include. Always emits an 'All' pill first,
    followed by one pill per distinct kind in widget-position order. Multi-
    select: kind pills toggle in/out of the property; All clears it."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<includes>\n',
        f'  <include name="{FILTER_INCLUDE_NAME}">\n',
        _all_pill(),
    ]
    for i, kind in enumerate(kinds, start=1):
        parts.append(_kind_pill(kind, FILTER_BASE_BUTTON_ID + i))
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
    kinds = cm.get_distinct_visible_kinds()
    cm.close()

    xml = _build_xml()
    path = xbmcvfs.translatePath(GENERATED_PATH)
    with xbmcvfs.File(path, "w") as f:
        f.write(xml)

    filter_xml = _build_filter_xml(kinds)
    filter_path = xbmcvfs.translatePath(FILTER_GENERATED_PATH)
    with xbmcvfs.File(filter_path, "w") as f:
        f.write(filter_xml)

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
