from flask import Flask, render_template, request, jsonify
import pickle
import requests
import pandas as pd

app = Flask(__name__)

# --- TMDB API Key ---
API_KEY = "8265bd1679663a7ea12ac168da84d2e8"

# --- Helper Functions ---
def fetch_movie_details(movie_id):
    """Fetch poster, genres, rating, overview, and cast info from TMDB."""
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US"
        data = requests.get(url).json()

        cast_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={API_KEY}&language=en-US"
        cast_data = requests.get(cast_url).json()

        poster_path = data.get('poster_path')
        genres = [g['name'] for g in data.get('genres', [])]
        cast = [c['name'] for c in cast_data.get('cast', [])[:3]]  # top 3 cast

        return {
            'id': movie_id,
            'title': data.get('title', 'Unknown'),
            'poster': f"https://image.tmdb.org/t/p/w500/{poster_path}" if poster_path else "https://placehold.co/500x750/333/FFFFFF?text=No+Poster",
            'year': data.get('release_date', 'N/A')[:4],
            'rating': f"{data.get('vote_average', 0):.1f}",
            'overview': data.get('overview', 'No overview available.'),
            'genres': genres,
            'cast': ", ".join(cast) if cast else "N/A"
        }
    except Exception as e:
        print(f"Error fetching details: {e}")
        return None


# --- Load model files ---
try:
    movies_dict = pickle.load(open('artifacts/movie_dict.pkl', 'rb'))
    movies = pd.DataFrame(movies_dict)
    similarity = pickle.load(open('artifacts/similarity.pkl', 'rb'))
except FileNotFoundError:
    print("Model files not found.")
    movies, similarity = None, None


# --- Recommendation Logic ---
def recommend(movie):
    """Recommends 4 similar movies with full TMDB details."""
    try:
        index = movies[movies['title'] == movie].index[0]
    except IndexError:
        return []

    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    recommendations = []

    for i in distances[1:5]:
        movie_data = movies.iloc[i[0]]
        details = fetch_movie_details(movie_data.movie_id)
        if details:
            recommendations.append(details)
    return recommendations


# --- Fetch top movies by genre for homepage ---
def get_top_movies_by_genre():
    """Fetch top movies by genre using TMDB genre IDs."""
    # TMDB Genre IDs mapping
    genre_map = {
        "Action": 28,
        "Comedy": 35,
        "Drama": 18,
        "Horror": 27
    }
    
    genre_movies = {}
    
    for genre_name, genre_id in genre_map.items():
        try:
            url = f"https://api.themoviedb.org/3/discover/movie?api_key={API_KEY}&with_genres={genre_id}&sort_by=vote_average.desc&vote_count.gte=100&page=1"
            response = requests.get(url, timeout=5)
            data = response.json()
            results = data.get("results", [])[:4]  # Get top 4 movies
            
            details = []
            for m in results:
                details.append({
                    "id": m["id"],
                    "title": m["title"],
                    "poster": f"https://image.tmdb.org/t/p/w500/{m['poster_path']}" if m.get("poster_path") else "https://placehold.co/500x750/333/FFFFFF?text=No+Poster",
                    "rating": f"{m.get('vote_average', 0):.1f}",
                    "overview": m.get("overview", "No overview available."),
                    "year": m.get("release_date", "N/A")[:4] if m.get("release_date") else "N/A"
                })
            
            genre_movies[genre_name] = details
            
        except Exception as e:
            print(f"Error fetching {genre_name} movies: {e}")
            genre_movies[genre_name] = []
    
    return genre_movies


# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if movies is None:
        return "<h3>Model files not found. Please ensure 'movie_dict.pkl' and 'similarity.pkl' exist in the 'artifacts' folder.</h3>"

    movie_list = movies['title'].tolist()
    recommendations = []
    selected_movie = None
    searched_movie_details = None
    top_movies = get_top_movies_by_genre()

    # Only show recommendations on POST, not on page reload (GET)
    if request.method == 'POST':
        selected_movie = request.form.get('movie')
        if selected_movie:
            # Get the searched movie details
            try:
                movie_row = movies[movies['title'] == selected_movie].iloc[0]
                searched_movie_details = fetch_movie_details(movie_row.movie_id)
            except (IndexError, AttributeError) as e:
                print(f"Error fetching searched movie details: {e}")
                searched_movie_details = None
            
            # Get recommendations
            recommendations = recommend(selected_movie)
            
            # After showing recommendations, render without form data
            # This prevents form resubmission on reload
            return render_template(
                'index.html',
                movie_list=movie_list,
                recommendations=recommendations,
                selected_movie=selected_movie,
                searched_movie_details=searched_movie_details,
                top_movies=top_movies
            )

    # GET request - always show homepage
    return render_template(
        'index.html',
        movie_list=movie_list,
        recommendations=[],
        selected_movie=None,
        searched_movie_details=None,
        top_movies=top_movies
    )


# --- API for AJAX search dropdown ---
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').lower()
    if movies is not None:
        results = [m for m in movies['title'].tolist() if query in m.lower()]
        return jsonify(results[:6])
    return jsonify([])


if __name__ == '__main__':
    app.run(debug=True)
