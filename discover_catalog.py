import json
import re
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent
CARDS_FILE = BASE_DIR / "cards.json"
CATALOG_FILE = BASE_DIR / "catalog.json"

API_BASE = "https://api.goagain.dev/v1/cards"
SETS_API = "https://api.goagain.dev/v1/sets?limit=200"
TARGET_RARITIES = {"M", "L", "F"}
RARITY_NAMES = {"M": "Majestic", "L": "Legendary", "F": "Fabled"}
ALL_RARITY_NAMES = {
    "C": "Common", "R": "Rare", "S": "Super Rare", "M": "Majestic",
    "L": "Legendary", "F": "Fabled", "T": "Token", "B": "Basic",
    "V": "Marvel", "P": "Promo",
}
RARITY_ORDER = ["F", "L", "M", "V", "S", "R", "P", "C", "B", "T"]
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


def first_image(card):
    for printing in card.get("printings", []):
        if printing.get("image_url"):
            return printing["image_url"]
    return None


def best_rarity_label(card):
    rarities = {p.get("rarity") for p in card.get("printings", [])}
    for code in RARITY_ORDER:
        if code in rarities:
            return ALL_RARITY_NAMES.get(code, code)
    return None


def fetch_set_names():
    with urllib.request.urlopen(SETS_API, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    return {s["id"]: s["name"] for s in data}


def extension_for_target_rarity(card, set_names):
    """Extension (nom d'edition) de la premiere impression correspondant a une des rarete ciblees."""
    for printing in card.get("printings", []):
        if printing.get("rarity") in TARGET_RARITIES:
            return set_names.get(printing.get("set_id"))
    return None


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

    print("Recuperation des noms d'extensions...")
    set_names = fetch_set_names()
    print(f"{len(set_names)} extensions recuperees.")

    by_id = {slugify_id(c["name"]): c for c in all_cards}

    cards = load_json(CARDS_FILE, [])
    cards_updated = 0
    for card in cards:
        source = by_id.get(card["id"])
        if not source:
            continue
        changed = False
        if not card.get("image"):
            image = first_image(source)
            if image:
                card["image"] = image
                changed = True
        if not card.get("rarete"):
            rarity = best_rarity_label(source)
            if rarity:
                card["rarete"] = rarity
                changed = True
        if not card.get("extension"):
            extension = extension_for_target_rarity(source, set_names)
            if extension:
                card["extension"] = extension
                changed = True
        if changed:
            cards_updated += 1
    if cards_updated:
        with open(CARDS_FILE, "w", encoding="utf-8") as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)
    existing_cards_ids = {c["id"] for c in cards}

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
        image = first_image(card)
        extension = extension_for_target_rarity(card, set_names)

        if card_id in catalog_by_id:
            catalog_by_id[card_id]["rarete"] = rarity_label
            catalog_by_id[card_id]["url"] = url
            if image:
                catalog_by_id[card_id]["image"] = image
            if extension:
                catalog_by_id[card_id]["extension"] = extension
        else:
            entry = {
                "id": card_id,
                "nom": card["name"],
                "url": url,
                "rarete": rarity_label,
            }
            if image:
                entry["image"] = image
            if extension:
                entry["extension"] = extension
            catalog_by_id[card_id] = entry
            added += 1

    catalog = sorted(catalog_by_id.values(), key=lambda c: c["nom"])
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"Catalogue mis a jour : {len(catalog)} cartes au total ({added} nouvelles).")
    print(f"cards.json : {cards_updated} images ajoutees.")


if __name__ == "__main__":
    main()
