# -*- coding: utf-8 -*-
import xbmc, xbmcgui


def open_channel_guide():
    target = (xbmc.getLocalizedString(19686) or "").strip()
    if not target:
        return
    home = xbmcgui.Window(10000)
    home.setProperty("altus.pvr.hiding_ctx", "true")
    try:
        monitor = xbmc.Monitor()
        xbmc.executebuiltin("Action(ContextMenu)")
        for _ in range(40):
            if xbmc.getCondVisibility("Window.IsVisible(contextmenu)"):
                break
            if monitor.waitForAbort(0.02):
                return
        else:
            return
        prev = None
        for _ in range(60):
            label = (xbmc.getInfoLabel("System.CurrentControl") or "").strip()
            if label and label == target:
                xbmc.executebuiltin("Action(Select)")
                return
            if label and label == prev:
                break
            prev = label
            xbmc.executebuiltin("Action(Down)")
            if monitor.waitForAbort(0.030):
                return
        xbmc.executebuiltin("Action(Close)")
    finally:
        xbmc.sleep(300)
        home.clearProperty("altus.pvr.hiding_ctx")
