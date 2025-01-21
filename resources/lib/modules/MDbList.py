import xbmc, xbmcgui, xbmcvfs
import datetime as dt
import sqlite3 as database
import time
import requests
import json
from datetime import datetime
import re
from difflib import SequenceMatcher

settings_path = xbmcvfs.translatePath(
    "special://profile/addon_data/script.altus.helper/"
)
ratings_database_path = xbmcvfs.translatePath(
    "special://profile/addon_data/script.altus.helper/ratings_cache.db"
)
IMAGE_PATH = "special://home/addons/skin.altus/resources/rating_images/"
TMDB_API_KEY = "66a9a671e472b4dc34549c067deff536"


def make_session(url="https://"):
    session = requests.Session()
    session.mount(url, requests.adapters.HTTPAdapter(pool_maxsize=100))
    return session


api_url = "https://mdblist.com/api/?apikey=%s&i=%s"
session = make_session("https://www.mdblist.com/")


class TMDbLookup:
    def __init__(self):
        self.api_key = TMDB_API_KEY
        self.base_url = "https://api.themoviedb.org/3"
        self.session = make_session("https://api.themoviedb.org/")

    def search_by_info(self, title, year_or_premiered=None, media_type="movie"):
        clean_title = title.lower().strip()
        year = None
        if year_or_premiered and str(year_or_premiered).isdigit():
            year = int(year_or_premiered)
        elif year_or_premiered:
            try:
                year = datetime.strptime(year_or_premiered, "%Y-%m-%d").year
            except (ValueError, TypeError):
                pass
        if year:
            exact_matches = self._search_tmdb(clean_title, media_type, year)
            if exact_matches:
                return self._get_best_match(exact_matches, clean_title, year)
        fuzzy_matches = self._search_tmdb(clean_title, media_type)
        if fuzzy_matches:
            return self._get_best_match(fuzzy_matches, clean_title, year)
        return None, None

    def _search_tmdb(self, title, media_type, year=None):
        params = {
            "api_key": self.api_key,
            "query": title,
            "language": "en-US",
            "page": 1,
        }
        if year:
            params["year"] = year
        url = f"{self.base_url}/search/{media_type}"
        try:
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
        except requests.RequestException as e:
            xbmc.log(f"Altus Debug: TMDb Request Error: {str(e)}", xbmc.LOGERROR)
        return []

    def _get_best_match(self, results, title, year=None):
        best_score = 0
        best_match = None
        for result in results:
            tmdb_id = str(result.get("id"))
            if not tmdb_id:
                continue
            result_title = (
                result.get("name" if "name" in result else "title", "").lower().strip()
            )
            score = SequenceMatcher(None, title, result_title).ratio()
            if year:
                try:
                    result_date = result.get(
                        (
                            "first_air_date"
                            if "first_air_date" in result
                            else "release_date"
                        ),
                        "",
                    )
                    result_year = int(result_date[:4]) if result_date else None
                    if result_year and result_year == year:
                        score += 0.3
                except (ValueError, TypeError):
                    pass
            if score > best_score:
                best_score = score
                best_match = result
        if best_match and best_score > 0.6:
            tmdb_id = str(best_match.get("id"))
            media_type = "tv" if "first_air_date" in best_match else "movie"
            imdb_id = self._get_external_ids(tmdb_id, media_type)
            return imdb_id, tmdb_id
        return None, None

    def _get_external_ids(self, tmdb_id, media_type):
        params = {"api_key": self.api_key}
        try:
            response = self.session.get(
                f"{self.base_url}/{media_type}/{tmdb_id}/external_ids", params=params
            )
            if response.status_code == 200:
                return response.json().get("imdb_id")
        except requests.RequestException:
            pass
        return None


