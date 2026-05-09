# -*- coding: utf-8 -*-
"""
In-house library search backend for Altus search widgets.

Invoked via plugin URL:
  plugin://script.altus.helper/?mode=library_search&type=<type>&query=<term>

<type> ∈ movies, tvshows, episodes, musicvideos, songs, albums, artists.
Performs a JSON-RPC title-contains query, returns directory items matching
the standard library content shape (so widget templates render normally).
"""

import json

import xbmc
import xbmcgui
import xbmcplugin


# (jsonrpc_method, content_type, mediatype, filter_field, properties)
_VIDEO_FIELDS = {
    "movies": (
        "VideoLibrary.GetMovies", "movies", "movie", "title",
        ["title", "originaltitle", "year", "genre", "plot", "plotoutline",
         "rating", "votes", "mpaa", "runtime", "studio", "country",
         "director", "writer", "premiered", "tagline", "playcount",
         "lastplayed", "art", "file", "trailer", "set"],
    ),
    "tvshows": (
        "VideoLibrary.GetTVShows", "tvshows", "tvshow", "title",
        ["title", "originaltitle", "year", "genre", "plot", "rating",
         "votes", "mpaa", "studio", "premiered", "playcount",
         "lastplayed", "art", "file", "season", "episode",
         "watchedepisodes"],
    ),
    "episodes": (
        "VideoLibrary.GetEpisodes", "episodes", "episode", "title",
        ["title", "season", "episode", "showtitle", "plot", "rating",
         "votes", "firstaired", "runtime", "playcount", "lastplayed",
         "art", "file", "writer", "director", "originaltitle"],
    ),
    "seasons": (
        # Filter on showtitle — "Search Seasons" maps to "show me seasons
        # of shows whose name matches my query." Season titles themselves
        # ("Season 1") aren't a useful search target.
        "VideoLibrary.GetSeasons", "seasons", "season", "showtitle",
        ["title", "showtitle", "season", "playcount", "episode",
         "watchedepisodes", "art", "tvshowid"],
    ),
    "musicvideos": (
        "VideoLibrary.GetMusicVideos", "musicvideos", "musicvideo", "title",
        ["title", "artist", "album", "year", "genre", "runtime",
         "rating", "art", "playcount", "lastplayed", "file", "plot",
         "studio", "track"],
    ),
}

_AUDIO_FIELDS = {
    "songs": (
        "AudioLibrary.GetSongs", "songs", "song", "title",
        ["title", "artist", "album", "track", "duration", "year",
         "genre", "playcount", "rating", "art", "file", "albumartist"],
    ),
    "albums": (
        "AudioLibrary.GetAlbums", "albums", "album", "album",
        ["title", "artist", "year", "genre", "rating", "playcount",
         "art", "albumlabel", "description", "albumartist"],
    ),
    "artists": (
        "AudioLibrary.GetArtists", "artists", "artist", "artist",
        ["instrument", "style", "mood", "born", "formed", "description",
         "genre", "died", "disbanded", "yearsactive", "art"],
    ),
}


def _jsonrpc(method, params):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
    })
    raw = xbmc.executeJSONRPC(payload)
    try:
        return json.loads(raw).get("result", {}) or {}
    except Exception:
        return {}


def _video_listitem(item, mediatype):
    li = xbmcgui.ListItem(label=item.get("label", "") or item.get("title", ""))
    if item.get("art"):
        li.setArt(item["art"])
    info = {"mediatype": mediatype}
    for k in ("title", "originaltitle", "year", "plot", "plotoutline",
              "rating", "votes", "mpaa", "genre", "studio", "country",
              "director", "writer", "premiered", "tagline", "playcount",
              "lastplayed", "trailer", "season", "episode", "showtitle",
              "firstaired", "artist", "album", "track"):
        if k in item:
            info[k] = item[k]
    if "runtime" in item:
        info["duration"] = item["runtime"]
    li.setInfo("video", info)
    li.setProperty("IsPlayable", "true")
    return li


