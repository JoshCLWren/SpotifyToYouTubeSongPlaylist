import json
import os

from playlist import Playlist
from user import User
from youtube_playlist import YoutubePlaylists


def __main__():
    """Main function"""

    if not os.path.exists("./song_cache"):
        os.mkdir("./song_cache")
    if not os.path.exists("./playlist_cache"):
        os.mkdir("./playlist_cache")

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    user = User()

    youtube_playlists = YoutubePlaylists(user.youtube)

    for spotify_playlist_id in user.spotify_playlist_ids:
        playlist = Playlist(
            spotify_playlist_id,
            user.spotify,
            youtube=user.youtube,
            youtube_playlists=youtube_playlists,
        )
        try:
            playlist.place_songs_in_playlist()
        except Exception as e:
            print(e)
            continue


if __name__ == "__main__":
    __main__()
