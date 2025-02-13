import contextlib


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
        request = self.youtube.search().list(
            part="snippet", maxResults=1, q=self.full_name
        )
        response = request.execute()

        response = response.get("items")
        response = response[0]
        response = response.get("id")
        self.video_id = response.get("videoId")
        return self.video_id
