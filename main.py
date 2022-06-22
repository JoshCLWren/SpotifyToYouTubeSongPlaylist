import asyncio
import json
import os

from joblib import Parallel, delayed

from playlist import Playlist
from spotifysession import SpotifySession
from youtube_playlist import YoutubePlaylists
from youtube_request import Quota, YouTubeAuthSession

loop = asyncio.get_event_loop()


async def __main__():
    """Main function"""
    if not os.path.exists("./song_cache"):
        os.mkdir("./song_cache")
    if not os.path.exists("./playlist_cache"):
        os.mkdir("./playlist_cache")

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    import pdb

    pdb.set_trace()
    spotify_session = SpotifySession()
    spotify_session.setup_cache()
    youtube_quota = Quota()
    quota_remaining = youtube_quota.check()
    print(f"Quota remaining: {quota_remaining}")
    if quota_remaining == 0:
        print("Quota is 0. Exiting")
        return

    youtube_auth_session = YouTubeAuthSession()

    await asyncio.gather(
        *[
            process_playlist(
                youtube_auth_session=youtube_auth_session,
                youtube_quota=youtube_quota,
                spotify_playlist_id=playlist_id,
                user=spotify_session,
            )
            for playlist_id in spotify_session.spotify_playlist_ids
        ]
    )


async def process_playlist(
    *, user, youtube_auth_session, youtube_quota, spotify_playlist_id
):
    playlist = Playlist(
        spotify_playlist_id,
        user.spotify_request,
        youtube_request=youtube_auth_session,
        spotify_playlists=user.playlists,
        quota=youtube_quota,
    )
    await playlist.place_songs_in_playlist(youtube_quota)


if __name__ == "__main__":
    loop.run_until_complete(__main__())
