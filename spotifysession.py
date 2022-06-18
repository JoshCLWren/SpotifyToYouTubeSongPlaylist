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
        """initialize User Info"""

        self.spotify_user_id = spotify_user_id
        self.spotify_json = spotify_json
        with open("client_codes_Spotify.json") as f:
            client_codes = json.load(f)
        self.app_token = handle_request(
            func=request_client_token,
            client_id=str(client_codes["client_id"]),
            client_secret=str(client_codes["client_secret"]),
        )
        self.spotify = Spotify(self.app_token)

        if os.path.exists("spotify_playlist_cache.json"):
            with open("spotify_playlist_cache.json") as f:
                try:
                    playlists = json.load(f)
                except Exception:
                    self.playlists = {}
                if (
                        len(playlists) > 1
                        and (arrow.get(playlists.get("last_updated")) - arrow.now()).days
                        < 7
                ):
                    self.playlists = playlists
                    self.spotify_playlist_ids = [
                        playlist["id"] for playlist in self.playlists["playlists"]
                    ]

        else:
            self.playlists = self._get_current_spotify()

    def _get_current_spotify(self):  # sourcery skip: dict-assign-update-to-union
        next_page = True
        limit = 50
        offset = 0
        playlists = {"playlists": []}

        while next_page:
            pl = self.spotify.playlists(
                self.spotify_user_id, limit=limit, offset=offset
            )
            pl_json = json.loads(pl.json())

            if pl.offset + limit >= pl.total:
                next_page = False
            playlists["playlists"].extend(pl_json["items"])
            offset += limit
        self.spotify_playlist_ids = [
            playlist["id"] for playlist in playlists["playlists"]
        ]

        for pl in playlists["playlists"]:
            tracks = []
            playlist = Playlist(spotify_id=pl["id"], spotify=self.spotify)

            for tune in playlist.tracks:
                song = Song(
                    spotify_playlist_id=pl["id"],
                    spotify=self.spotify,
                    spotify_meta_data=tune,
                )
                tracks.append(
                    {
                        "artist_name": song.artist_name,
                        "track_name": song.track_name,
                        "album_name": song.album_name,
                        "track_id": pl["id"],
                    }
                )
            pl["tracks"] = tracks

        with open("spotify_playlist_cache.json", "w") as f:
            playlists["last_updated"] = arrow.now().isoformat()
            json.dump(playlists, f)
        return playlists
