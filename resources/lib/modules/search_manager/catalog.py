# -*- coding: utf-8 -*-
"""
Preset catalog for the Altus search-widget manager.

Each entry is a per-(source, kind) row that the catalog dialog can offer when
a user adds a new search widget. Entries with ``source_addon_id`` set are
filtered in the dialog by ``System.HasAddon(...)`` so users only see what they
can use right now.

Library entries point at script.altus.helper's plugin endpoint
(``mode=library_search``), which performs in-house JSON-RPC searches and
returns directory items. No external addon dependency.

Fields:
    source_addon_id  Addon ID required for this entry; None for library.
    source_label     Uppercase string used in the [BRACKET] label prefix.
    kind             User-facing category (Movies, TV Shows, People, ...).
                     Drives the Live-mode "Filter by Kind" radio at runtime
                     and the catalog grouping in the Add dialog.
    label            Default widget label, fully formed: "[SOURCE] Kind"
                     (or an override when disambiguation is needed).
    url_template     Raw Kodi-resolvable URL with $INFO[...] embedded.
    display_type     Widget include name to use for the parent list.
    target           ActivateWindow target ("videos" or "music").
    is_stacked       1 for stacked widgets, else 0.
    stacked_type     Child include base name when is_stacked=1; the XML
                     generator appends "Stacked" suffix automatically.
"""

# Kodi resolves these at directory-load time against home-window properties
# written by SPaths.search_input(). search_utils.py owns the encoding.
_Q = "$INFO[Window(home).Property(altus.search.input.encoded)]"
_Q_TRAKT = "$INFO[Window(home).Property(altus.search.input.trakt.encoded)]"

_LIB = "plugin://script.altus.helper/?mode=library_search&type=%s&query=" + _Q


def _entry(source_addon_id, source_label, kind, url_template,
           display_type="WidgetListSmallPoster", target="videos",
           is_stacked=0, stacked_type=None, label_override=None):
    label = label_override or "[%s] %s" % (source_label, kind)
    return {
        "source_addon_id": source_addon_id,
        "source_label": source_label,
        "kind": kind,
        "label": label,
        "url_template": url_template,
        "display_type": display_type,
        "target": target,
        "is_stacked": is_stacked,
        "stacked_type": stacked_type,
    }


