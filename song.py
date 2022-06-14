import contextlib
import os
import json
import arrow
from http_requests import prevent_429


class Song:
    """a class for a song"""

    def __init__(
        self,
        spotify_meta_data,
        spotify_playlist_id=None,
        playlist_id_youtube=None,
        youtube=None,
        spotify=None,
    ):
        """initializer doc string"""
        names = spotify_meta_data.track.artists
        if len(names) > 1:
            self.artist_name = f"{names[0].name} featuring {names[1].name}"
        else:
            self.artist_name = names[0].name
        self.spotify_playlist_id = spotify_playlist_id
        self.playlist_id_youtube = playlist_id_youtube
        self.youtube = youtube
        self.spotify = spotify
        self.track_name = spotify_meta_data.track.name
        self.full_name = f"{self.track_name} - {self.artist_name}"
        self.video_id = None
        self.album_name = spotify_meta_data.track.album.name
        self.album_image = spotify_meta_data.track.album.images[0].url
        self.album_release_date = spotify_meta_data.track.album.release_date

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
            self.get_song_youtube(
                f"{track.name} by {artist.name}", self.youtube_playlist_id
            )

    # Searches the name of the song by the artist and get the first video on the lists id
    def get_song_youtube(self):
        """Gets the song from youtube"""
        request = prevent_429(
            func=self.youtube.search().list,
            part="snippet",
            maxResults=1,
            q=self.full_name,
        )
        response = prevent_429(func=request.execute)

        response = response.get("items")
        response = response[0]
        response = response.get("id")
        self.video_id = response.get("videoId")
        return self.video_id

    def cache_song(self):
        """Caches the song"""
        song_to_cache = {
            "artist_name": self.artist_name,
            "track_name": self.track_name,
            "video_id": self.video_id,
            "album_name": self.album_name,
            "album_image": self.album_image,
            "album_release_date": self.album_release_date,
            "spotify_playlist_id": self.spotify_playlist_id,
            "playlist_id_youtube": self.playlist_id_youtube,
            "youtube_url": f"https://www.youtube.com/watch?v={self.video_id}",
            "last_updated": arrow.now().isoformat(),
        }
        if not os.path.exists(f"./song_cache/{self.artist_name}"):
            os.mkdir(f"./song_cache/{self.artist_name}")
        if not os.path.exists(f"/song_cache/{self.artist_name}/{self.track_name}"):
            os.mkdir(f"./song_cache/{self.artist_name}/{self.track_name}.json")
        else:
            # read cache and check if song is already in cache
            with open(
                f"./song_cache/{self.artist_name}/{self.track_name}.json", "r"
            ) as f:
                cache = json.load(f)
                if cache["video_id"] == self.video_id:
                    print(f"{self.full_name} is already in cache")
                    return cache

        with open(f"./song_cache/{self.artist_name}/{self.track_name}.json", "w") as f:

            json.dump(song_to_cache, f)
            return song_to_cache
