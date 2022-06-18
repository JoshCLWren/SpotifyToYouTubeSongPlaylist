import json
import os

from playlist import Playlist
from user import User
from youtube_playlist import YoutubePlaylists


def __main__():
    """Main function"""
    # import pdb; pdb.set_trace()
    if not os.path.exists("./song_cache"):
        os.mkdir("./song_cache")
    if not os.path.exists("./playlist_cache"):
        os.mkdir("./playlist_cache")

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    user = User()

    youtube_playlists = YoutubePlaylists(user.youtube)

    for playlist_count, spotify_playlist_id in enumerate(user.spotify_playlist_ids, start=1):
        print(f"Processing playlist {playlist_count} of {len(user.spotify_playlist_ids)}")
        playlist = Playlist(
            spotify_playlist_id,
            user.spotify,
            youtube=user.youtube,
            youtube_playlists=youtube_playlists,
            spotify_playlists=user.playlists,
        )
        playlist.place_songs_in_playlist()



if __name__ == "__main__":
    __main__()
