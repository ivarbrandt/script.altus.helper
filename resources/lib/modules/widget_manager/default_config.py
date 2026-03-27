# -*- coding: utf-8 -*-
"""
Creates default sections and widgets matching Estuary's standard home screen layout.
Called on fresh install when no existing config or migration data exists.

Display type mapping (Estuary → Altus):
  WidgetListCategories → WidgetListCategory
  WidgetListPoster     → WidgetListPoster
  WidgetListEpisodes   → WidgetListLandscape
  WidgetListSquare     → WidgetListSquare
  WidgetListPVR        → WidgetListPVR
"""
from modules.widget_manager.config_manager import ConfigManager

# Each section: (name, onclick, widgets)
# Each widget: (label, path, display_type, target, sortby, sortorder)
DEFAULT_SECTIONS = [
    {
        "name": "Movies",
        "onclick": "ActivateWindow(Videos,videodb://movies/titles/,return)",
        "widgets": [
            (
                "Categories",
                "library://video/movies/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
            (
                "In Progress",
                "special://skin/playlists/inprogress_movies.xsp",
                "WidgetListPoster",
                "videos",
                "",
                "",
            ),
            (
                "Recently Added",
                "special://skin/playlists/recent_unwatched_movies.xsp",
                "WidgetListPoster",
                "videos",
                "",
                "",
            ),
            (
                "Unwatched",
                "special://skin/playlists/unwatched_movies.xsp",
                "WidgetListPoster",
                "videos",
                "",
                "",
            ),
            (
                "Random",
                "special://skin/playlists/random_movies.xsp",
                "WidgetListPoster",
                "videos",
                "",
                "",
            ),
            (
                "Genres",
                "videodb://movies/genres/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
            (
                "Sets",
                "videodb://movies/sets/",
                "WidgetListPoster",
                "videos",
                "random",
                "",
            ),
        ],
    },
    {
        "name": "TV Shows",
        "onclick": "ActivateWindow(Videos,videodb://tvshows/titles/,return)",
        "widgets": [
            (
                "Categories",
                "library://video/tvshows/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
            (
                "In Progress",
                "videodb://inprogresstvshows/",
                "WidgetListPoster",
                "videos",
                "lastplayed",
                "descending",
            ),
            (
                "Recently Added Episodes",
                "special://skin/playlists/recent_unwatched_episodes.xsp",
                "WidgetListLandscape",
                "videos",
                "",
                "",
            ),
            (
                "Unwatched",
                "special://skin/playlists/unwatched_tvshows.xsp",
                "WidgetListPoster",
                "videos",
                "",
                "",
            ),
            (
                "Genres",
                "videodb://tvshows/genres/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
            (
                "Studios",
                "videodb://tvshows/studios/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
        ],
    },
    {
        "name": "Music",
        "onclick": "ActivateWindow(Music,root,return)",
        "widgets": [
            (
                "Categories",
                "library://music/",
                "WidgetListCategory",
                "music",
                "",
                "",
            ),
            (
                "Recently Played",
                "musicdb://recentlyplayedalbums/",
                "WidgetListSquare",
                "music",
                "",
                "",
            ),
            (
                "Recently Added",
                "musicdb://recentlyaddedalbums/",
                "WidgetListSquare",
                "music",
                "",
                "",
            ),
            (
                "Random Albums",
                "special://skin/playlists/random_albums.xsp",
                "WidgetListSquare",
                "music",
                "",
                "",
            ),
            (
                "Random Artists",
                "special://skin/playlists/random_artists.xsp",
                "WidgetListSquare",
                "music",
                "",
                "",
            ),
            (
                "Unplayed Albums",
                "special://skin/playlists/unplayed_albums.xsp",
                "WidgetListSquare",
                "music",
                "",
                "",
            ),
            (
                "Most Played",
                "special://skin/playlists/mostplayed_albums.xsp",
                "WidgetListSquare",
                "music",
                "playcount",
                "descending",
            ),
        ],
    },
    {
        "name": "Addons",
        "onclick": "ActivateWindow(AddonBrowser)",
        "widgets": [
            (
                "Categories",
                "addons://",
                "WidgetListCategory",
                "addonbrowser",
                "",
                "",
            ),
            (
                "Video Addons",
                "addons://sources/video/",
                "WidgetListSquare",
                "videos",
                "lastused",
                "descending",
            ),
            (
                "Music Addons",
                "addons://sources/audio/",
                "WidgetListSquare",
                "music",
                "lastused",
                "descending",
            ),
            (
                "Game Addons",
                "addons://sources/game/",
                "WidgetListSquare",
                "games",
                "lastused",
                "descending",
            ),
            (
                "Program Addons",
                "addons://sources/executable/",
                "WidgetListSquare",
                "programs",
                "lastused",
                "descending",
            ),
            (
                "Android Apps",
                "androidapp://sources/apps/",
                "WidgetListSquare",
                "programs",
                "lastused",
                "descending",
            ),
            (
                "Picture Addons",
                "addons://sources/image/",
                "WidgetListSquare",
                "pictures",
                "lastused",
                "descending",
            ),
        ],
    },
    {
        "name": "Videos",
        "onclick": "ActivateWindow(Videos,root)",
        "widgets": [
            (
                "Categories",
                "library://video/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
            (
                "Sources",
                "sources://video/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
            (
                "Playlists",
                "special://videoplaylists/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
        ],
    },
    {
        "name": "Live TV",
        "onclick": "ActivateWindow(TVChannels)",
        "widgets": [
            ("Categories", "pvr://tv/", "WidgetListCategory", "videos", "", ""),
            (
                "Recent Channels",
                "pvr://channels/tv/*?view=lastplayed",
                "WidgetListPVR",
                "tvchannels",
                "lastplayed",
                "descending",
            ),
            (
                "Recordings",
                "pvr://recordings/tv/active?view=flat",
                "WidgetListPVR",
                "tvrecordings",
                "date",
                "descending",
            ),
            (
                "Timers",
                "pvr://timers/tv/timers/?view=hidedisabled",
                "WidgetListPVR",
                "tvtimers",
                "date",
                "ascending",
            ),
            ("Channel Groups", "pvr://channels/tv", "WidgetListPVR", "tvguide", "", ""),
            (
                "Saved Searches",
                "pvr://search/tv/savedsearches",
                "WidgetListPVR",
                "tvsearch",
                "date",
                "descending",
            ),
            (
                "New Channels",
                "pvr://channels/tv/*?view=dateadded",
                "WidgetListPVR",
                "tvchannels",
                "dateadded",
                "descending",
            ),
        ],
    },
    {
        "name": "Radio",
        "onclick": "ActivateWindow(RadioChannels)",
        "widgets": [
            ("Categories", "pvr://radio/", "WidgetListCategory", "music", "", ""),
            (
                "Recent Channels",
                "pvr://channels/radio/*?view=lastplayed",
                "WidgetListPVR",
                "radiochannels",
                "lastplayed",
                "descending",
            ),
            (
                "Recordings",
                "pvr://recordings/radio/active?view=flat",
                "WidgetListPVR",
                "radiorecordings",
                "date",
                "descending",
            ),
            (
                "Timers",
                "pvr://timers/radio/timers/?view=hidedisabled",
                "WidgetListPVR",
                "radiotimers",
                "date",
                "ascending",
            ),
            (
                "Channel Groups",
                "pvr://channels/radio",
                "WidgetListPVR",
                "radioguide",
                "",
                "",
            ),
            (
                "Saved Searches",
                "pvr://search/radio/savedsearches",
                "WidgetListPVR",
                "radiosearch",
                "date",
                "descending",
            ),
            (
                "New Channels",
                "pvr://channels/radio/*?view=dateadded",
                "WidgetListPVR",
                "radiochannels",
                "dateadded",
                "descending",
            ),
        ],
    },
    {
        "name": "Favourites",
        "onclick": "ActivateWindow(favouritesbrowser)",
        "widgets": [
            ("Favourites", "favourites://", "WidgetListFavourites", "videos", "", ""),
        ],
    },
    {
        "name": "Weather",
        "onclick": "ActivateWindow(Weather)",
        "widgets": [],
    },
    {
        "name": "Music Videos",
        "onclick": "ActivateWindow(Videos,musicvideos,return)",
        "widgets": [
            (
                "Categories",
                "library://video/musicvideos/",
                "WidgetListCategory",
                "videos",
                "",
                "",
            ),
            (
                "Recently Added",
                "videodb://recentlyaddedmusicvideos/",
                "WidgetListLandscape",
                "videos",
                "",
                "",
            ),
            (
                "Unwatched",
                "special://skin/playlists/unwatched_musicvideos.xsp",
                "WidgetListLandscape",
                "videos",
                "",
                "",
            ),
            (
                "Random Artists",
                "special://skin/playlists/random_musicvideo_artists.xsp",
                "WidgetListSquare",
                "music",
                "",
                "",
            ),
            (
                "Random Music Videos",
                "special://skin/playlists/random_musicvideos.xsp",
                "WidgetListLandscape",
                "videos",
                "",
                "",
            ),
            (
                "Studios",
                "videodb://musicvideos/studios/",
                "WidgetListCategory",
                "music",
                "",
                "",
            ),
        ],
    },
    {
        "name": "Pictures",
        "onclick": "ActivateWindow(Pictures)",
        "widgets": [
            (
                "Sources",
                "sources://pictures/",
                "WidgetListCategory",
                "pictures",
                "",
                "",
            ),
        ],
    },
    {
        "name": "Games",
        "onclick": "ActivateWindow(Games)",
        "widgets": [
            (
                "Game Addons",
                "addons://sources/game/",
                "WidgetListSquare",
                "games",
                "lastused",
                "descending",
            ),
        ],
    },
]


def create_default_sections():
    """Populate the config DB with default sections and widgets.

    Only call when no existing config exists (fresh install, no migration).
    Returns True if sections were created.
    """
    cm = ConfigManager()
    # Check if any sections already exist
    config = cm.get_full_config()
    if config:
        cm.close()
        return False
    for section_data in DEFAULT_SECTIONS:
        section_id = cm.add_section(
            name=section_data["name"],
            onclick=section_data["onclick"],
        )
        for label, path, display_type, target, sortby, sortorder in section_data[
            "widgets"
        ]:
            cm.add_widget(
                section_id=section_id,
                path=path,
                label=label,
                display_type=display_type,
                target=target,
                sortby=sortby,
                sortorder=sortorder,
            )
    cm.close()
    return True
