from aiohttp import web
import json
from pathlib import Path
import os
import aiohttp_cors
import logging
from urllib.parse import unquote

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path("db/streamnova_all.json")

LANG_FLAGS = {
    "en": "🇺🇸", "es": "🇪🇸", "fr": "🇫🇷", "de": "🇩🇪",
    "jp": "🇯🇵", "pt": "🇧🇷", "it": "🇮🇹", "ar": "🇸🇦"
}

def load_database():
    """Load and parse the database with error handling"""
    try:
        if not DB_PATH.exists():
            logger.warning(f"Database file {DB_PATH} not found")
            return []
        
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        if not content:
            logger.warning("Database file is empty")
            return []
        
        # Handle both array format and line-delimited JSON
        if content.startswith('['):
            return json.loads(content)
        else:
            # Parse line-delimited JSON
            entries = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):  # Skip comments
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing JSON line: {line[:50]}... - {e}")
            return entries
            
    except Exception as e:
        logger.error(f"Error loading database: {e}")
        return []

def generate_stremio_id(entry, index):
    """Generate proper Stremio ID"""
    if entry.get("type") == "series":
        series_id = entry.get("series_id") or f"series_{index}"
        season = entry.get("season", 1)
        episode = entry.get("episode", 1)
        return f"{series_id}:{season}:{episode}"
    else:
        return f"movie_{index}"

async def manifest_handler(request):
    """Serve the Stremio addon manifest"""
    manifest = {
        "id": "org.streamnova.addon",
        "version": "1.0.3",
        "name": "StreamNova",
        "description": "Multi-source anime streaming addon with auto-scraping",
        "resources": ["catalog", "stream"],
        "types": ["movie", "series"],
        "catalogs": [
            {
                "type": "movie",
                "id": "streamnova_movies",
                "name": "StreamNova Movies",
                "extra": [
                    {"name": "search", "isRequired": False},
                    {"name": "genre", "isRequired": False}
                ]
            },
            {
                "type": "series", 
                "id": "streamnova_series",
                "name": "StreamNova Series",
                "extra": [
                    {"name": "search", "isRequired": False},
                    {"name": "genre", "isRequired": False}
                ]
            }
        ],
        "idPrefixes": ["streamnova_"],
        "background": "https://i.imgur.com/t8wVwcg.jpg",
        "logo": "https://i.imgur.com/44rdZux.png"
    }
    return web.json_response(manifest)

async def catalog_handler(request):
    """Handle Stremio catalog requests"""
    try:
        db = load_database()
        req_type = request.match_info.get("type", "movie")
        catalog_id = request.match_info.get("id", "all")
        
        # Get query parameters for search/filtering
        search = request.query.get("search", "").lower()
        skip = int(request.query.get("skip", "0"))
        
        metas = []
        
        for i, entry in enumerate(db):
            try:
                entry_type = entry.get("type", "movie")
                
                # Skip if type doesn't match
                if entry_type != req_type:
                    continue
                
                title = entry.get("title", "Unknown")
                
                # Apply search filter
                if search and search not in title.lower():
                    continue
                
                # Generate proper Stremio meta
                stremio_id = generate_stremio_id(entry, i)
                flag = LANG_FLAGS.get(entry.get("lang", "en").lower(), "🌐")
                
                meta = {
                    "id": stremio_id,
                    "type": req_type,
                    "name": f"{flag} {title}",
                    "poster": entry.get("poster", "https://via.placeholder.com/300x450?text=No+Poster"),
                    "background": entry.get("background", ""),
                    "description": entry.get("description", f"From {entry.get('source', 'Unknown')} • Language: {entry.get('lang', 'en').upper()}"),
                    "genres": entry.get("genres", ["Anime"]),
                    "imdbRating": entry.get("rating", "N/A"),
                    "year": entry.get("year", ""),
                    "releaseInfo": f"{entry.get('lang', 'en').upper()} • {entry.get('source', 'Unknown').title()}"
                }
                
                # Add series-specific fields
                if req_type == "series":
                    meta.update({
                        "videos": [{
                            "id": stremio_id,
                            "title": f"S{entry.get('season', 1)}E{entry.get('episode', 1)} - {title}",
                            "season": entry.get("season", 1),
                            "episode": entry.get("episode", 1),
                            "overview": entry.get("description", ""),
                            "thumbnail": entry.get("poster", "")
                        }]
                    })
                
                metas.append(meta)
                
            except Exception as e:
                logger.error(f"Error processing catalog entry {i}: {e}")
                continue
        
        # Pagination
        metas = metas[skip:skip+100]  # Limit to 100 items per page
        
        return web.json_response({"metas": metas})
        
    except Exception as e:
        logger.error(f"Error in catalog_handler: {e}")
        return web.json_response({"metas": []}, status=200)  # Return empty, don't error

