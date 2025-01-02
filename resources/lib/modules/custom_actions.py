import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import xml.etree.ElementTree as ET
from xml.dom import minidom
from threading import Timer
import sys, re

KEYMAP_LOCATION = "special://userdata/keymaps/"
POSSIBLE_KEYMAP_NAMES = ["gen.xml", "keyboard.xml", "keymap.xml"]


def show_changelog():
    helper_addon = xbmcaddon.Addon("script.altus.helper")
    helper_version = helper_addon.getAddonInfo("version")
    skin_addon = xbmcaddon.Addon("skin.altus")
    skin_version = skin_addon.getAddonInfo("version")
    skin_name = skin_addon.getAddonInfo("name")
    changelog_path = xbmcvfs.translatePath("special://skin/altuschangelog.txt")
    with xbmcvfs.File(changelog_path) as file:
        changelog_text = file.read()
    if isinstance(changelog_text, bytes):
        changelog_text = changelog_text.decode("utf-8")
    changelog_text = re.sub(
        r"\[COLOR \w+\](Version \d+\.\d+\.\d+)\[/COLOR\]",
        f"[COLOR $VAR[FocusColorTheme]]\\1[/COLOR]",
        changelog_text,
    )
    changelog_text = re.sub(
        r"\[COLOR \w+\](Version \$INFO\[.*?\])\[/COLOR\]",
        f"[COLOR $VAR[FocusColorTheme]]\\1[/COLOR]",
        changelog_text,
    )
    helper_pattern = r"(Altus Helper: Latest: v([\d.]+)) \| Installed: v.*"
    helper_match = re.search(helper_pattern, changelog_text)
    if helper_match:
        latest_helper_version = helper_match.group(2)
        installed_part = f"Installed: v{helper_version}"
        if helper_version != latest_helper_version:
            installed_part = f"[COLOR red][B]{installed_part}[/B][/COLOR]"
            update_message = (
                "\n\n[COLOR red][B]An update is available for the Altus Helper. "
                "Please follow these instructions to update and get the latest features and ensure full continued functionality:[/B][/COLOR]"
                "\n\n1. Go to Settings [B]»[/B] System [B]»[/B] Addons tab [B]»[/B] Manage dependencies"
                "\n2. Find Altus Helper and click it"
                "\n3. Versions [B]»[/B] Click the latest version in ivarbrandt's Repository"
            )
        else:
            update_message = "\n\n[COLOR limegreen][B]Altus Helper up to date. No updates needed at this time.[/B][/COLOR]"
        new_helper_info = f"{helper_match.group(1)} | {installed_part}{update_message}"
        changelog_text = re.sub(
            helper_pattern, new_helper_info, changelog_text, count=1
        )
    header = f"CHANGELOG: {skin_name} v{skin_version}"
    dialog = xbmcgui.Dialog()
    dialog.textviewer(header, changelog_text)


def set_image():
    last_path = xbmc.getInfoLabel("Skin.String(LastImagePath)")
    image_file = xbmcgui.Dialog().browse(
        2,
        "Choose Custom Background Image",
        "network",
        ".jpg|.png|.bmp",
        False,
        False,
        last_path,
    )
    if image_file:
        xbmc.executebuiltin(f"Skin.SetString(LastImagePath,{image_file})")
        xbmc.executebuiltin(f"Skin.SetString(AltusCustomBackground,{image_file})")


# def set_widget_boundaries():
#     if len(sys.argv) >= 3:
#         list_id = sys.argv[2]
#         if len(list_id) in (4, 5, 6):
#             # Determine container ID based on list ID length
#             container_id = (
#                 f"{list_id[:2]}001" if len(list_id) in (5, 6) else f"{list_id[0]}001"
#             )

#             try:
#                 # Get the number of items in the container
#                 num_items_str = xbmc.getInfoLabel(f"Container({container_id}).NumItems")

#                 if num_items_str and num_items_str.isdigit():
#                     num_items = int(num_items_str)

#                     # Collect widget IDs
#                     widget_ids = []

#                     # Fixed patterns that don't depend on num_items
#                     fixed_patterns = [
#                         f"{list_id[:2]}900",
#                         f"{list_id[:1]}200",
#                         f"{list_id[:1]}300",
#                         f"{list_id[:1]}400",
#                         f"{list_id[:1]}500",
#                         f"{list_id[:1]}600",
#                         f"{list_id[:1]}700",
#                         f"{list_id[:1]}800",
#                         f"{list_id[:1]}900",
#                         f"{list_id[:2]}200",
#                         f"{list_id[:2]}300",
#                         f"{list_id[:2]}400",
#                         f"{list_id[:2]}500",
#                         f"{list_id[:2]}600",
#                         f"{list_id[:2]}700",
#                         f"{list_id[:2]}800",
#                     ]

#                     # Patterns that depend on num_items
#                     dynamic_patterns = [
#                         [f"{list_id[:2]}0{i}0" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}1" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}2" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}3" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}4" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}5" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}6" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}7" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}8" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}9" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}11" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}21" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}31" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}41" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}51" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}61" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}71" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}81" for i in range(1, num_items + 1)],
#                         [f"{list_id[:2]}0{i}91" for i in range(1, num_items + 1)],
#                     ]

#                     # Combine patterns
#                     all_patterns = fixed_patterns + [
#                         pattern for sublist in dynamic_patterns for pattern in sublist
#                     ]

#                     # Try to find existing controls for these patterns
#                     for pattern in set(all_patterns):  # Use set to remove duplicates
#                         try:
#                             control_id = int(pattern)
#                             control = xbmcgui.Window(10000).getControl(control_id)

#                             # Check number of items in the container
#                             container_items_str = xbmc.getInfoLabel(
#                                 f"Container({control_id}).NumItems"
#                             )

#                             if container_items_str and container_items_str.isdigit():
#                                 num_container_items = int(container_items_str)

#                                 # Only append if number of items is greater than 0
#                                 if num_container_items > 0:
#                                     widget_ids.append(pattern)
#                                     xbmc.log(
#                                         f"Found widget: {pattern} with {num_container_items} items",
#                                         2,
#                                     )
#                         except Exception:
#                             pass

#                     # Sort the widget IDs
#                     widget_ids = list(set(widget_ids))  # Remove duplicates
#                     widget_ids.sort(key=lambda x: (not x.endswith("900"), x))

#                     # Log found widget IDs
#                     xbmc.log(f"All found widget IDs: {widget_ids}", 2)

#                     # Set properties if widgets are found
#                     if len(widget_ids) > 1:
#                         xbmc.executebuiltin(
#                             f"SetProperty(FirstWidgetID,{widget_ids[0]},Home)"
#                         )
#                         xbmc.executebuiltin(
#                             f"SetProperty(LastWidgetID,{widget_ids[-1]},Home)"
#                         )

#             except Exception as e:
#                 xbmc.log(f"Error in set_widget_boundaries: {str(e)}", 2)
