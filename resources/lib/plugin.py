# -*- coding: utf-8 -*-
import sys
from urllib.parse import parse_qsl

import xbmc


def main():
    xbmc.log("[script.altus.helper plugin] argv=%r" % (sys.argv,), level=xbmc.LOGINFO)

    if len(sys.argv) < 3:
        xbmc.log("[script.altus.helper plugin] unexpected argv length", level=xbmc.LOGWARNING)
        return

    handle = int(sys.argv[1])
    query = sys.argv[2][1:] if sys.argv[2].startswith("?") else sys.argv[2]
    params = dict(parse_qsl(query, keep_blank_values=True))
    action = params.get("action")
    xbmc.log("[script.altus.helper plugin] action=%r params=%r" % (action, params), level=xbmc.LOGINFO)

    if action == "channel_epg":
        from modules.pvr_epg import build_channel_epg
        build_channel_epg(handle, params.get("channelname", ""))
        return

    if action == "switch_channel":
        import json
        import xbmcgui
        import xbmcplugin
        channelid = params.get("channelid")
        if channelid:
            try:
                payload = {
                    "jsonrpc": "2.0", "id": 1, "method": "Player.Open",
                    "params": {"item": {"channelid": int(channelid)}},
                }
                xbmc.executeJSONRPC(json.dumps(payload))
            except (TypeError, ValueError):
                pass
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    xbmc.log("[script.altus.helper plugin] unknown action: %r" % action, level=xbmc.LOGWARNING)


main()
