import json
import os
import time

import arrow
from googleapiclient.errors import HttpError

from http_requests import handle_request


def get_youtube_playlists_from_cache():
    """Gets the YouTube playlists from the cache"""
    if not os.path.exists("youtube_playlists_v1.json"):
        return None
    try:
        with open("youtube_playlists_v1.json") as f:
            youtube_playlist_cache = json.load(f)
            if youtube_playlist_cache["playlist_count"] == 0:
                return {"playlist_count": 0}
            return youtube_playlist_cache
    except json.JSONDecodeError:
        return {"playlist_count": 0}


class YoutubePlaylists:
    """Class for all the users YouTube playlists"""

    def __init__(self, youtube_session=None):  # sourcery skip: identity-comprehension
        self.youtube = youtube_session
        self.time_to_wait = 1
        self.last_time_created = arrow.now().isoformat()
        self.as_dict, self.ids, self.names = self.get_youtube_playlists()

    def get_youtube_playlists(self, youtube_quota=None):
        """Gets all the users YouTube playlists"""

        # try to get the playlists from the cache
        youtube_playlists = get_youtube_playlists_from_cache()

        if (
            youtube_playlists is not None
            and len(youtube_playlists) > 0
            and youtube_playlists["playlist_count"] > 0
        ):
            return (
                youtube_playlists,
                [value for _, value in youtube_playlists.items()][:-2],
                [playlist for playlist in youtube_playlists][:-2],
            )
        if not youtube_playlists or isinstance(youtube_playlists, dict) and youtube_playlists.get("playlist_count", 0) == 0:
            youtube_playlists, _ids, _names = self._get_current_youtube(youtube_quota)
            return (
                youtube_playlists,
                _ids,
                _names,
            )

    def _get_current_youtube(self, youtube_quota):
        names = []
        ids = []
        next_page = True
        page = None
        tracks = []
        if youtube_quota == 0:
            print("Quota is 0. Exiting, no playlist will be created")
            return None, None, None
        while next_page:
            request = handle_request(
                func=self.youtube.playlists().list,
                part="snippet",
                maxResults=50,
                mine=True,
                pageToken=page,
            )
            budget_approval = youtube_quota.check(1)
            if budget_approval == 0:
                print("Budget denied. Exiting, no playlist will be created")
                return None, None, None
            response = handle_request(func=request.execute)
            if response:
                youtube_quota.spend(1)
                youtube_quota.log_success(response, response["items"])
            if response["pageInfo"]["totalResults"] > 50:
                next_page = True
                page += 1
            else:
                next_page = False
            page_results = response["items"]

            for page_result in page_results:
                names.append(page_result["snippet"]["title"])
                ids.append(page_result["id"])
        youtube_playlist_dict = {
            "playlist_count": len(names),
            "last_modified": arrow.now().isoformat(),
            "created_at": arrow.now().isoformat(),
        }
        for name, _id in names, ids:
            youtube_playlist_dict[name] = {"id": _id, "name": name, "tracks": [], "tracks_count": 0, "last_updated": arrow.now().isoformat()}
            # save the playlist names and ids to a json file
            with open("youtube_playlists_v1.json", "w") as f:
                json.dump(youtube_playlist_dict, f)
        return youtube_playlist_dict, ids, names

    def create(self, name, youtube_quota):
        """Creates a new Youtube playlist"""

        if name in self.names:
            print(f"Playlist {name} already exists")
            return self.as_dict[name]

        request = self.youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": name.title(),
                },
                "status": {"privacyStatus": "public"},
            },
        )
        budget_approval = youtube_quota.check(1)
        if budget_approval == 0:
            print("Budget denied. Exiting, no playlist will be created")
            return None

        if response := handle_request(func=request.execute):
            return self._handle_response(youtube_quota, response, name)

    def _handle_response(self, youtube_quota, response, name):
        youtube_quota.spend(1)
        self.as_dict[name] = {"id": response["id"], "name": name, "tracks": [], "tracks_count": 0, "last_updated": arrow.now().isoformat()}
        youtube_quota.log_success(response, self.as_dict[name])
        with open("youtube_playlists_v1.json", "r") as f:
            cache = json.load(f)
        if cache:
            cache["playlist_count"] += 1
            cache[name] = {"id": response["id"], "name": name, "tracks": [], "tracks_count": 0, "last_updated": arrow.now().isoformat()}
            with open("youtube_playlists_v1.json", "w") as f:
                json.dump(cache, f)
        else:
            with open("youtube_playlists_v1.json", "w") as f:
                json.dump({"last_modified": arrow.now().isoformat(), "playlist_count": 1, name: {"id": response["id"], "name": name, "tracks": [], "tracks_count": 0, "last_updated": arrow.now().isoformat()}}, f)
        return self.as_dict[name]