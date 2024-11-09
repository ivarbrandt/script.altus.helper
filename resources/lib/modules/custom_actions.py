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
        f"[COLOR $VAR[MenuSelectorColor]]\\1[/COLOR]",
        changelog_text,
    )
    changelog_text = re.sub(
        r"\[COLOR \w+\](Version \$INFO\[.*?\])\[/COLOR\]",
        f"[COLOR $VAR[MenuSelectorColor]]\\1[/COLOR]",
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


def set_blurradius():
    current_value = xbmc.getInfoLabel("Skin.String(BlurRadius)") or "30"
    dialog = xbmcgui.Dialog()
    value = dialog.numeric(0, "Enter blur radius value", current_value)
    if value == "":
        value = "30"
    xbmc.executebuiltin(f"Skin.SetString(BlurRadius,{value})")


def set_blursaturation():
    current_value = xbmc.getInfoLabel("Skin.String(BlurSaturation)") or "1.5"
    keyboard = xbmc.Keyboard(current_value, "Enter blur saturation value")
    keyboard.doModal()
    if keyboard.isConfirmed():
        text = keyboard.getText()
        if text == "":
            text = "1.5"
        xbmc.executebuiltin(f"Skin.SetString(BlurSaturation,{text})")


def set_autoendplaybackdelay():
    current_value = xbmc.getInfoLabel("Skin.String(PlaybackDelayMins)") or "30"
    dialog = xbmcgui.Dialog()
    value_mins = dialog.numeric(0, "Enter delay in minutes", current_value)
    if value_mins == "":
        value_mins = "30"
        value_secs = 1800
    else:
        value_secs = int(value_mins) * 60
    xbmc.executebuiltin(f"Skin.SetString(PlaybackDelayMins,{value_mins})")
    xbmc.executebuiltin(f"Skin.SetString(PlaybackDelaySecs,{value_secs})")
