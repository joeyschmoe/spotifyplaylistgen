from flask import Flask, request, redirect
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import math

app = Flask(__name__)

# Spotify API credentials
CLIENT_ID = '267667063f5546daab698c699deea638'
CLIENT_SECRET = 'dac476373d9640ed8854f3969bb0bb6c'
REDIRECT_URI = 'http://localhost:5000/callback'

# Create Spotify client object
scopes = "playlist-read-private \
          playlist-read-collaborative \
          playlist-modify-private \
          playlist-modify-public \
          user-follow-read \
          user-top-read \
          user-read-recently-played \
          user-library-read"
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=scopes)

@app.route('/')
def index():
    auth_url = sp_oauth.get_authorize_url()
    return f'<a href="{auth_url}">Login with Spotify</a>'

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    access_token = token_info['access_token']
    
    # Use the access_token to make API calls
    sp = spotipy.Spotify(auth=access_token)
    user_info = sp.current_user()

    # Get and display user's saved tracks
    # results = sp.current_user_saved_tracks()
    # tracks = []
    # for idx, item in enumerate(results['items']):
    #     track = item['track']
    #     to_append = str(idx+1) + ": " + str(track['artists'][0]['name']) + " - " + str(track['name'])
    #     tracks.append(to_append)

    # to_display = ''
    # for item in tracks:
    #     to_display = to_display + item + os.linesep
    # return to_display

    # Create a test playlist
    # sp.user_playlist_create(user_info["id"], "test playlist")

    # Get URIs for user's recently played 50 songs
    recents = sp.current_user_recently_played(50)
    recent_uris = []
    for item in recents["items"]:
        recent_uris.append(item["track"]["uri"])

    # Extract features from each URI
    recent_features = sp.audio_features(recent_uris)
    for track in recent_features:
        track.pop("analysis_url")
        track.pop("id")
        track.pop("track_href")
        track.pop("type")
        track.pop("uri")
        track.pop("mode")

    # Get average value of features (for first song in playlist)
    avgs = {}
    for feature_type in list(recent_features[0]):
        avgs[feature_type] = sum(d[feature_type] for d in recent_features) / len(recent_features)

    # Create Playlists
    sp.user_playlist_create(user_info["id"], "testplaylist-1")
    sp.user_playlist_create(user_info["id"], "testplaylist-2")

    # Use model to learn transition probabilities based on features in each of the user's playlists
    playlists = sp.current_user_playlists()

    model = {"danceability": [],"energy": [],"key": [],"loudness": [],"speechiness": [],"acousticness": [],
             "instrumentalness": [],"liveness": [],"valence": [],"tempo": [],"duration_ms": [],"time_signature": []}

    for playlist in playlists["items"]:
        uris = []
        # If output playlist, store playlist ID
        if playlist["name"] == "testplaylist-1":
            output_playlist_id = playlist["id"]

        # If default playlist, store playlist ID
        if playlist["name"] == "testplaylist-2":
            default_playlist_id = playlist["id"]

        if playlist["tracks"]["total"] == 0:
            continue

        # Get URIs for each track in the playlist
        for item in sp.playlist_items(playlist["id"])["items"]:
            uris.append(item["track"]["uri"])

        # Extract features from each URI
        features = sp.audio_features(uris)
        for track in features:
            track.pop("analysis_url")
            track.pop("id")
            track.pop("track_href")
            track.pop("type")
            track.pop("uri")
            track.pop("mode")

        # Enter transitions between features into model
        for i in range(len(features)-1):
            for feat in list(features[0]):
                transition = [features[i][feat], features[i+1][feat]]
                model[feat].append(transition)

    def weighted_euclidean_dist(feats1, feats2):
        sum = 0
        for key in list(feats1):
            diff = feats1[key] - feats2[key]
            if key == "duration_ms":
                diff = diff / 300000
            elif key == "key":
                diff = diff / 12
            elif key == "loudness":
                diff = diff / 60
            elif key == "tempo":
                diff = diff / 100
            elif key == "time_signature":
                diff = diff / 4
            diff = diff * diff
            sum += diff
        return math.sqrt(sum)

    def nearest(recs, feats):
        # returns the URI of the track closest to the given features
        rec_uris = []
        for track in recs["tracks"]:
            rec_uris.append(track["uri"])
        
        shortest_dist = float('inf')

        features = sp.audio_features(rec_uris)
        for track in features:
            track.pop("analysis_url")
            track.pop("id")
            track.pop("track_href")
            track.pop("type")
            track_uri = track["uri"]
            track.pop("uri")
            track.pop("mode")

            dist = weighted_euclidean_dist(track, feats)
            if dist < shortest_dist:
                shortest_dist = dist
                best_track = track_uri

        return best_track
    
    # Get 100 recommendations based on specified genre
    all_genres = sp.recommendation_genre_seeds()["genres"]
    genre = ["alt-rock"]
    recommendations = sp.recommendations(None, genre, None, 100)

    # Pick first song based on avg features from above and add to playlist
    song_to_add = nearest(recommendations, avgs)

    # Get next song method using previous song and model
    def best_next_feature(model, key, value):
        shortest_distance = float('inf')
        best_value = 0.5
        for tup in model[key]:
            if abs(value - tup[0]) < shortest_distance:
                shortest_distance = abs(value - tup[0])
                best_value = tup[1]
        return best_value

    def get_next_features(model, prev):
        prev_features = sp.audio_features([prev])[0]
        prev_features.pop("analysis_url")
        prev_features.pop("id")
        prev_features.pop("track_href")
        prev_features.pop("type")
        prev_features.pop("uri")
        prev_features.pop("mode")

        next_features = {}

        for key in list(prev_features):
            next_features[key] = best_next_feature(model, key, prev_features[key])

        return next_features

    # Fill Playlist
    for i in range(100):
        sp.user_playlist_add_tracks(user_info["id"], output_playlist_id, [song_to_add])
        next_feats = get_next_features(model, song_to_add)
        recommendations = sp.recommendations(None, genre, None, 100)
        song_to_add = nearest(recommendations, next_feats)

    for i in range(100):
        next_rec = sp.recommendations(None, genre, None, 1)["tracks"][0]["uri"]
        sp.user_playlist_add_tracks(user_info["id"], default_playlist_id, [next_rec])

    # Use markov model to predict features of next song
    # Get 100 recommendations based on previous up to 4 tracks in playlist and genre
    # Find which recommendation is closest to the predicted features and add to playlist

    output_playlist_transitions = {"danceability": [],"energy": [],"key": [],"loudness": [],"speechiness": [],"acousticness": [],
             "instrumentalness": [],"liveness": [],"valence": [],"tempo": [],"duration_ms": [],"time_signature": []}
    default_playlist_transitions = {"danceability": [],"energy": [],"key": [],"loudness": [],"speechiness": [],"acousticness": [],
             "instrumentalness": [],"liveness": [],"valence": [],"tempo": [],"duration_ms": [],"time_signature": []}
    
    for playlist in playlists["items"]:
        uris = []
        # If output playlist, store transitions
        if playlist["name"] == "testplaylist-1":
            # Get URIs for each track in the playlist
            for item in sp.playlist_items(playlist["id"])["items"]:
                uris.append(item["track"]["uri"])

            # Extract features from each URI
            features = sp.audio_features(uris)
            for track in features:
                track.pop("analysis_url")
                track.pop("id")
                track.pop("track_href")
                track.pop("type")
                track.pop("uri")
                track.pop("mode")

            # Enter transitions between features into model
            for i in range(len(features)-1):
                for feat in list(features[0]):
                    transition = [features[i][feat], features[i+1][feat]]
                    output_playlist_transitions[feat].append(transition)

        # If default playlist, store transitions
        if playlist["name"] == "testplaylist-2":
            # Get URIs for each track in the playlist
            for item in sp.playlist_items(playlist["id"])["items"]:
                uris.append(item["track"]["uri"])

            # Extract features from each URI
            features = sp.audio_features(uris)
            for track in features:
                track.pop("analysis_url")
                track.pop("id")
                track.pop("track_href")
                track.pop("type")
                track.pop("uri")
                track.pop("mode")

            # Enter transitions between features into model
            for i in range(len(features)-1):
                for feat in list(features[0]):
                    transition = [features[i][feat], features[i+1][feat]]
                    default_playlist_transitions[feat].append(transition)

        if playlist["tracks"]["total"] == 0:
            continue

        
    return {"model": model, "output_transitions": output_playlist_transitions, "default_transitions": default_playlist_transitions}

    return avgs

    # Get features from most recent songs
    return recents["items"][0]["track"]["uri"]

    # Starting features
    

    # Read user's playlists
    playlists = sp.user_playlists(user_info["id"])
    return playlists["items"][1]

    return user_info
    
    return f'Welcome, {user_info["display_name"]}!'

if __name__ == '__main__':
    app.run()