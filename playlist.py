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

import youtube_playlist
from http_requests import handle_request
from song import Song


def _try_song_cache(tune):
    """Tries to get the song from the cache"""
    try:
        with open(
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
        self.tracks = []
        self.youtube_request = youtube_request
        self.youtube_id = None
        self.cache = None
        try:
            self.playlist = spotify.playlist(playlist_id=self.spotify_id)
            self.name = self.playlist.name
            self.youtube_playlist_cache = bool(self._is_cached())
        except AttributeError:
            self.playlist = None
            self.name = None
            self.youtube_playlist_cache = False
        if not self.youtube_id:
            self.create_youtube_playlist(quota)
        self.spotify = spotify

    def _is_cached(self):
        """Tries to get the playlist from the cache"""
        if os.path.exists(f"./playlist_cache/{self.name}.json"):
            try:
                with open(f"./playlist_cache/{self.name}.json") as f:
                    self.cache = json.load(f)
                    self.tracks = self.cache["tracks"]

                    print(f"{self.name} is cached")
                    self.youtube_id = self.cache["youtube_playlist_id"]
            except KeyError:
                print(f"{self.name} not in cache")
                return None
            except json.JSONDecodeError:
                print("Not valid json")
                return None
        else:
            print("No cache found")
            return None
        return None

    def place_songs_in_playlist(self, youtube_quota):
        """Places the songs in the playlist"""
        if youtube_quota.remaining == 0:
            print("Youtube quota exceeded")
            return
        print(f"Placing songs in {self.name}")
        for index, tune in enumerate(self.tracks):
            self.process_song(tune, youtube_quota, index)

    def process_song(self, tune, youtube_quota, index):
        """Processes the song"""
        try:
            print(f"Placing {tune['track_name']} by {tune['artist_name']}")
        except TypeError:
            print(f"Failed to place song: {tune}")
            return
        song = self._handle_cache(tune, youtube_quota)
        # checks if the song is already in the playlist
        if song.playlist_id_youtube == self.youtube_id:
            print(f"{song.full_name} already in playlist")
            return
        if song.youtube_id:
            self._update_cache(self, song, index)
            budget_approval = youtube_quota.budget(1)
            if not budget_approval:
                print("Youtube quota exceeded, can't add song to playlist")
                return
            # check if song is already in the playlist
            if not self.is_song_in_youtube_playlist(tune):
                self._youtube_song(song, youtube_quota)

    def _handle_cache(self, tune, youtube_quota):
        cached_song, song = self.song_lookup(tune, youtube_quota)
        if len(cached_song) == 1:
            song.cache_song()
            print(f"{tune['track_name']} by {tune['artist_name']} cached")
        else:
            song.update_song_cache()
            print(f"cache for {tune['track_name']} by {tune['artist_name']} updated")
        return song

    def _youtube_song(self, song, youtube_quota):
        request = handle_request(
            func=self.youtube_request.discovery.playlistItems().insert,
            part="snippet",
            body={
                "snippet": {
                    "playlistId": self.youtube_id,
                    "position": 0,  # insert at the top?
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": song.youtube_id,
                    },
                }
            },
        )
        try:
            if response := handle_request(func=request.execute):
                youtube_quota.spend(1)
                youtube_quota.log_success(response, self.name)

        except googleapiclient.errors.HttpError as e:
            print(e)
            self.attempts += 1
            if self.attempts > 6 or self.attempts == 6:
                print(
                    f"{song.full_name} failed to add to playlist. The song has been skipped"
                )

    def song_lookup(self, tune, youtube_quota):
        cached_song = _try_song_cache(tune) or {"video_id": None}
        song = Song(
            spotify_playlist_id=self.spotify_id,
            playlist_id_youtube=self.youtube_id,
            spotify_meta_data=tune,
            spotify_cache=self.is_spotify_cached,
            spotify=self.spotify,
            youtube_request=self.youtube_request,
        )
        song.youtube_id = (
            cached_song.get("video_id") or song.get_song_youtube(youtube_quota) or None
        )
        return cached_song, song

    def cache_playlist(self):
        """Caches the playlist"""
        playlist_to_cache = {
            "name": name,
            "youtube_playlist_id": self.youtube_playlist_id,
            "spotify_id": self.spotify_id,
            "tracks": self.tracks,
            "last_updated": arrow.now().isoformat(),
        }
        if not os.path.exists(f"./playlist_cache/{self.name}"):
            os.mkdir(f"./playlist_cache/{self.name}")

        else:
            # read cache and check if song is already in cache
            with open(f"./playlist_cache/{self.name}", "r") as f:
                cache = json.load(f)
                if cache["youtube_playlist_id"] == self.youtube_playlist_id:
                    print(f"{self.name} is already in cache")
                    return cache

        with open(f"./playlist_cache/{self.name}", "w") as f:

            json.dump(playlist_to_cache, f)
            self.is_spotify_cached = True
            print(f"{self.name} cached")
            return playlist_to_cache

    def create_youtube_playlist(self, quota):
        """Creates a new playlist in youtube"""
        playlist = None
        if quota.remaining > 0:
            request = handle_request(
                func=self.youtube_request.discovery.playlists().insert,
                part="snippet,status",
                body={
                    "snippet": {
                        "title": self.name,
                        "description": "Created by Spotify to Youtube",
                    },
                    "status": {"privacyStatus": "public"},
                },
            )
            budget_approval = quota.budget(1)
            if not budget_approval:
                print("Youtube quota exceeded, can't create playlist")
                return
            if playlist_request := handle_request(func=request.execute):
                playlist = self._spend_quota(quota, playlist_request)
        else:
            print("Youtube quota exceeded, can't create playlist")
            return
        try:
            self.youtube_id = playlist["id"]
            self._update_cache()
            print(f"{self.name} created in youtube")
            return playlist["id"]
        except TypeError:
            return self._log_failed_playlist()

    def _spend_quota(self, quota, playlist):
        quota.spend(1)
        quota.log_success(playlist, self.name)
        self.youtube_playlist_id = playlist["id"]
        self.youtube_playlist_cache = True
        print(f"{self.name} created")
        return playlist

    def _log_failed_playlist(self):
        print(f"{self.name} failed to create playlist. The playlist has been skipped")

        return None

    def _update_cache(self, song, index):
        """Updates the cache with the new playlist"""
        self.tracks[index]["youtube_id"] = song.youtube_id

        with open(f"./playlist_cache/{self.name}", "w") as f:
            json.dump(self.tracks, f)
            print(f"{self.name} cache updated")

    def is_song_in_youtube_playlist(self, tune):
        """Checks if the song is already in the playlist if"""
        if self.youtube_playlist_cache:
            with open("youtube_playlists_v1.json", "r") as f:
                cache = json.load(f)
                for song in cache["playlists"][f"{self.name}"]["tracks"]:
                    if (
                        song["track_name"] == tune["track_name"]
                        and song["artist_name"] == tune["artist_name"]
                    ):
                        return True
        return False
