import json
from pathlib import Path
from animeonline_scraper import scrape_animeonline
from latanime_scraper import scrape_latanime

def save_to_db(entries, name):
    db_path = Path("db") / f"{name}.json"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

def deduplicate(entries):
    seen = set()
    unique = []
    for entry in entries:
        key = (entry["title"].lower(), entry["url"])
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique

def main():
    all_entries = []

    ao_entries = scrape_animeonline()
    save_to_db(ao_entries, "animeonline")
    all_entries += ao_entries

    lat_entries = scrape_latanime()
    save_to_db(lat_entries, "latanime")
    all_entries += lat_entries

    all_entries = deduplicate(all_entries)
    save_to_db(all_entries, "streamnova_all")

if __name__ == "__main__":
    main()
