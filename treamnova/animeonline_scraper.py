import requests
from bs4 import BeautifulSoup

def scrape_animeonline():
    base_url = "https://ww3.animeonline.ninja"
    res = requests.get(f"{base_url}/anime-list/", timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")

    anime_entries = []
    for link in soup.select(".animes a"):
        title = link.get("title", "").strip()
        href = link.get("href", "")
        if not href.startswith("http"):
            href = base_url + href
        anime_entries.append({
            "title": title,
            "url": href,
            "lang": "en",
            "source": "animeonline"
        })
    return anime_entries
