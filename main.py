import json
import os

from playlist import Playlist
from spotifysession import SpotifySession
from youtube_playlist import YoutubePlaylists
from youtube_request import YouTubeAuthSession, YouTubeRequest, Quota


def __main__():
    """Main function"""
    if not os.path.exists("./song_cache"):
        os.mkdir("./song_cache")
    if not os.path.exists("./playlist_cache"):
        os.mkdir("./playlist_cache")

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    user = SpotifySession()

    youtube_playlists = YoutubePlaylists(youtube_session=None)
    youtube_quota = Quota()
    quota_remaining = youtube_quota.check()
    print(f"Quota remaining: {quota_remaining}")
    if quota_remaining == 0:
        print("Quota is 0. Exiting")
        return
    youtube_auth_session = YouTubeAuthSession()
    for playlist_count, spotify_playlist_id in enumerate(user.spotify_playlist_ids, start=1):
        print(f"Processing playlist {playlist_count} of {len(user.spotify_playlist_ids)}")
        playlist = Playlist(
            spotify_playlist_id,
            user.spotify,
            youtube=youtube_auth_session,
            spotify_playlists=user.playlists,
        )
        playlist.place_songs_in_playlist(youtube_quota)









if __name__ == "__main__":
    __main__()
