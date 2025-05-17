from aiohttp import web
import json
from pathlib import Path
import os  # <-- Add this line

DB_PATH = Path("db/streamnova_all.json")

LANG_FLAGS = {
    "en": "🇺🇸", "es": "🇪🇸", "fr": "🇫🇷", "de": "🇩🇪",
    "jp": "🇯🇵", "pt": "🇧🇷", "it": "🇮🇹", "ar": "🇸🇦"
}

async def manifest_handler(request):
    manifest = {
        "id": "org.streamnova.addon",
        "version": "1.0.1",
        "name": "Stream Nova",
        "description": "Auto-scraping multi-source streaming addon with language flags",
        "resources": ["catalog", "stream"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "all", "name": "Stream Nova Catalog"},
            {"type": "series", "id": "all", "name": "Stream Nova Series Catalog"}
        ],
        "idPrefixes": ["streamnova_"]
    }
    return web.json_response(manifest)

async def catalog_handler(request):
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    metas = []
    for i, item in enumerate(db):
        flag = LANG_FLAGS.get(item["lang"].lower(), "")
        metas.append({
            "id": f"streamnova_{i}",
            "type": "movie",
            "name": f"{flag} {item['title']}",
            "poster": "",
            "description": f"Source: {item['source'].capitalize()}, Lang: {item['lang'].upper()}"
        })
    return web.json_response({"metas": metas})

async def stream_handler(request):
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    stream_id = request.match_info['id']
    index = int(stream_id.replace("streamnova_", ""))
    entry = db[index]
    flag = LANG_FLAGS.get(entry["lang"].lower(), "")
    stream = {
        "title": entry['title'],
        "url": entry['url'],
        "name": f"{flag} {entry['lang'].upper()} | {entry['source']}"
    }
    return web.json_response({"streams": [stream]})

app = web.Application()
app.router.add_get("/manifest.json", manifest_handler)
app.router.add_get("/catalog/{type}/{id}.json", catalog_handler)
app.router.add_get("/stream/{type}/{id}.json", stream_handler)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7000))  # <-- Use PORT env var if set, fallback to 7000 locally
    web.run_app(app, port=port)
