import json
import re
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent
CARDS_FILE = BASE_DIR / "cards.json"
CATALOG_FILE = BASE_DIR / "catalog.json"

API_BASE = "https://api.goagain.dev/v1/cards"
TARGET_RARITIES = {"M", "L", "F"}
RARITY_NAMES = {"M": "Majestic", "L": "Legendary", "F": "Fabled"}
PAGE_SIZE = 100


def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def slugify_id(name):
    name = name.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def slugify_url_name(name):
    name = name.replace("'", "").replace("’", "")
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")


def fetch_all_cards():
    cards = []
    offset = 0
    while True:
        url = f"{API_BASE}?limit={PAGE_SIZE}&offset={offset}"
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        cards.extend(data["data"])
        offset += PAGE_SIZE
        if offset >= data["total"]:
            break
        time.sleep(0.2)
    return cards


def main():
    print("Recuperation de la liste complete des cartes (API goagain.dev)...")
    all_cards = fetch_all_cards()
    print(f"{len(all_cards)} cartes recuperees.")

    existing_cards_ids = {c["id"] for c in load_json(CARDS_FILE, [])}
    catalog = load_json(CATALOG_FILE, [])
    catalog_by_id = {c["id"]: c for c in catalog}

    added = 0
    for card in all_cards:
        rarities = {p["rarity"] for p in card.get("printings", [])}
        hit = rarities & TARGET_RARITIES
        if not hit:
            continue

        card_id = slugify_id(card["name"])
        if card_id in existing_cards_ids:
            continue  # deja suivie manuellement dans cards.json, on ne duplique pas

        rarity_label = RARITY_NAMES[sorted(hit)[0]]
        url = f"https://www.cardmarket.com/en/FleshAndBlood/Cards/{slugify_url_name(card['name'])}"

        if card_id in catalog_by_id:
            catalog_by_id[card_id]["rarete"] = rarity_label
            catalog_by_id[card_id]["url"] = url
        else:
            catalog_by_id[card_id] = {
                "id": card_id,
                "nom": card["name"],
                "url": url,
                "rarete": rarity_label,
            }
            added += 1

    catalog = sorted(catalog_by_id.values(), key=lambda c: c["nom"])
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"Catalogue mis a jour : {len(catalog)} cartes au total ({added} nouvelles).")


if __name__ == "__main__":
    main()
