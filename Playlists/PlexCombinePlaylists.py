'''This script takes two or more playlists from a Plex server and combines them into a new playlist. That way, a 'master' playlist can be built. 
Tracks can be sorted in different ways.
New: The total number of tracks can be limited.'''

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound
import random
from datetime import datetime
import os
from dotenv import load_dotenv
import FreeSimpleGUI as sg

# 1. Identify current folder as working folder.
current_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_directory)

# 2. Get plex instance by using one of the following methods:

# 2.1. Use your personal PlexUrl and PlexToken directly in the code.
# PLEX_URL = "http://your-plex-server:32400"
# PLEX_TOKEN = "your-plex-token" 

# 2.2. Or point to  *.env with your personal PlexUrl and PlexToken.
envpath = os.path.join('..', '..', 'Z helperfiles', 'plex.env')
load_dotenv(envpath)
plexurl = os.getenv("PLEXURL")
token = os.getenv("PLEXTOKEN")
library = os.getenv("PLEXLIBRARY")
plex = PlexServer(plexurl, token) 
# discogs = discogs_client.Client('G', user_token='c')
library = plex.library.section(library)

def list_playlists(plex):
    """Retrieve all playlists from the Plex server."""
    playlists = plex.playlists()
    if not playlists:
        print("No playlists found.")
        exit(1)
    
    print("\nAvailable Playlists:")
    for idx, playlist in enumerate(playlists, 1):
        print(f"{idx}. {playlist.title}")
    
    return playlists

def choose_playlists(playlists):
    """Prompt user to select two or more playlists using a GUI dialog."""
    playlist_titles = [pl.title for pl in playlists]
    # Use checkboxes for easier multi-selection
    layout = [
        [sg.Text("Select two or more playlists to combine:")],
        [sg.Column([[sg.Checkbox(title, key=title)] for title in playlist_titles], scrollable=True, vertical_scroll_only=True, size=(350, min(400, 30*len(playlist_titles))))],
        [sg.Button("OK")]
    ]
    window = sg.Window("Choose Playlists", layout)
    event, values = window.read()
    window.close()
    if event is None:
        print("User exited. Exiting script.")
        exit(0)

    # Get selected playlist titles
    selected_titles = [title for title, checked in values.items() if checked]
    if not selected_titles or len(selected_titles) < 2:
        sg.popup("You must select at least two playlists.")
        return choose_playlists(playlists)

    # Map selected titles back to playlist objects
    selected_playlists = [pl for pl in playlists if pl.title in selected_titles]
    return selected_playlists

def reorder_tracks(playlists):
    """Prompt user to select the order of tracks."""
    layout = [
        [sg.Text("Choose track order:")],
        [sg.Radio("Keep sequence", "ORDER", key="k", default=True),
         sg.Radio("Sort by last play date (ascending)", "ORDER", key="a"),
         sg.Radio("Shuffle randomly", "ORDER", key="r")],
        [sg.Text("Total track number:")],
        [sg.Radio("Keep all tracks", "LIMIT", key="all", default=True),
         sg.Radio("Limit to 20", "LIMIT", key="20"),
         sg.Radio("Limit to 50", "LIMIT", key="50")],
        [sg.Button("OK")]
    ]
    window = sg.Window("Track Order and Limit", layout)
    event, values = window.read()
    window.close()
    if event is None:
        print("User exited. Exiting script.")
        exit(0)

    # Determine order
    if values["k"]:
        order = "k"
    elif values["a"]:
        order = "a"
    else:
        order = "r"

    # Determine limit
    if values["all"]:
        limit = None
    elif values["20"]:
        limit = 20
    else:
        limit = 50

    return order, limit
def create_combined_playlist(plex, selected_playlists, seq, limit):
    """Combine multiple playlists into a new one."""
    all_items = []
    for playlist in selected_playlists:
        all_items.extend(playlist.items())

    if seq == 'r':
        random.shuffle(all_items)
    elif seq == 'a':
        # check if all items have lastViewedAt attribute, if None, put item to the beginning of the list
        proxy_date = datetime(1900, 1, 1)
        all_items.sort(key=lambda x: x.lastViewedAt if x.lastViewedAt else proxy_date)
        print("Tracks sorted by last play date:")
        for idx, item in enumerate(all_items, 1):
            print(f"{idx}. {item.title} - {item.lastViewedAt}")

    all_items = all_items[:limit] if limit else all_items

    layout = [
        [sg.Text("Enter name for the new combined playlist:")],
        [sg.Input(key="playlist_name")],
        [sg.Button("OK")]
    ]
    window = sg.Window("New Playlist Name", layout)
    event, values = window.read()
    window.close()
    if event is None:
        print("User exited. Exiting script.")
        exit(0)
    new_playlist_name = values["playlist_name"]
    
    try:
        plex.createPlaylist(new_playlist_name, items=list(all_items))
        print(f"New playlist '{new_playlist_name}' created successfully!")
    except Exception as e:
        print(f"Error creating playlist: {e}")

def main():

    playlists = list_playlists(plex)
    selected_playlists = choose_playlists(playlists)
    seq, limit = reorder_tracks(selected_playlists)
    create_combined_playlist(plex, selected_playlists, seq, limit)

if __name__ == "__main__":
    main()