CATALOG = [
    # --- LIBRARY -------------------------------------------------------------
    _entry(None, "LIBRARY", "Movies",
           _LIB % "movies",
           display_type="WidgetListPoster"),
    _entry(None, "LIBRARY", "TV Shows",
           _LIB % "tvshows",
           display_type="WidgetListPoster"),
    _entry(None, "LIBRARY", "Seasons",
           _LIB % "seasons",
           display_type="WidgetListPoster"),
    _entry(None, "LIBRARY", "Episodes",
           _LIB % "episodes",
           display_type="WidgetListLandscape"),
    _entry(None, "LIBRARY", "Music Videos",
           _LIB % "musicvideos",
           display_type="WidgetListLandscape"),
    _entry(None, "LIBRARY", "Songs",
           _LIB % "songs",
           display_type="WidgetListSquare", target="music"),
    _entry(None, "LIBRARY", "Albums",
           _LIB % "albums",
           display_type="WidgetListSquare", target="music"),
    _entry(None, "LIBRARY", "Artists",
           _LIB % "artists",
           display_type="WidgetListSquare", target="music"),

    # --- FEN -----------------------------------------------------------------
    _entry("plugin.video.fen", "FEN", "Movies",
           "plugin://plugin.video.fen/?mode=build_movie_list&action=tmdb_movies_search&query=" + _Q),
    _entry("plugin.video.fen", "FEN", "TV Shows",
           "plugin://plugin.video.fen/?mode=build_tvshow_list&action=tmdb_tv_search&query=" + _Q),
    _entry("plugin.video.fen", "FEN", "Collections",
           "plugin://plugin.video.fen/?mode=build_movie_list&action=tmdb_movies_search_sets&query=" + _Q),
    _entry("plugin.video.fen", "FEN", "People",
           "plugin://plugin.video.fen/?mode=person_direct.search&query=" + _Q),
    _entry("plugin.video.fen", "FEN", "Keywords (Movies)",
           "plugin://plugin.video.fen/?mode=build_movie_list&action=imdb_keywords_list_contents&list_id=" + _Q),
    _entry("plugin.video.fen", "FEN", "Keywords (TV Shows)",
           "plugin://plugin.video.fen/?mode=build_tvshow_list&action=imdb_keywords_list_contents&list_id=" + _Q),
    _entry("plugin.video.fen", "FEN", "Trakt Lists",
           "plugin://plugin.video.fen/?mode=trakt.list.search_trakt_lists&query=" + _Q_TRAKT,
           display_type="WidgetListCategoryStacked",
           is_stacked=1, stacked_type="WidgetListLandscape"),

    # --- FEN LIGHT -----------------------------------------------------------
    _entry("plugin.video.fenlight", "FEN LIGHT", "Movies",
           "plugin://plugin.video.fenlight/?mode=build_movie_list&action=tmdb_movies_search&query=" + _Q),
    _entry("plugin.video.fenlight", "FEN LIGHT", "TV Shows",
           "plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_tv_search&query=" + _Q),
    _entry("plugin.video.fenlight", "FEN LIGHT", "Anime",
           "plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_anime_search&query=" + _Q),
    _entry("plugin.video.fenlight", "FEN LIGHT", "People",
           "plugin://plugin.video.fenlight/?mode=person_direct.search&key_id=" + _Q),
    _entry("plugin.video.fenlight", "FEN LIGHT", "Keywords (Movies)",
           "plugin://plugin.video.fenlight/?mode=build_movie_list&action=tmdb_movie_keyword_results_direct&key_id=" + _Q),
    _entry("plugin.video.fenlight", "FEN LIGHT", "Keywords (TV Shows)",
           "plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_tv_keyword_results_direct&key_id=" + _Q),
    _entry("plugin.video.fenlight", "FEN LIGHT", "Trakt Lists",
           "plugin://plugin.video.fenlight/?mode=trakt.list.search_trakt_lists&query=" + _Q_TRAKT,
           display_type="WidgetListCategoryStacked",
           is_stacked=1, stacked_type="WidgetListLandscape"),

    # --- UMBRELLA ------------------------------------------------------------
    # People & Trakt Lists are split per-content; kind stays unified for the
    # filter UX, label disambiguates.
    _entry("plugin.video.umbrella", "UMBRELLA", "Movies",
           "plugin://plugin.video.umbrella/?action=movieSearchterm&name=" + _Q),
    _entry("plugin.video.umbrella", "UMBRELLA", "TV Shows",
           "plugin://plugin.video.umbrella/?action=tvSearchterm&name=" + _Q),
    _entry("plugin.video.umbrella", "UMBRELLA", "People",
           "plugin://plugin.video.umbrella/?action=actorSearchMovies&name=" + _Q,
           label_override="[UMBRELLA] People (Movies)"),
    _entry("plugin.video.umbrella", "UMBRELLA", "People",
           "plugin://plugin.video.umbrella/?action=actorSearchTV&name=" + _Q,
           label_override="[UMBRELLA] People (TV Shows)"),
    _entry("plugin.video.umbrella", "UMBRELLA", "Trakt Lists",
           "plugin://plugin.video.umbrella/?action=trakt_search_lists&media_type=movies&name=" + _Q_TRAKT,
           display_type="WidgetListCategoryStacked",
           is_stacked=1, stacked_type="WidgetListLandscape",
           label_override="[UMBRELLA] Trakt Lists (Movies)"),
    _entry("plugin.video.umbrella", "UMBRELLA", "Trakt Lists",
           "plugin://plugin.video.umbrella/?action=trakt_search_lists&media_type=tvshows&name=" + _Q_TRAKT,
           display_type="WidgetListCategoryStacked",
           is_stacked=1, stacked_type="WidgetListLandscape",
           label_override="[UMBRELLA] Trakt Lists (TV Shows)"),

    # --- POV -----------------------------------------------------------------
    _entry("plugin.video.pov", "POV", "Movies",
           "plugin://plugin.video.pov/?mode=build_movie_list&action=tmdb_movies_search&query=" + _Q),
    _entry("plugin.video.pov", "POV", "TV Shows",
           "plugin://plugin.video.pov/?mode=build_tvshow_list&action=tmdb_tv_search&query=" + _Q),
    _entry("plugin.video.pov", "POV", "Collections",
           "plugin://plugin.video.pov/?mode=build_movie_list&action=tmdb_movies_search_collections&query=" + _Q),
    _entry("plugin.video.pov", "POV", "People",
           "plugin://plugin.video.pov/?mode=get_search_term&search_type=people&query=" + _Q),
    _entry("plugin.video.pov", "POV", "Keywords (Movies)",
           "plugin://plugin.video.pov/?mode=imdb_build_keyword_results&media_type=movie&query=" + _Q),
    _entry("plugin.video.pov", "POV", "Keywords (TV Shows)",
           "plugin://plugin.video.pov/?mode=imdb_build_keyword_results&media_type=tvshow&query=" + _Q),
    _entry("plugin.video.pov", "POV", "Trakt Lists",
           "plugin://plugin.video.pov/?mode=build_trakt_list.search_trakt_lists&search_title=" + _Q_TRAKT,
           display_type="WidgetListCategoryStacked",
           is_stacked=1, stacked_type="WidgetListLandscape"),

    # --- SEREN ---------------------------------------------------------------
    _entry("plugin.video.seren", "SEREN", "Movies",
           "plugin://plugin.video.seren/?action=moviesSearchResults&actionArgs=" + _Q),
    _entry("plugin.video.seren", "SEREN", "TV Shows",
           "plugin://plugin.video.seren/?action=showsSearchResults&actionArgs=" + _Q),
]