def _song_listitem(item):
    li = xbmcgui.ListItem(label=item.get("label", "") or item.get("title", ""))
    if item.get("art"):
        li.setArt(item["art"])
    info = {"mediatype": "song"}
    for k in ("title", "artist", "album", "track", "year", "genre",
              "playcount", "rating", "albumartist"):
        if k in item:
            info[k] = item[k]
    if "duration" in item:
        info["duration"] = item["duration"]
    li.setInfo("music", info)
    li.setProperty("IsPlayable", "true")
    return li


def _album_listitem(item):
    li = xbmcgui.ListItem(label=item.get("label", "") or item.get("title", ""))
    if item.get("art"):
        li.setArt(item["art"])
    info = {"mediatype": "album"}
    for k in ("title", "artist", "year", "genre", "rating",
              "playcount", "albumlabel", "description", "albumartist"):
        if k in item:
            info[k] = item[k]
    li.setInfo("music", info)
    return li


def _artist_listitem(item):
    artist = item.get("artist", "")
    if isinstance(artist, list):
        artist = artist[0] if artist else ""
    li = xbmcgui.ListItem(label=item.get("label", "") or artist)
    if item.get("art"):
        li.setArt(item["art"])
    info = {"mediatype": "artist", "artist": artist}
    for k in ("genre", "instrument", "style", "mood", "born",
              "formed", "description", "died", "disbanded", "yearsactive"):
        if k in item:
            info[k] = item[k]
    li.setInfo("music", info)
    return li


def library_search(handle, params):
    content_type = params.get("type", "")
    query = params.get("query", "").strip()

    if not content_type or not query:
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
        return

    if content_type in _VIDEO_FIELDS:
        method, content, mediatype, filter_field, props = _VIDEO_FIELDS[content_type]
        result = _jsonrpc(method, {
            "properties": props,
            "filter": {"field": filter_field, "operator": "contains", "value": query},
            "sort": {"order": "ascending", "method": "label"},
        })
        items = result.get(content, []) or []
        xbmcplugin.setContent(handle, content)
        for it in items:
            if content_type == "seasons":
                # Seasons are folders, not playable files. Path drills into
                # the show's season listing. Compose a label that includes
                # the show name so the row is meaningful out of context.
                show = it.get("showtitle") or ""
                label = "%s - Season %s" % (show, it.get("season", "")) \
                    if show else (it.get("label") or it.get("title") or "")
                li = _video_listitem(it, mediatype)
                li.setLabel(label)
                li.setProperty("IsPlayable", "false")
                tvshow_id = it.get("tvshowid", "")
                season_num = it.get("season", "")
                path = "videodb://tvshows/titles/%s/%s/" % (tvshow_id, season_num)
                xbmcplugin.addDirectoryItem(handle, path, li, isFolder=True)
            else:
                li = _video_listitem(it, mediatype)
                xbmcplugin.addDirectoryItem(handle, it.get("file", ""), li, isFolder=False)

    elif content_type in _AUDIO_FIELDS:
        method, content, _mt, filter_field, props = _AUDIO_FIELDS[content_type]
        result = _jsonrpc(method, {
            "properties": props,
            "filter": {"field": filter_field, "operator": "contains", "value": query},
            "sort": {"order": "ascending", "method": "label"},
        })
        items = result.get(content, []) or []
        xbmcplugin.setContent(handle, content)
        for it in items:
            if content_type == "songs":
                li = _song_listitem(it)
                xbmcplugin.addDirectoryItem(handle, it.get("file", ""), li, isFolder=False)
            elif content_type == "albums":
                li = _album_listitem(it)
                path = "musicdb://albums/%s/" % it.get("albumid", "")
                xbmcplugin.addDirectoryItem(handle, path, li, isFolder=True)
            elif content_type == "artists":
                li = _artist_listitem(it)
                path = "musicdb://artists/%s/" % it.get("artistid", "")
                xbmcplugin.addDirectoryItem(handle, path, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
