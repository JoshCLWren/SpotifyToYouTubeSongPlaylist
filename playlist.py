import asyncio
import contextlib
import json
import os
import time
from unicodedata import name

import aiofiles
import arrow
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.errors import HttpError
from tekore import Spotify, request_client_token, scope

from http_requests import handle_request
from song import Song


async def _try_song_cache(tune):
    """Tries to get the song from the cache"""
    try:
        async with aiofiles.open(
            f"song_cache/{tune['artist_name']}/{tune['track_name']}.json", "r"
        ) as f:
            return json.load(f)
    except Exception as e:
        print(e)
        return None


class Playlist:
    """A class with playlist related state properties"""

    def __init__(
        self,
        spotify_id,
        spotify,
        youtube_request=None,
        spotify_playlists=None,
        quota=None,
    ):
        self.attempts = None
        self.spotify_id = spotify_id
        self.is_spotify_cached = False
        self.tracks = self._try_playlist_cache(spotify_id, spotify_playlists) or []
        self.youtube_request = youtube_request
        self.youtube_id = None
        try:
            self.youtube_playlist_id = (
                self._try_youtube_cache() or self.create_youtube_playlist(quota)
            )
        except AttributeError:
            self.youtube_playlist_id = None
        self.spotify = spotify
        self.youtube_playlist_cache = bool(self._try_youtube_cache())

    @property
    async def spotify_playlist(self):
        return Spotify.playlists(self.spotify_id)

    # @property
    # async def name(self):
    #     return await self.spotify_playlist().name

    async def _try_youtube_cache(self):
        """Tries to get the playlist from the cache"""
        # import pdb; pdb.set_trace()
        if os.path.exists("youtube_playlists_v1.json"):
            async with aiofiles.open("youtube_playlists_v1.json", "r") as f:
                cache = json.load(f)
                for playlist, _id in cache.items():
                    if playlist == await self.spotify_playlist.name:
                        return _id
        return None

    async def _try_playlist_cache(self, spotify_id, spotify_playlists):
        """Tries to get the playlist from the cache"""
        # import pdb; pdb.set_trace()
        if spotify_playlists:
            for _playlist in spotify_playlists["playlists"]:
                if _playlist["id"] == spotify_id:
                    self.is_spotify_cached = True
                    return _playlist["tracks"]

    async def place_songs_in_playlist(self, youtube_quota):
        """Places the songs in the playlist"""
        if youtube_quota.remaining == 0:
            print("Youtube quota exceeded")
            return
        print(f"Placing songs in {await self.spotify_playlist.name}")

        await asyncio.gather(
            *[self.process_song(tune, youtube_quota) for tune in self.tracks]
        )

    async def process_song(self, tune, youtube_quota):
        """Processes the song"""
        try:
            print(f"Placing {tune['track_name']} by {tune['artist_name']}")
        except TypeError:
            print(f"Failed to place song: {tune}")
            return
        song = await self._handle_cache(tune, youtube_quota)
        # checks if the song is already in the playlist
        if song.youtube_id:
            self.tracks.append(song.youtube_id)
            budget_approval = youtube_quota.budget(1)
            if not budget_approval:
                print("Youtube quota exceeded, can't add song to playlist")
                return
            # check if song is already in the playlist
            if not self.is_song_in_youtube_playlist(tune):
                await self._youtube_song(song, youtube_quota)

    async def _handle_cache(self, tune, youtube_quota):
        cached_song, song = self.song_lookup(tune, youtube_quota)
        if len(cached_song) == 1:
            await song.cache_song()
            print(f"{tune['track_name']} by {tune['artist_name']} cached")
        else:
            await song.update_song_cache()
            print(f"cache for {tune['track_name']} by {tune['artist_name']} updated")
        return song

    async def _youtube_song(self, song, youtube_quota):
        request = await handle_request(
            func=self.youtube_request.discovery.playlistItems().insert,
            part="snippet",
            body={
                "snippet": {
                    "playlistId": self.youtube_playlist_id,
                    "position": 0,  # insert at the top?
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": song.youtube_id,
                    },
                }
            },
        )
        try:
            if response := await handle_request(func=request.execute):
                youtube_quota.spend(1)
                await youtube_quota.log_success(
                    response, await self.spotify_playlist.name
                )

        except googleapiclient.errors.HttpError as e:
            print(e)
            self.attempts += 1
            if self.attempts > 6 or self.attempts == 6:
                print(
                    f"{song.full_name} failed to add to playlist. The song has been skipped"
                )

    async def song_lookup(self, tune, youtube_quota):
        cached_song = await _try_song_cache(tune) or {"video_id": None}
        song = Song(
            spotify_playlist_id=self.spotify_id,
            playlist_id_youtube=self.youtube_id,
            spotify_meta_data=tune,
            spotify_cache=self.is_spotify_cached,
            spotify=self.spotify,
            youtube_request=self.youtube_request,
        )
        song.youtube_id = (
            cached_song.get("video_id")
            or await song.get_song_youtube(youtube_quota)
            or None
        )
        return cached_song, song

    async def cache_playlist(self):
        """Caches the playlist"""
        name = await self.spotify_playlist.name
        playlist_to_cache = {
            "name": name,
            "youtube_playlist_id": self.youtube_playlist_id,
            "spotify_id": self.spotify_id,
            "tracks": self.tracks,
            "last_updated": arrow.now().isoformat(),
        }
        if not os.path.exists(f"./playlist_cache/{name}"):
            os.mkdir(f"./playlist_cache/{name}")

        else:
            # read cache and check if song is already in cache
            async with aiofiles.open(f"./playlist_cache/{name}", "r") as f:
                cache = json.load(f)
                if cache["youtube_playlist_id"] == self.youtube_playlist_id:
                    print(f"{name} is already in cache")
                    return cache

        async with aiofiles.open(f"./playlist_cache/{name}", "w") as f:

            json.dump(playlist_to_cache, f)
            self.is_spotify_cached = True
            print(f"{name} cached")
            return playlist_to_cache

    async def create_youtube_playlist(self, quota):
        """Creates a new playlist in youtube"""
        playlist = None
        if quota.remaining > 0:
            request = await handle_request(
                func=self.youtube_request.discovery.playlists().insert,
                part="snippet,status",
                body={
                    "snippet": {
                        "title": await self.spotify_playlist.name,
                        "description": "Created by Spotify to Youtube",
                    },
                    "status": {"privacyStatus": "public"},
                },
            )
            budget_approval = quota.budget(1)
            if not budget_approval:
                print("Youtube quota exceeded, can't create playlist")
                return
            if playlist_request := await handle_request(func=request.execute):
                playlist = self._spend_quota(quota, playlist_request)
        else:
            print("Youtube quota exceeded, can't create playlist")
            return
        try:
            self.youtube_id = playlist["id"]
            await self._update_youtube_cache()
            print(f"{await self.spotify_playlist.name} created in youtube")
            return playlist["id"]
        except TypeError:
            return await self._log_failed_playlist()

    async def _spend_quota(self, quota, playlist):
        quota.spend(1)
        await quota.log_success(playlist, await self.spotify_playlist.name)
        self.youtube_playlist_id = playlist["id"]
        self.youtube_playlist_cache = True
        print(f"{await self.spotify_playlist.name} created")
        return playlist

    async def _log_failed_playlist(self):
        print(
            f"{await self.spotify_playlist.name} failed to create playlist. The playlist has been skipped"
        )

        return None

    async def _update_youtube_cache(self):
        """Updates the cache with the new playlist"""
        if not os.path.exists("youtube_playlists_v1.json"):
            async with aiofiles.open("youtube_playlists_v1.json", "w") as f:
                json.dump({}, f)
        async with aiofiles.open("youtube_playlists_v1.json", "r") as f:
            cache = json.load(f)
            cache[await self.spotify_playlist.name] = self.youtube_id
            cache["last_updated"] = arrow.now().isoformat()
        async with aiofiles.open("youtube_playlists_v1.json", "w") as f:
            json.dump(cache, f)

    async def is_song_in_youtube_playlist(self, tune):
        """Checks if the song is already in the playlist if"""
        if self.youtube_playlist_cache:
            async with aiofiles.open("youtube_playlists_v1.json", "r") as f:
                cache = json.load(f)
                for song in cache["playlists"][await self.spotify_playlist.name][
                    "tracks"
                ]:
                    if (
                        song["track_name"] == tune["track_name"]
                        and song["artist_name"] == tune["artist_name"]
                    ):
                        return True
        return False
