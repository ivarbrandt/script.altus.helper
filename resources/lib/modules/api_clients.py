# import requests
# from datetime import datetime
# from typing import Optional, Dict, Any, List, Tuple
# import xbmc
# from difflib import SequenceMatcher
# from .database import Database
# from .config import API_URLS, RATINGS_IMAGE_PATH

# class BaseAPIClient:
#     def __init__(self, base_url: str):
#         self.base_url = base_url
#         self.session = self._create_session()

#     def _create_session(self) -> requests.Session:
#         """Create and configure a requests session."""
#         session = requests.Session()
#         session.mount(self.base_url, requests.adapters.HTTPAdapter(pool_maxsize=100))
#         return session



