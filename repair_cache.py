import json

import arrow


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
                track["last_modified"] = arrow.now().isoformat()

                track["spotify_id"] = (
                    track["track_id"] if track["track_id"] != playlist["id"] else None
                )
                track.pop("track_id")
                track["youtube_id"] = None
                track["in_youtube_playlist"] = in_youtube_playlist
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
                track["last_modified"] = arrow.now().isoformat()
                track["spotify_id"] = (
                    track["track_id"] if track["track_id"] != playlist["id"] else None
                )
                track.pop("track_id")
                track["youtube_id"] = None
                track["in_youtube_playlist"] = False

    new_cache["playlists_count"] = len(new_cache["playlists"])
    with open("combined_playlists_cache.json", "w") as f:
        json.dump(new_cache, f)


if __name__ == "__main__":
    selection = input(
        "Press 1 to fix the keys of the youtube cache\n Press 2 to combine the spotify and youtube cache\n Press Q to "
        "quit "
    )
    if selection == "1":
        fix_keys_of_youtube_cache()
    elif selection == "2":
        combine_spotify_and_youtube_cache()
    elif selection.upper() == "Q":
        exit()
    else:
        print("Invalid selection")
