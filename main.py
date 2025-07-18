import os
import json
from datetime import datetime, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth

DESC = "Auto-created by Liked Songs Manager"
GENRE_PLAYLIST_NAME = "All Liked Songs by Genre"
RECENT_50_NAME = "Recent 50 Liked Songs"

def get_spotify():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope="user-library-read playlist-modify-private user-library-read"
    ))

def get_liked_songs(sp, limit=5000):
    liked = []
    offset = 0
    while True:
        results = sp.current_user_saved_tracks(limit=50, offset=offset)
        items = results['items']
        if not items:
            break
        liked.extend(items)
        offset += 50
        if len(liked) >= limit:
            break
    return liked

def create_or_replace_playlist(sp, user_id, name, track_ids):
    existing = sp.current_user_playlists(limit=50)["items"]
    playlist = next((pl for pl in existing if pl["name"] == name), None)

    if playlist:
        sp.playlist_replace_items(playlist_id=playlist["id"], items=track_ids)
        print(f"🔁 Updated: {name}")
    else:
        playlist = sp.user_playlist_create(user=user_id, name=name, public=False, description=DESC)
        sp.playlist_add_items(playlist["id"], items=track_ids)
        print(f"✅ Created: {name}")

def make_monthly_playlist(sp, user_id, liked):
    # Determine last full calendar month
    today = datetime.utcnow()
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # Filter liked songs from last month
    monthly_tracks = [
        item['track']['id']
        for item in liked
        if last_month_start <= datetime.strptime(item['added_at'], "%Y-%m-%dT%H:%M:%SZ") <= last_month_end
    ]

    if monthly_tracks:
        label = last_month_end.strftime("%B %Y")
        name = f"Liked Songs - {label}"
        create_or_replace_playlist(sp, user_id, name, list(reversed(monthly_tracks)))  # oldest to newest
    else:
        print("📭 No songs liked last month. Skipping monthly playlist.")

def make_recent_50_playlist(sp, user_id, liked):
    recent_50 = [item['track']['id'] for item in liked[:50] if item['track']]
    create_or_replace_playlist(sp, user_id, RECENT_50_NAME, recent_50)

def make_genre_playlist(sp, user_id, liked):
    genre_map = {}
    all_track_ids = []

    for item in liked:
        track = item['track']
        if not track:
            continue
        track_id = track['id']
        all_track_ids.append(track_id)

        # Get artist genres
        artist_id = track['artists'][0]['id']
        artist = sp.artist(artist_id)
        genres = artist.get("genres", [])

        primary_genre = genres[0] if genres else "Unknown"
        genre_map.setdefault(primary_genre, []).append(track_id)

    # Flatten genre blocks in alphabetical order
    sorted_genres = sorted(genre_map.items())
    flattened = [tid for genre, tracks in sorted_genres for tid in tracks]

    create_or_replace_playlist(sp, user_id, GENRE_PLAYLIST_NAME, flattened)

def run():
    sp = get_spotify()
    user_id = sp.me()["id"]
    liked = get_liked_songs(sp)

    make_monthly_playlist(sp, user_id, liked)
    make_recent_50_playlist(sp, user_id, liked)
    make_genre_playlist(sp, user_id, liked)

if __name__ == "__main__":
    run()
