import json
import os

import arrow
from tekore import Spotify, request_client_token

from http_requests import handle_request
from playlist import Playlist
from song import Song


class SpotifySession:
    """The Spotify Session class"""

    def __init__(
        self,
        spotify_user_id=os.getenv("spotify_user_id", None),
        spotify_json="client_codes_Spotify.json",
    ):
        """initialize spotify User Info"""
        self.spotify_user_id = spotify_user_id
        self.spotify_json = spotify_json
        self.playlists_cache = {}
        self.spotify_playlist_ids = []
        self.playlists_cache, self.spotify_playlist_ids = self.setup_cache()

    def setup_cache(self):
        if os.path.exists("spotify_playlist_cache.json"):
            with open("spotify_playlist_cache.json") as f:
                try:
                    playlists_cache = json.load(f)
                except Exception:
                    playlists_cache = {}
                if (
                    len(playlists_cache) > 1
                    and (
                        arrow.get(playlists_cache.get("last_updated")) - arrow.now()
                    ).days
                    < 7
                ):
                    spotify_playlist_ids = [
                        playlist["id"] for playlist in playlists_cache["playlists"]
                    ]
        else:
            playlists_cache = {}
            spotify_playlist_ids = []
        return playlists_cache, spotify_playlist_ids

    @property
    def spotify_request(self):
        with open("client_codes_Spotify.json") as f:
            client_codes = json.load(f)
        request = handle_request(
            func=request_client_token,
            client_id=str(client_codes["client_id"]),
            client_secret=str(client_codes["client_secret"]),
        )
        return Spotify(request)

    @property
    def playlists(self):

        if len(self.playlists_cache) > 1:
            return self.playlists_cache
        next_page = True
        limit = 50
        offset = 0
        playlists_dict = {"playlists": []}
        while next_page:
            pl = Spotify.playlists(self.spotify_user_id, limit=limit, offset=offset)
            pl_json = json.loads(pl.json())

            if pl.offset + limit >= pl.total:
                next_page = False
            playlists_dict["playlists"].extend(pl_json["items"])
            offset += limit
        self.spotify_playlist_ids = [
            playlist["id"] for playlist in playlists_dict["playlists"]
        ]

        for pl in playlists_dict["playlists"]:
            tracks = []
            playlist = Playlist(spotify_id=pl["id"], spotify=self.spotify_request)

            for tune in playlist.tracks:
                song = Song(
                    spotify_playlist_id=pl["id"],
                    spotify=self.spotify_request,
                    spotify_meta_data=tune,
                )
                tracks.append(
                    {
                        "artist_name": song.artist_name,
                        "track_name": song.track_name,
                        "album_name": song.album_name,
                    }
                )
            pl["tracks"] = tracks

        with open("spotify_playlist_cache.json", "w") as f:
            playlists_dict["last_updated"] = arrow.now().isoformat()
            json.dump(playlists_dict, f)
        return playlists_dict
