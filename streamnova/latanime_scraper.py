import requests
from bs4 import BeautifulSoup

def scrape_latanime():
    base_url = "https://latanime.org"
    res = requests.get(f"{base_url}/anime/", timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")

    anime_entries = []
    for card in soup.select(".AnimeAltList a"):
        title = card.get("title", "").strip()
        href = card.get("href", "")
        if not href.startswith("http"):
            href = base_url + href
        anime_entries.append({
            "title": title,
            "url": href,
            "lang": "es",
            "source": "latanime"
        })
    return anime_entries
