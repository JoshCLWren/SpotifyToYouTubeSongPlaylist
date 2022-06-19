import contextlib
import json
import os

import arrow

from http_requests import handle_request


class Song:
    """a class for a song"""

    def __init__(
        self,
        spotify_meta_data,
        spotify_cache=False,
        spotify_playlist_id=None,
        playlist_id_youtube=None,
        youtube=None,
        spotify=None,
    ):
        """initializer doc string"""
        if not spotify_cache:
            names = spotify_meta_data.track.artists
            if len(names) > 1:
                self.artist_name = f"{names[0].name} featuring {names[1].name}".replace(
                    "/", ""
                )
            else:
                self.artist_name = names[0].name.replace("/", "")
            self.track_name = spotify_meta_data.track.name.replace("/", "")
            self.album_name = spotify_meta_data.track.album.name.replace("/", "")
            self.album_image = spotify_meta_data.track.album.images[0].url
            self.album_release_date = spotify_meta_data.track.album.release_date
        else:
            self.artist_name = spotify_meta_data["artist_name"].replace("/", "")
            self.track_name = spotify_meta_data["track_name"].replace("/", "")
            self.album_name = spotify_meta_data["album_name"].replace("/", "")
            self.album_image = None
            self.album_release_date = None
        self.spotify_playlist_id = spotify_playlist_id
        self.playlist_id_youtube = playlist_id_youtube
        self.youtube = youtube
        self.spotify = spotify
        self.full_name = f"{self.track_name} - {self.artist_name}".replace("/", "")
        self.youtube_id = None

    def get_songs_spotify(self):
        """Gets the songs from a spotify playlist"""
        playlist = self.spotify.playlist_items(self.spotify_playlist_id, as_tracks=True)
        print(playlist)
        playlist = playlist["tracks"]["items"]
        print(playlist)
        with contextlib.suppress(IndexError):
            i = 0
            songIds = []
            whileLoop = True

            # Gets the song ids from the returned dictionary
            while whileLoop:
                subPlaylist = playlist[i]
                subPlaylist.pop("added_at", None)
                subPlaylist.pop("added_by", None)
                subPlaylist.pop("is_local", None)
                subPlaylist.pop("primary_color", None)
                subPlaylist = subPlaylist["track"]
                subPlaylist.pop("album", None)
                subPlaylist.pop("artists", None)
                subPlaylist.pop("available_markets", None)
                subPlaylist = subPlaylist["id"]
                print(subPlaylist)
                songIds.append(subPlaylist)
                i += 1

        for songId in songIds:
            track = self.spotify.track(songId, market=None)
            artist = track.artists
            artist = artist[0]
            print(f"{track.name} by {artist.name}")
            self.get_song_youtube(youtube_quota=None)

    # Searches the name of the song by the artist and get the first video on the lists id
    def get_song_youtube(self, youtube_quota):
        """Gets the song from youtube"""
        if youtube_id := self.check_cache():
            return youtube_id
        if youtube_quota == 0:
            print(
                "You have reached your quota for youtube searches, please try again later"
            )
            return None
        budget_approval = youtube_quota.budget(1)
        if not budget_approval:
            print(
                "Budget exceeded, please try again later. Can't get song from youtube"
            )
            return None
        request = handle_request(
            func=self.youtube.search().list,
            part="snippet",
            maxResults=1,
            q=f"({self.full_name}) ({self.album_name})",
        )
        try:
            return self._handle_response(request, youtube_quota)
        except Exception as e:
            print(e)
            return None

    def _handle_response(self, request, youtube_quota):
        response = handle_request(func=request.execute)
        youtube_quota.spend(1)
        youtube_quota.log_success(response, self.full_name)
        response = response.get("items")
        response = response[0]
        response = response.get("id")
        return response.get("videoId")

    def cache_song(self):
        """Caches the song"""
        # import pdb; pdb.set_trace()
        song_to_cache = {
            "artist_name": self.artist_name,
            "track_name": self.track_name,
            "video_id": self.youtube_id,
            "album_name": self.album_name,
            "album_image": self.album_image,
            "album_release_date": self.album_release_date,
            "spotify_playlist_id": self.spotify_playlist_id,
            "playlist_id_youtube": self.playlist_id_youtube,
            "youtube_url": f"https://www.youtube.com/watch?v={self.youtube_id}",
            "last_updated": arrow.now().isoformat(),
        }
        path = f"./song_cache/{self.artist_name}"
        path.replace("/", "")
        if not os.path.exists(path):
            os.mkdir(f"./song_cache/{self.artist_name}")
        path += f"/{self.track_name}.json"
        path.replace("/", "")
        if not os.path.exists(path):
            with open(
                f"./song_cache/{self.artist_name}/{self.track_name}.json", "w"
            ) as f:

                json.dump(song_to_cache, f)
                return song_to_cache
        else:
            # read cache and check if song is already in cache
            with open(
                f"./song_cache/{self.artist_name}/{self.track_name}.json", "r"
            ) as f:
                cache = json.load(f)
                if cache["video_id"] == self.youtube_id:
                    print(f"{self.full_name} is already in cache")
                    return cache

    def check_cache(self):
        """Checks if the song is in the cache"""
        if os.path.exists(f"./song_cache/{self.artist_name}/{self.track_name}.json"):
            with open(
                f"./song_cache/{self.artist_name}/{self.track_name}.json", "r"
            ) as f:
                cache = json.load(f)
                if cache.get("video_id") == self.youtube_id:
                    print(f"{self.full_name} is already in cache")
                    return cache.get("video_id")

        return False

    def update_song_cache(self):
        """Updates the song cache"""
        song_to_cache = {
            "artist_name": self.artist_name,
            "track_name": self.track_name,
            "video_id": self.youtube_id,
            "album_name": self.album_name,
            "album_image": self.album_image,
            "album_release_date": self.album_release_date,
            "spotify_playlist_id": self.spotify_playlist_id,
            "playlist_id_youtube": self.playlist_id_youtube,
            "youtube_url": f"https://www.youtube.com/watch?v={self.youtube_id}",
            "last_updated": arrow.now().isoformat(),
        }
        path = f"./song_cache/{self.artist_name}"
        if not os.path.exists(path):
            os.mkdir(f"./song_cache/{self.artist_name}")
        path += f"/{self.track_name}.json"
        if not os.path.exists(path):
            with open(
                f"./song_cache/{self.artist_name}/{self.track_name}.json", "w"
            ) as f:

                json.dump(song_to_cache, f)
                return song_to_cache
        else:
            # read cache and check if song is already in cache
            with open(
                f"./song_cache/{self.artist_name}/{self.track_name}.json", "r"
            ) as f:
                cache = json.load(f)
                if cache["video_id"] == self.youtube_id:
                    print(f"{self.full_name} is already in cache")
                    return cache
                else:
                    with open(
                        f"./song_cache/{self.artist_name}/{self.track_name}.json", "w"
                    ) as f:
                        json.dump(song_to_cache, f)
                        return song_to_cache
