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
from http_requests import prevent_429
from song import Song
import arrow


class Playlist:
    """A class with playlist related state properties"""

    def __init__(self, spotify_id, spotify, youtube=None, youtube_playlists=None):
        self.spotify_id = spotify_id
        self.spotify_playlist = spotify.playlist(spotify_id)
        self.tracks = []
        self.name = self.spotify_playlist.name
        self.youtube = youtube
        self.youtube_id = None
        try:
            self.youtube_playlist_id = youtube_playlists.create(name=self.name)
        except AttributeError:
            self.youtube_playlist_id = None
        self.spotify = spotify

    def place_songs_in_playlist(self):
        for tune in self.tracks:

            song = Song(
                spotify_playlist_id=self.spotify_id,
                playlist_id_youtube=self.youtube_id,
                youtube=self.youtube,
                spotify_metadata=tune,
                spotify=self.spotify,
            )
            song_youtube_id = song.get_song_youtube()
            song.cache_song()
            # checks if the song is already in the playlist
            self.tracks.append(song.youtube_id)
            request = prevent_429(
                func=self.youtube.playlistItems().insert,
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": self.youtube_playlist_id,
                        "position": 0,  # insert at the top?
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": song_youtube_id,
                        },
                    }
                },
            )

            try:
                prevent_429(func=request.execute)
                self.attempts = 0

            except googleapiclient.errors.HttpError as e:
                print(e)
                self.attempts += 1
                if self.attempts > 6 or self.attempts == 6:
                    print(
                        f"{song.full_name} failed to add to playlist. The song has been skipped"
                    )
                    with open(f"{self.name}_response.txt", "w") as f1:
                        f1.write(str(song.full_name))
                        f1.write("\n")

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
            return playlist_to_cache
