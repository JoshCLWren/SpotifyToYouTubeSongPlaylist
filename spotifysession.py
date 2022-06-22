import json
import os

import aiofiles
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

    async def setup_cache(self):
        if os.path.exists("spotify_playlist_cache.json"):
            async with aiofiles.open("spotify_playlist_cache.json") as f:
                try:
                    playlists_cache = await f.read()
                    playlists_cache = json.loads(playlists_cache)
                except Exception:
                    playlists_cache = {}
                if (
                    len(playlists_cache) > 1
                    and (
                        arrow.get(playlists_cache.get("last_updated")) - arrow.now()
                    ).days
                    < 7
                ):
                    self.playlists_cache = playlists_cache
                    self.spotify_playlist_ids = [
                        playlist["id"] for playlist in self.playlists_cache["playlists"]
                    ]
        else:
            self.playlists_cache = {}
            self.spotify_playlist_ids = []

    @property
    async def spotify(self):
        async with aiofiles.open("client_codes_Spotify.json") as f:
            client_codes = json.load(f)
        request = await handle_request(
            func=request_client_token,
            client_id=str(client_codes["client_id"]),
            client_secret=str(client_codes["client_secret"]),
        )
        return Spotify(request)

    @property
    async def playlists(self):

        if len(self.playlists_cache) > 1:
            return self.playlists_cache
        next_page = True
        limit = 50
        offset = 0
        playlists = {"playlists": []}
        while next_page:
            pl = Spotify.playlists(self.spotify_user_id, limit=limit, offset=offset)
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
                    }
                )
            pl["tracks"] = tracks

        async with aiofiles.open("spotify_playlist_cache.json", "w") as f:
            playlists["last_updated"] = arrow.now().isoformat()
            json.dump(playlists, f)
        return playlists
