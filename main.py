import json
import os

from playlist import Playlist
from user import User
from youtube_playlist import YoutubePlaylists

client_details = {
    "client_id": "./client_secret_YouTube.json",
    "client_secret": os.getenv("client_secret", None),
}


def __main__():
    """Main function"""

    if os.path.exists("./client_secret_YouTube.json"):
        with open("./client_secret_YouTube.json", "r") as f:
            client_details = json.load(f)
    else:
        with open("client_codes_Spotify.json", "w") as f:
            json.dump(client_details, f)

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

        playlist.place_songs_in_playlist()


if __name__ == "__main__":
    __main__()
