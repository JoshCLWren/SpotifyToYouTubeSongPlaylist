import contextlib
import itertools
import json
import os

import arrow

import spotifysession


def fix_keys_of_youtube_cache():
    """Fixes the cache formating of youtube playlists"""
    with open("youtube_playlists_v1.json", "r") as f:
        cache = json.load(f)
        playlist_dict = {}
        for name, _id in cache["playlists"].items():
            playlist_dict[name] = {
                "id": _id,
                "tracks": [],
                "name": name,
                "last_modified": arrow.now().isoformat(),
            }

        cache["playlists"] = playlist_dict
        cache["last_updated"] = arrow.now().isoformat()
        with open("youtube_playlists_v2.json", "w") as f:
            json.dump(cache, f)
    return cache


def combine_spotify_and_youtube_cache():
    """Combines the spotify and YouTube cache"""
    new_cache = {
        "last_updated": arrow.now().isoformat(),
        "date_created": arrow.now().isoformat(),
        "playlists": {},
    }
    with open("spotify_playlist_cache.json", "r") as spotify:
        spotify_cache = json.load(spotify)
    with open("youtube_playlists_v1.json", "r") as f:
        youtube_cache = json.load(f)
    for playlist in spotify_cache["playlists"]:
        if playlist["name"] in youtube_cache["playlists"]:
            new_cache["playlists"][playlist["name"]] = {
                "spotify_playlist_id": playlist["id"],
                "youtube_playlist_id": youtube_cache["playlists"][playlist["name"]][
                    "id"
                ],
                "tracks": playlist["tracks"],
                "name": playlist["name"],
                "last_modified": arrow.now().isoformat(),
                "total_tracks": len(playlist["tracks"]),
            }
            for track in new_cache["playlists"][playlist["name"]]["tracks"]:
                in_youtube_playlist = (
                    track["track_name"]
                    in youtube_cache["playlists"][playlist["name"]]["tracks"]
                )
                track = _modify_song(track, playlist, in_youtube_playlist)

        else:
            new_cache["playlists"][playlist["name"]] = {
                "spotify_playlist_id": playlist["id"],
                "youtube_playlist_id": None,
                "tracks": playlist["tracks"],
                "name": playlist["name"],
                "last_modified": arrow.now().isoformat(),
                "total_tracks": len(playlist["tracks"]),
            }
            for track in new_cache["playlists"][playlist["name"]]["tracks"]:
                track = _modify_song(track, playlist, False)
    new_cache["playlists_count"] = len(new_cache["playlists"])
    with open("combined_playlists_cache.json", "w") as f:
        json.dump(new_cache, f)


# TODO Rename this here and in `combine_spotify_and_youtube_cache`
def _modify_song(track, playlist, arg2):
    track["last_modified"] = arrow.now().isoformat()

    track["spotify_id"] = (
        track["track_id"] if track["track_id"] != playlist["id"] else None
    )
    track.pop("track_id")
    track["youtube_id"] = None
    track["in_youtube_playlist"] = arg2
    return track


def correct_and_find_song_ids():
    """Finds the spotify ids for the missing ids"""
    songs_with_new_ids = []
    spotify = spotifysession.SpotifySession()
    print("Spotify session created")
    for sub_folder in os.listdir("./song_cache"):
        with contextlib.suppress(NotADirectoryError):
            for json_file in os.listdir(f"./song_cache/{sub_folder}"):
                cache_location = f"./song_cache/{sub_folder}/{json_file}"
                with open(cache_location, "r") as f:
                    song_cache = json.load(f)
                    print(
                        f"Loading cache for {song_cache['artist_name']} {song_cache['track_name']}"
                    )
                song_cache["cache_location"] = cache_location
                if song_cache.get("video_id") is None:
                    print(
                        f"***No*** video id found for {song_cache['artist_name']} {song_cache['track_name']}"
                    )
                    continue
                print(
                    f"<<<<Video id>>>> found for {song_cache['artist_name']} {song_cache['track_name']}, adding that to temp cache"
                )
                if song_cache.get("video_id") or "None" not in song_cache.get(
                    "youtube_url"
                ):
                    songs_with_new_ids.append(song_cache)

    with open("combined_playlists_cache.json", "r") as f:
        print("Loading combined cache")
        playlist_cache = json.load(f)
    spotify_tracks = []
    for playlist in playlist_cache["playlists"].values():
        print(f"Loading spotify playlist {playlist['name']}")
        spotify_playlist = spotify.spotify.playlist_items(
            playlist["spotify_playlist_id"]
        )

        for item in spotify_playlist.items:
            names = item.track.artists
            if len(names) > 1:
                artist_name = f"{names[0].name} featuring {names[1].name}".replace(
                    "/", ""
                )

            else:
                artist_name = names[0].name.replace("/", "")

            song = {
                "track_name": item.track.name.replace("/", ""),
                "spotify_id": item.track.id,
                "artist_name": artist_name,
                "album_name": item.track.album.name.replace("/", ""),
                "last_modified": arrow.now().isoformat(),
                "is_local": item.is_local,
            }
            spotify_tracks.append(song)
            print(
                f"Adding Spotify ID to temp cache for song {song['artist_name']} {song['track_name']}"
            )

    for song, spotify_track in itertools.product(songs_with_new_ids, spotify_tracks):
        if (
            song["track_name"] == spotify_track["track_name"]
            and song["artist_name"] == spotify_track["artist_name"]
        ):
            print(
                f"Adding youtube data to temp cache for song {song['artist_name']} {song['track_name']}"
            )
            spotify_track["youtube_id"] = song["video_id"] or None
            spotify_track["youtube_url"] = song["youtube_url"]

    for playlist in playlist_cache["playlists"].values():
        for spotify_track in spotify_tracks:
            for playlist_song in playlist["tracks"]:
                if (
                    playlist_song["track_name"] == spotify_track["track_name"]
                    and playlist_song["artist_name"] == spotify_track["artist_name"]
                ):
                    spotify_track["last_modified"] = arrow.now().isoformat()
                    print(
                        f"updating local cache for song {spotify_track['artist_name']} {spotify_track['track_name']}"
                    )
                    with open(
                        spotify_track.get(
                            "cache_location",
                            f"./song_cache/{spotify_track['artist_name']}/{spotify_track['track_name']}.json",
                        ),
                        "w",
                    ) as f:
                        json.dump(spotify_track, f)
        playlist_title = f"{playlist['name']}".replace("/", "")
        playlist_cache_path = f"./playlist_cache/{playlist_title}.json"

        with open(playlist_cache_path, "w") as f:
            playlist["last_modified"] = arrow.now().isoformat()
            print(f"updating local cache for playlist {playlist['name']}")
            json.dump(playlist, f)
    with open("./combined_playlists_cache.json", "w") as f:
        playlist_cache["last_updated"] = arrow.now().isoformat()
        print("updating local cache for all playlists collection")
        json.dump(playlist_cache, f)


if __name__ == "__main__":
    while True:
        selection = input(
            "Press 1 to fix the keys of the youtube cache\n"
            "Press 2 to combine the spotify and youtube cache\n"
            "Press 3 to correct and or find ids for songs\n"
            "Press Q to quit "
        )
        if selection == "1":
            fix_keys_of_youtube_cache()
        elif selection == "2":
            combine_spotify_and_youtube_cache()
        elif selection == "3":
            correct_and_find_song_ids()
        elif selection.upper() == "Q":
            exit()
        else:
            print("Invalid selection")
