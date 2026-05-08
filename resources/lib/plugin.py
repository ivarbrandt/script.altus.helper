# -*- coding: utf-8 -*-
import sys
from urllib.parse import parse_qsl

import xbmcplugin


def main():
    handle = int(sys.argv[1])
    qs = sys.argv[2]
    if qs.startswith("?"):
        qs = qs[1:]
    params = dict(parse_qsl(qs, keep_blank_values=True))
    mode = params.get("mode", "")

    if mode == "library_search":
        from modules.library_search import library_search
        return library_search(handle, params)

    xbmcplugin.endOfDirectory(handle, succeeded=False)


main()
