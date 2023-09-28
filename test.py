import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth

bird_uri = 'spotify:artist:0zj204gA3fbYlvc0ukJtiV'
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())

scope = "user-library-read"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

results = sp.current_user_saved_tracks()
for idx, item in enumerate(results['items']):
    track = item['track']
    print(idx, track['artists'][0]['name'], " – ", track['name'])



# results = spotify.artist_top_tracks(bird_uri)
# print(results['tracks'][0]['uri'])

# print(results['tracks'][0]['name'])
# # print(spotify.audio_features(results['tracks'][0]['uri']))

# song_uris = []
# for i in results['tracks']:
#     song_uris.append(i['uri'])
#     print(i['name'], "energy = ", spotify.audio_features(i['uri'])[0]['energy'])

# spotify.user_playlist_create(0, "test playlist")