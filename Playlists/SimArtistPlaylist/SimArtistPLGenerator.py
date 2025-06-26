'''This script takes an artists name from a variety of sources and generates a textfile 
with artists similar to the artist and some of their popular songs to feed into Apple Music with a shortcut (M3U2AppleMusic)'''

import os
from dotenv import load_dotenv
import sys
import requests
import FreeSimpleGUI as sg
from plexapi.server import PlexServer
import random

# 1.User defined variables
SIMARTISTSLIMIT = 5  # Limit for similar artists, for radio x 2
ALBLIMIT = 1  # Limit for albums per found similar artist
TRCKLIMIT = 2  # Limit for tracks per found similar artist

# 2. Identify current folder as working folder
current_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_directory)

# 3. Get plex instance by using one of the following methods:

# 3.1. Use your personal PlexUrl and PlexToken directly in the code.
# PLEX_URL = "http://your-plex-server:32400"
# PLEX_TOKEN = "your-plex-token" 

# 3.2. Or point to  *.env with your personal PlexUrl and PlexToken.
envpath = os.path.join('..', '..', 'Plex Working Scripts', 'Z helperfiles', 'plex.env')
load_dotenv(envpath)
plexurl = os.getenv("PLEXURL")
token = os.getenv("PLEXTOKEN")
library = os.getenv("PLEXLIBRARY")
plex = PlexServer(plexurl, token) 
library = plex.library.section(library)

# 4. Functions

def fetch_user_input():
    sg.theme('SystemDefault')  # Set the theme for the GUI

    layout = [
        [sg.Text('Enter artist name:')],
        [sg.InputText(key='artist_name')],
        [sg.Radio('Top Tracks of Similar Artists', 'RADIO1', default=True, key='fetch_tracks'), 
         sg.Radio('Top Albums of Similar Artists', 'RADIO1', key='fetch_albums'),
         sg.Radio('Artist Radio Shuffle', 'RADIO1', key='artist_radio_shuffle')],
        [sg.Button('Generate'), sg.Button('Exit')]
    ]

    window = sg.Window('SimArtistPLGenerator', layout)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        if event == 'Generate':
            source_artist = values['artist_name']
            if values['fetch_tracks']:
                choice = 'tracks'
            elif values['fetch_albums']:
                choice = 'albums'
            elif values['artist_radio_shuffle']:
                choice = 'radio'
            else:
                choice = None
            if source_artist:
                window.close()
                return source_artist, choice

    window.close()

def get_similar_artists_from_lastfm(source_artist, lastfm_api_key, choice):
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={source_artist}&api_key={lastfm_api_key}&format=json"
    response = requests.get(url)
    similar_artists_in_lastfm = []
    if response.status_code == 200:
        data = response.json()
        all_similar_artists_in_lastfm = []
        if "similarartists" in data and "artist" in data["similarartists"]:
            for artist in data["similarartists"]["artist"]:
                name = artist.get("name")
                match = artist.get("match") 
                all_similar_artists_in_lastfm.append(name)
        similar_artists_in_lastfm = filter(all_similar_artists_in_lastfm)
        if choice == 'radio':
            similar_artists_in_lastfm = similar_artists_in_lastfm[:SIMARTISTSLIMIT * 2] 
        else: 
            similar_artists_in_lastfm = similar_artists_in_lastfm[:SIMARTISTSLIMIT]  # Limit to SIMARTISTSLIMIT
        return similar_artists_in_lastfm
    else:
        print(f"Error fetching similar artists from LastFM: {response.status_code}")
        return None

def fetch_top_albums(simartist):
    print(f"Fetching top albums of {simartist} from LastFM...")
    """Fetch top 2 albums for the given artist from LastFM."""
    lastfm_api_key = os.getenv("LFM_API_KEY")
    allalbumtracks = []
    if not lastfm_api_key:
        print("LastFM API key not found in environment variables.")
        return []
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettopalbums&artist={simartist}&api_key={lastfm_api_key}&format=json&limit=5"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching top albums for {simartist} from LastFM: {response.status_code}")
        return []
    data = response.json()
    albums = []
    if "topalbums" in data and "album" in data["topalbums"]:
        for album in data["topalbums"]["album"]:
            name = album.get("name")
            if name and name.lower() != "unknown":
                albums.append(name)
                # Fetch the tracks in that album using a separate LastFM API call
                albumtracks = []
                album_artist = simartist
                album_mbid = album.get("mbid")
                if album_mbid:
                    album_url = f"http://ws.audioscrobbler.com/2.0/?method=album.getinfo&mbid={album_mbid}&api_key={lastfm_api_key}&format=json"
                else:
                    album_url = f"http://ws.audioscrobbler.com/2.0/?method=album.getinfo&artist={album_artist}&album={name}&api_key={lastfm_api_key}&format=json"
                album_response = requests.get(album_url)
                if album_response.status_code == 200:
                    album_data = album_response.json()
                    if "album" in album_data and "tracks" in album_data["album"]:
                        tracks_data = album_data["album"]["tracks"].get("track", [])
                        # tracks_data can be a dict if only one track, or a list
                        if isinstance(tracks_data, dict):
                            albumtracks.append(tracks_data.get("name"))
                        else:
                            for track in tracks_data:
                                track_name = track.get("name")
                                if track_name and track_name.lower() != "unknown":
                                    albumtracks.append(track_name)
                    else:
                        if album_mbid:
                            print(f"No tracks found for album {name} by {album_artist} Go to: (MBID: {album_mbid}).")
                        print(f"No tracks found for album {name} by {album_artist}.")
                allalbumtracks.append(albumtracks)
            if len(albums) == ALBLIMIT:  # Limit albums to ALBLIMIT
                break
    return albums, allalbumtracks

