import os
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth

ARCHIVE_FILE = "archive_tracker.json"
TRACKS_PER_BATCH = 50
DESC = "Auto-created from liked songs archive"

def load_tracker():
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE) as f:
            return json.load(f)
    return {
        "archived_ids": [],
        "carryover_ids": [],
        "batch_number": 1
    }

def save_tracker(data):
    with open(ARCHIVE_FILE, "w") as f:
        json.dump(data, f)

def get_spotify():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope="user-library-read playlist-modify-private"
    ))

def get_liked(sp):
    liked = []
    offset = 0
    while True:
        results = sp.current_user_saved_tracks(limit=50, offset=offset)
        items = results["items"]
        if not items:
            break
        liked.extend(items)
        offset += 50
    return [t["track"]["id"] for t in liked if t["track"] and t["track"]["id"]]

def create_playlist(sp, user_id, name, track_ids):
    playlist = sp.user_playlist_create(user=user_id, name=name, public=False, description=DESC)
    sp.playlist_add_items(playlist["id"], track_ids)

def run():
    sp = get_spotify()
    user_id = sp.me()["id"]
    tracker = load_tracker()

    archived_ids = set(tracker["archived_ids"])
    carryover = tracker["carryover_ids"]
    batch_num = tracker["batch_number"]

    liked = get_liked(sp)

    # Deduplicate and preserve order
    seen = set()
    unique = []
    for tid in liked:
        if tid not in seen:
            seen.add(tid)
            unique.append(tid)

    # Get newest 50 liked tracks (always)
    start = (batch_num - 1) * TRACKS_PER_BATCH
    end = batch_num * TRACKS_PER_BATCH
    all_batch = unique[start:end]

    if len(all_batch) < TRACKS_PER_BATCH:
        print("❌ Not enough liked songs to generate next batch.")
        return

    # === Create 'All' Playlist ===
    name_all = f"Liked Songs #{batch_num} (All)"
    create_playlist(sp, user_id, name_all, all_batch)
    print(f"✅ Created: {name_all}")

    # === Create 'Fresh' Playlist ===
    fresh_candidates = carryover + [tid for tid in all_batch if tid not in archived_ids and tid not in carryover]

    if len(fresh_candidates) >= TRACKS_PER_BATCH:
        fresh_batch = fresh_candidates[:TRACKS_PER_BATCH]
        name_fresh = f"Liked Songs #{batch_num} (Fresh)"
        create_playlist(sp, user_id, name_fresh, fresh_batch)
        print(f"✅ Created: {name_fresh}")
        archived_ids.update(fresh_batch)
        carryover = fresh_candidates[TRACKS_PER_BATCH:]  # leftovers
    else:
        print(f"⏭️ Only {len(fresh_candidates)} fresh tracks. Skipping Fresh playlist this time.")
        carryover = fresh_candidates  # keep for next run

    # Save updates
    tracker["archived_ids"] = list(archived_ids)
    tracker["carryover_ids"] = carryover
    tracker["batch_number"] = batch_num + 1
    save_tracker(tracker)

if __name__ == "__main__":
    run()