async def stream_handler(request):
    """Handle Stremio stream requests"""
    try:
        db = load_database()
        stream_type = request.match_info.get('type', 'movie')
        stream_id = unquote(request.match_info.get('id', ''))
        
        if not stream_id:
            return web.json_response({"streams": []})

        streams = []
        
        # Handle series format: series_id:season:episode
        if ':' in stream_id:
            parts = stream_id.split(':')
            if len(parts) >= 3:
                series_id, season, episode = parts[0], int(parts[1]), int(parts[2])
                
                for entry in db:
                    if (entry.get("type") == "series" and
                        entry.get("series_id") == series_id and
                        entry.get("season") == season and
                        entry.get("episode") == episode):
                        
                        streams.append(create_stream_object(entry))
                        break
        else:
            # Handle movie format
            if stream_id.startswith("movie_"):
                try:
                    index = int(stream_id.replace("movie_", ""))
                    if 0 <= index < len(db):
                        entry = db[index]
                        if entry.get("type", "movie") == "movie":
                            streams.append(create_stream_object(entry))
                except (ValueError, IndexError):
                    pass
            else:
                # Try to find by exact ID match
                for entry in db:
                    if generate_stremio_id(entry, 0) == stream_id:
                        streams.append(create_stream_object(entry))
                        break

        return web.json_response({"streams": streams})
        
    except Exception as e:
        logger.error(f"Error in stream_handler: {e}")
        return web.json_response({"streams": []})

def create_stream_object(entry):
    """Create properly formatted Stremio stream object"""
    flag = LANG_FLAGS.get(entry.get("lang", "en").lower(), "🌐")
    source = entry.get("source", "Unknown").title()
    lang = entry.get("lang", "en").upper()
    
    stream = {
        "url": entry.get("url", ""),
        "title": f"{flag} {lang} • {source}",
        "name": f"{entry.get('title', 'Unknown')}",
        "description": f"Language: {lang} | Source: {source}",
    }
    
    # Add quality info if available
    if "quality" in entry:
        stream["title"] = f"{entry['quality']} • {stream['title']}"
    
    # Add subtitle info if available  
    if entry.get("subtitles"):
        stream["subtitles"] = entry["subtitles"]
    
    # Set behavior hints
    stream["behaviorHints"] = {
        "bingeGroup": f"streamnova-{entry.get('source', 'unknown')}"
    }
    
    return stream

async def health_handler(request):
    """Health check endpoint"""
    try:
        db = load_database()
        return web.json_response({
            "status": "healthy",
            "addon": "StreamNova",
            "entries": len(db),
            "database_exists": DB_PATH.exists(),
            "stremio_compatible": True
        })
    except Exception as e:
        return web.json_response({
            "status": "unhealthy",
            "error": str(e)
        }, status=500)

# Create application
app = web.Application()

# Add routes (Stremio format)
app.router.add_get("/", lambda r: web.Response(text="StreamNova Stremio Addon is running! Add /manifest.json to Stremio."))
app.router.add_get("/health", health_handler)
app.router.add_get("/manifest.json", manifest_handler)
app.router.add_get("/catalog/{type}/{id}.json", catalog_handler)
app.router.add_get("/stream/{type}/{id}.json", stream_handler)

# Enable CORS for Stremio
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
        allow_methods=["GET", "POST", "OPTIONS"]
    )
})

# Add CORS to all routes
for route in list(app.router.routes()):
    cors.add(route)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7000))
    logger.info(f"Starting StreamNova Stremio Addon on port {port}")
    web.run_app(app, port=port, host='0.0.0.0')