class MDbListAPI:
    last_checked_imdb_id = None

    def __init__(self):
        self.connect_database()
        self.tmdb_lookup = TMDbLookup()

    def connect_database(self):
        if not xbmcvfs.exists(settings_path):
            xbmcvfs.mkdir(settings_path)
        self.dbcon = database.connect(ratings_database_path, timeout=60)
        self.dbcon.execute(
            """
            CREATE TABLE IF NOT EXISTS ratings (
                imdb_id TEXT,
                tmdb_id TEXT,
                ratings TEXT,
                last_updated TIMESTAMP,
                PRIMARY KEY (imdb_id, tmdb_id)
            );
            """
        )
        self.dbcon.execute(
            """
            CREATE TABLE IF NOT EXISTS id_mappings (
                title TEXT,
                year TEXT,
                media_type TEXT,
                imdb_id TEXT,
                tmdb_id TEXT,
                last_updated TIMESTAMP,
                PRIMARY KEY (title, year, media_type)
            );
            """
        )
        self.dbcur = self.dbcon.cursor()

    def datetime_workaround(self, data, str_format):
        try:
            datetime_object = dt.datetime.strptime(data, str_format)
        except:
            datetime_object = dt.datetime(*(time.strptime(data, str_format)[0:6]))
        return datetime_object

    def insert_or_update_ratings(self, primary_id, result):
        imdb_id = result.get(
            "imdbid", primary_id if primary_id.startswith("tt") else None
        )
        tmdb_id = result.get("tmdbid", primary_id if primary_id.isdigit() else None)
        if not imdb_id and not tmdb_id:
            return
        ratings_data = json.dumps(result)
        self.dbcur.execute(
            """
            INSERT OR REPLACE INTO ratings (imdb_id, tmdb_id, ratings, last_updated)
            VALUES (?, ?, ?, ?)
            """,
            (imdb_id, tmdb_id, ratings_data, dt.datetime.now()),
        )
        self.dbcon.commit()

    # def delete_all_ratings(self):
    #     self.dbcur.execute("DELETE FROM ratings")
    #     self.dbcon.commit()
    #     dialog = xbmcgui.Dialog()
    #     dialog.ok("Altus", "All ratings have been cleared from the database.")

    def delete_all_ratings(self):
        self.dbcur.execute("DROP TABLE IF EXISTS ratings")
        self.dbcon.commit()

        # Recreate the table with new schema
        self.dbcon.execute(
            """
            CREATE TABLE IF NOT EXISTS ratings (
                imdb_id TEXT,
                tmdb_id TEXT,
                ratings TEXT,
                last_updated TIMESTAMP,
                PRIMARY KEY (imdb_id, tmdb_id)
            );
            """
        )
        self.dbcon.commit()
        dialog = xbmcgui.Dialog()
        dialog.ok("Altus", "All ratings have been cleared from the database.")

    def get_cached_info(self, id_to_check):
        self.dbcur.execute(
            """
            SELECT ratings, last_updated FROM ratings 
            WHERE imdb_id=? OR tmdb_id=?
            """,
            (id_to_check, id_to_check),
        )
        entry = self.dbcur.fetchone()
        if entry:
            ratings_data, last_updated = entry
            ratings = json.loads(ratings_data)
            last_updated_date = self.datetime_workaround(
                last_updated, "%Y-%m-%d %H:%M:%S.%f"
            )
            if dt.datetime.now() - last_updated_date < dt.timedelta(days=7):
                return ratings
        return None

    def get_cached_ids(self, title, year, media_type):
        self.dbcur.execute(
            "SELECT imdb_id, tmdb_id FROM id_mappings WHERE title=? AND year=? AND media_type=?",
            (title, year, media_type),
        )
        result = self.dbcur.fetchone()
        return result if result else (None, None)

    def cache_ids(self, title, year, media_type, imdb_id, tmdb_id):
        year = "" if year is None else year
        self.dbcur.execute(
            """
            INSERT OR REPLACE INTO id_mappings 
            (title, year, media_type, imdb_id, tmdb_id, last_updated)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (title, year, media_type, imdb_id, tmdb_id),
        )
        self.dbcon.commit()

    def _clean_tv_title(self, title):
        # TODO Add other patterns
        cleaned_title = re.sub(r"\s+season\s+\d+.*$", "", title, flags=re.IGNORECASE)
        return cleaned_title.strip()

    def lookup_imdb_id(self, meta):
        title = meta.get("title")
        premiered = meta.get("premiered")
        media_type = meta.get("media_type", "movie")
        if media_type == "tv":
            title = self._clean_tv_title(title)
        year = None
        if premiered:
            if "/" in premiered:
                parts = premiered.split("/")
                year = parts[2] if len(parts) == 3 and parts[2].isdigit() else None
            else:
                year = premiered[:4] if premiered else None
        cached_imdb_id, _ = self.get_cached_ids(title, year, media_type)
        if cached_imdb_id:
            return cached_imdb_id
        found_imdb_id, found_tmdb_id = self.tmdb_lookup.search_by_info(
            title, premiered, media_type
        )
        if found_imdb_id or found_tmdb_id:
            self.cache_ids(title, year, media_type, found_imdb_id, found_tmdb_id)
        return found_imdb_id

    def fetch_info(self, meta, mdblist_api_key):
        imdb_id = meta.get("imdb_id")
        tmdb_id = meta.get("tmdb_id")
        media_type = meta.get("media_type", "movie")
        if imdb_id and imdb_id.startswith("tt"):
            cached_data = self.get_cached_info(imdb_id)
            if cached_data:
                return cached_data
            result = self.get_result(imdb_id, mdblist_api_key, media_type)
            if result:
                self.insert_or_update_ratings(imdb_id, result)
            return result
        elif tmdb_id:
            cached_data = self.get_cached_info(tmdb_id)
            if cached_data:
                return cached_data
            result = self.get_result(tmdb_id, mdblist_api_key, media_type)
            if result:
                self.insert_or_update_ratings(tmdb_id, result)
            return result
        return {}

    def get_result(self, id_with_type, api_key, media_type="movie"):
        try:
            if isinstance(id_with_type, str) and id_with_type.isdigit():
                url = f"https://mdblist.com/api/?apikey={api_key}&tm={id_with_type}&m={'show' if media_type == 'tv' else 'movie'}"
            else:
                url = api_url % (api_key, id_with_type)
            response = requests.get(url)
            if response.status_code != 200:
                return {}
            json_data = response.json()
            ratings = json_data.get("ratings", [])
            data = {}
            data["imdbid"] = json_data.get("imdbid")
            data["tmdbid"] = json_data.get("tmdbid")
            released_digital = json_data.get("released_digital")
            try:
                recent_days = int(
                    xbmc.getInfoLabel("Skin.String(altus_digital_release_window)")
                    or "3"
                )
            except ValueError:
                recent_days = 3
            if released_digital:
                try:
                    release_date = self.datetime_workaround(
                        released_digital, "%Y-%m-%d"
                    )
                    current_date = datetime.now()
                    data["digital_release_date"] = release_date.strftime("%m/%d/%Y")
                    if release_date <= current_date:
                        days_since_release = (current_date - release_date).days
                        if days_since_release <= recent_days:
                            data["digital_release_flag"] = "recently"
                        else:
                            data["digital_release_flag"] = "true"
                    else:
                        data["digital_release_flag"] = "false"
                except (ValueError, TypeError):
                    data["digital_release_flag"] = ""
                    data["digital_release_date"] = ""
            else:
                data["digital_release_flag"] = ""
                data["digital_release_date"] = ""
            score_average = json_data.get("score_average")
            if score_average is not None and score_average != 0:
                data["mdblistRating"] = str(score_average)
                data["mdblistImage"] = IMAGE_PATH + "mdblist.png"
            else:
                data["mdblistRating"] = ""
                data["mdblistImage"] = ""
            is_certified_fresh = (
                "true"
                if next(
                    (
                        i
                        for i in json_data.get("keywords", [])
                        if i["name"] == "certified-fresh"
                    ),
                    None,
                )
                else "false"
            )
            for rating in ratings:
                source = rating.get("source")
                value = rating.get("value")
                popular = rating.get("popular")
                if source == "imdb":
                    if value is not None and value != 0:
                        data["imdbRating"] = str(value)
                        data["imdbImage"] = IMAGE_PATH + "imdb.png"
                        if popular is not None:
                            data["popularRating"] = "#" + str(popular)
                            if popular <= 10:
                                data["popularImage"] = IMAGE_PATH + "purpleflame.png"
                            elif 10 < popular <= 33:
                                data["popularImage"] = IMAGE_PATH + "pinkflame.png"
                            elif 33 < popular <= 66:
                                data["popularImage"] = IMAGE_PATH + "redflame.png"
                            elif 66 < popular <= 100:
                                data["popularImage"] = IMAGE_PATH + "blueflame.png"
                            else:
                                data["popularRating"] = ""
                                data["popularImage"] = ""
                        else:
                            data["popularRating"] = ""
                            data["popularImage"] = ""
                    else:
                        data["imdbRating"] = ""
                        data["imdbImage"] = ""
                        data["popularRating"] = ""
                        data["popularImage"] = ""
                elif source == "metacritic":
                    if value is not None and value != 0:
                        data["metascore"] = str(value)
                        data["metascoreImage"] = IMAGE_PATH + "metacritic.png"
                    else:
                        data["metascore"] = ""
                        data["metascoreImage"] = ""
                elif source == "trakt":
                    if value is not None and value != 0:
                        trakt_value = 10.0 if value == 100 else value / 10.0
                        data["traktRating"] = str(trakt_value)
                        data["traktImage"] = IMAGE_PATH + "trakt.png"
                    else:
                        data["traktRating"] = ""
                        data["traktImage"] = ""
                elif source == "letterboxd":
                    if value is not None and value != 0:
                        letterboxd_value = float(value) * 2
                        data["letterboxdRating"] = str(letterboxd_value)
                        data["letterboxdImage"] = IMAGE_PATH + "letterboxd.png"
                    else:
                        data["letterboxdRating"] = ""
                        data["letterboxdImage"] = ""
                elif source == "tomatoes":
                    if value is not None and value != 0:
                        data["tomatoMeter"] = str(value)
                        if is_certified_fresh == "true":
                            data["tomatoImage"] = IMAGE_PATH + "rtcertified.png"
                        elif value > 59:
                            data["tomatoImage"] = IMAGE_PATH + "rtfresh.png"
                        else:
                            data["tomatoImage"] = IMAGE_PATH + "rtrotten.png"
                    else:
                        data["tomatoMeter"] = ""
                        data["tomatoImage"] = ""
                elif source == "tomatoesaudience":
                    if value is not None and value != 0:
                        data["tomatoUserMeter"] = str(value)
                        if value > 59:
                            data["tomatoUserImage"] = IMAGE_PATH + "popcorn.png"
                        else:
                            data["tomatoUserImage"] = IMAGE_PATH + "popcorn_spilt.png"
                    else:
                        data["tomatoUserMeter"] = ""
                        data["tomatoUserImage"] = ""
                elif source == "tmdb":
                    if value is not None and value != 0:
                        data["tmdbRating"] = str(value / 10.0)
                        data["tmdbImage"] = IMAGE_PATH + "tmdb.png"
                    else:
                        data["tmdbRating"] = ""
                        data["tmdbImage"] = ""

            trailer = json_data.get("trailer", "")
            if not trailer:
                trailer = ""
            data["trailer"] = trailer
            data["first_in_collection"] = (
                "true"
                if next(
                    (
                        i
                        for i in json_data.get("keywords", [])
                        if i["name"] == "first-in-collection"
                    ),
                    None,
                )
                else "false"
            )
            data["collection_follow_up"] = (
                "true"
                if next(
                    (
                        i
                        for i in json_data.get("keywords", [])
                        if i["name"] == "collection-follow-up"
                    ),
                    None,
                )
                else "false"
            )
            data["belongs_to_collection"] = (
                "true"
                if next(
                    (
                        i
                        for i in json_data.get("keywords", [])
                        if i["name"] == "belongs-to-collection"
                    ),
                    None,
                )
                else "false"
            )
            return data
        except requests.RequestException:
            return {}


def play_trailer():
    trailer_source = xbmc.getInfoLabel("Skin.String(TrailerSource)")
    play_url = None
    if trailer_source == "0":
        play_url = xbmc.getInfoLabel("ListItem.Trailer")
    elif trailer_source == "1":
        play_url = xbmc.getInfoLabel("Skin.String(TrailerPlaybackURL)")
    if play_url:
        xbmc.executebuiltin("Skin.SetString(TrailerPlaying, true)")
        xbmc.executebuiltin(f"PlayMedia({play_url},0,noresume)")


def check_api_key(api_key):
    api_url = "https://mdblist.com/api/"
    params = {
        "apikey": api_key,
        "i": "tt0111161",
    }
    try:
        response = requests.get(api_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return ("valid", "ratings" in data and len(data["ratings"]) > 0)
    except requests.RequestException:
        return ("error", None)


def validate_api_key(api_key, silent=True):
    if not api_key:
        xbmc.executebuiltin("Skin.Reset(valid_api_key)")
        return
    xbmc.executebuiltin("Skin.SetString(checking_api_key,true)")
    try:
        status, is_valid = check_api_key(api_key)
        if status == "valid" and is_valid:
            xbmc.executebuiltin("Skin.SetString(valid_api_key,true)")
            if not silent:
                xbmcgui.Dialog().notification(
                    "Success",
                    "Features activated",
                    xbmcgui.NOTIFICATION_INFO,
                    3000,
                )
        elif status == "valid" and not is_valid:
            xbmc.executebuiltin("Skin.Reset(valid_api_key)")
        else:
            if not silent:
                xbmcgui.Dialog().notification(
                    "Connection Error",
                    "Unable to reach MDbList",
                    xbmcgui.NOTIFICATION_INFO,
                    3000,
                )
    finally:
        xbmc.executebuiltin("Skin.Reset(checking_api_key)")


def set_api_key():
    current_key = xbmc.getInfoLabel("Skin.String(mdblist_api_key)")
    keyboard = xbmc.Keyboard(current_key, "Enter MDbList API Key")
    keyboard.doModal()
    if keyboard.isConfirmed():
        new_key = keyboard.getText()
        if not new_key:
            xbmc.executebuiltin("Skin.Reset(mdblist_api_key)")
            xbmc.executebuiltin("Skin.Reset(valid_api_key)")
        else:
            xbmc.executebuiltin(f'Skin.SetString(mdblist_api_key,"{new_key}")')
            validate_api_key(new_key, silent=False)


def check_api_key_on_load():
    api_key = xbmc.getInfoLabel("Skin.String(mdblist_api_key)")
    validate_api_key(api_key, silent=True)
