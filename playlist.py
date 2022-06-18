import contextlib
import json
import os
import time
from unicodedata import name

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.errors import HttpError
from tekore import Spotify, request_client_token, scope
from http_requests import handle_request
from song import Song
import arrow


def _try_song_cache(tune):
    """Tries to get the song from the cache"""
    try:
        with open(f"song_cache/{tune['artist_name']}/{tune['track_name']}.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(e)
        return None


class Playlist:
    """A class with playlist related state properties"""

    def __init__(self, spotify_id, spotify, youtube=None, spotify_playlists=None):
        self.attempts = None
        self.spotify_id = spotify_id
        self.spotify_playlist = spotify.playlist(spotify_id)
        self.is_spotify_cached = False
        self.tracks = self._try_playlist_cache(spotify_id, spotify_playlists) or []
        self.name = self.spotify_playlist.name
        self.youtube = youtube
        self.youtube_id = None
        try:
            self.youtube_playlist_id = self._try_youtube_cache(self.name) or self.create_youtube_playlist(self.name)
        except AttributeError:
            self.youtube_playlist_id = None
        self.spotify = spotify
        self.youtube_playlist_cache = bool(self._try_youtube_cache(self.name))

    @staticmethod
    def _try_youtube_cache(title):
        """Tries to get the playlist from the cache"""
        # import pdb; pdb.set_trace()
        if os.path.exists("youtube_playlists_v1.json"):
            with open("youtube_playlists_v1.json", "r") as f:
                cache = json.load(f)
                for playlist, _id in cache.items():
                    if playlist == title:
                        return _id
        return None

    def _try_playlist_cache(self, spotify_id, spotify_playlists):
        """Tries to get the playlist from the cache"""
        # import pdb; pdb.set_trace()
        if spotify_playlists:
            for _playlist in spotify_playlists["playlists"]:
                if _playlist["id"] == spotify_id:
                    self.is_spotify_cached = True
                    return _playlist["tracks"]

    def place_songs_in_playlist(self, youtube_quota):
        """Places the songs in the playlist"""
        if youtube_quota.remaining == 0:
            print("Youtube quota exceeded")
            return
        print(f"Placing songs in {self.name}")
        for tune in self.tracks:

            try:
                print(f"Placing {tune['track_name']} by {tune['artist_name']}")
            except TypeError:
                print(f"Failed to place song: {tune}")
                continue
            cached_song = _try_song_cache(tune) or {"video_id": None}
            song = Song(
                spotify_playlist_id=self.spotify_id,
                playlist_id_youtube=self.youtube_id,
                youtube=self.youtube,
                spotify_meta_data=tune,
                spotify_cache=self.is_spotify_cached,
                spotify=self.spotify,
            )
            song.youtube_id = cached_song["video_id"] or song.get_song_youtube(youtube_quota)
            if len(cached_song) == 1:
                song.cache_song()
                print(f"{tune['track_name']} by {tune['artist_name']} cached")
            else:
                song.update_song_cache()
                print(f"cache for {tune['track_name']} by {tune['artist_name']} updated")
            # checks if the song is already in the playlist
            if song.youtube_id:
                self.tracks.append(song.youtube_id)
                budget_approval = youtube_quota.budget(1)
                if not budget_approval:
                    print("Youtube quota exceeded, can't add song to playlist")
                    return
                # check if song is already in the playlist
                if not self.is_song_in_youtube_playlist(tune):
                    request = handle_request(
                        func=self.youtube.playlistItems().insert,
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

    def cache_playlist(self):
        """Caches the playlist"""
        playlist_to_cache = {
            "name": self.name,
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

    def create_youtube_playlist(self, title, quota):
        """Creates a new playlist in youtube"""
        playlist = None
        if quota.remaining > 0:
            request = handle_request(
                func=self.youtube.playlists().insert,
                part="snippet,status",
                body={
                    "snippet": {
                        "title": title,
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
            self._update_youtube_cache()
            print(f"{title} created in youtube")
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

    def _update_youtube_cache(self):
        """Updates the cache with the new playlist"""
        if not os.path.exists("youtube_playlists_v1.json"):
            with open("youtube_playlists_v1.json", "w") as f:
                json.dump({}, f)
        with open("youtube_playlists_v1.json", "r") as f:
            cache = json.load(f)
            cache[self.name] = self.youtube_id
            cache["last_updated"] = arrow.now().isoformat()
        with open("youtube_playlists_v1.json", "w") as f:
            json.dump(cache, f)

    def is_song_in_youtube_playlist(self, tune):
        """Checks if the song is already in the playlist if"""
        if self.youtube_playlist_cache:
            with open("youtube_playlists_v1.json", "r") as f:
                cache = json.load(f)
                for song in cache["playlists"][self.name]["tracks"]:
                    if song["track_name"] == tune["track_name"] and song["artist_name"] == tune[
                        "artist_name"
                    ]:
                        return True
        return False