def filter(similar_artists):
    """Filter out artists that are in the Plex library."""
    filtered_artists = []
    for artist in similar_artists:
        if not library.searchArtists(title=artist):
            filtered_artists.append(artist)
            if len(filtered_artists) == int(SIMARTISTSLIMIT * 2):  # Limit to SIMARTISTSLIMIT
                break
    return filtered_artists

def already_in_tracks(name, tracks):
    """Check if a track name is already in the tracks list (case-insensitive)."""
    return any(name.lower() == t.lower() for t in tracks)

def fetch_top_tracks(artist_name, choice):
    """Fetch top 2 tracks for the given artist from LastFM."""
    lastfm_api_key = os.getenv("LFM_API_KEY")
    if not lastfm_api_key:
        print("LastFM API key not found in environment variables.")
        return []
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks&artist={artist_name}&api_key={lastfm_api_key}&format=json&limit=5"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching top tracks for {artist_name} from LastFM: {response.status_code}")
        return []
    data = response.json()
    tracks = []
    if "toptracks" in data and "track" in data["toptracks"]:
        for track in data["toptracks"]["track"]:
            name = track.get("name")
            if name and name.lower() != "unknown" and not already_in_tracks(name, tracks):
                tracks.append(name)
            if choice == 'radio':
                if len(tracks) == 1:
                    break
            else:
                if len(tracks) == TRCKLIMIT:
                    break
    return tracks

def add_2_txtfile(artist, tracks, filename):
    # create a textfile if not exists
    if not os.path.exists('SimArtists.txt'):
        with open(f"{filename}.txt", 'w') as f:
            for track in tracks:
                if artist:
                    f.write(f"{artist} - {track}\n")
                else:
                    f.write(f"{track}\n") # if artist already in track variable
    else: 
        with open(f"{filename}.txt", 'a') as f:
            for track in tracks:
                if artist:
                    f.write(f"{artist} - {track}\n")
                else:
                    f.write(f"{track}\n")

def main():
    """Main function to run the script."""
    lastfm_api_key = os.getenv("LFM_API_KEY")
    if not lastfm_api_key:
        print("LastFM API key not found in environment variables.")
        sys.exit(1)
    source_artist, choice = fetch_user_input()
    if not source_artist:
        print("No artist name provided.")
        sys.exit(1)
    similar_artists = get_similar_artists_from_lastfm(source_artist, lastfm_api_key, choice)
    radiotracks = []
    if similar_artists:
        print(f"Similar artists to {source_artist}:")
        for simartist in similar_artists:
            if choice == 'albums':
                albums, allalbumtracks = fetch_top_albums(simartist)
                print(f"{simartist}: {albums}")
                for album, tracks in zip(albums, allalbumtracks):
                    for track in tracks:
                        print(f"{simartist} - {album}: {track}")
                        add_2_txtfile(simartist, [track], filename=f'{source_artist}-SimArtistsAlbums')
            elif choice == 'tracks' or choice == 'radio':

                allsimartists = []
                tracks = fetch_top_tracks(simartist, choice)
                print(f"{simartist}: {tracks}")
                if not choice == 'radio':
                    add_2_txtfile(simartist, tracks, filename=f'{source_artist}-SimArtistsTracks')
                if choice == 'radio':
                    # write all lines of 'simartist - track' to a list
                    for track in tracks:
                        radiotracks.append(f"{simartist} - {track}")


    if choice == 'radio': 
        # add tracks of the artist to the list
        source_tracks = fetch_top_tracks(source_artist, choice)
        print(f"{source_artist}: {source_tracks}")
        for track in source_tracks:
            radiotracks.append(f"{source_artist} - {track}")
        # shuffle the list
        random.shuffle(radiotracks)
        add_2_txtfile(None, radiotracks, filename=f'{source_artist}-Radio')

                    
    # create_tracklist()


main()
