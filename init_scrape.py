"""Scraping d'initialisation : parcourt tout le catalogue une fois pour amorcer prices.json.

- Résumable : saute les cartes qui ont déjà au moins un point de prix.
- Sauvegarde incrémentale (toutes les SAVE_EVERY cartes) : rien n'est perdu si ça s'arrête.
- Coupe-circuit : s'arrête après MAX_CONSECUTIVE_BLOCKS échecs consécutifs (IP probablement
  bloquée) pour ne pas aggraver le blocage.

À relancer autant de fois que nécessaire : il reprend là où il s'était arrêté.
"""

import random
import time

from playwright.sync_api import sync_playwright

from cardmarket_common import BASE_DIR, fetch_card_isolated, load_json, record_price, save_json

CATALOG_FILE = BASE_DIR / "catalog.json"
CARDS_FILE = BASE_DIR / "cards.json"
PRICES_FILE = BASE_DIR / "prices.json"

SAVE_EVERY = 10
MAX_CONSECUTIVE_BLOCKS = 8
DELAY_MIN = 8
DELAY_MAX = 12


def main():
    catalog = load_json(CATALOG_FILE, [])
    cards = load_json(CARDS_FILE, [])
    prices = load_json(PRICES_FILE, {})

    todo = []
    seen = set()
    for card in cards + catalog:
        if card["id"] in seen:
            continue
        seen.add(card["id"])
        if prices.get(card["id"]):
            continue  # deja un point -> on saute (reprise)
        todo.append(card)

    print(f"{len(todo)} cartes a scraper (sur {len(seen)} au total, {len(seen) - len(todo)} deja faites).")
    if not todo:
        print("Rien a faire, tout est deja scrape.")
        return

    consecutive_blocks = 0
    done = 0

    with sync_playwright() as p:
        for i, card in enumerate(todo):
            print(f"[{i + 1}/{len(todo)}] {card['nom']}...")
            try:
                info = fetch_card_isolated(p, card)
            except Exception as exc:
                print(f"  [ERREUR] {exc}")
                info = None

            if info is None:
                consecutive_blocks += 1
                if consecutive_blocks >= MAX_CONSECUTIVE_BLOCKS:
                    print(f"  [STOP] {consecutive_blocks} echecs consecutifs, IP probablement bloquee. Arret propre.")
                    break
            else:
                consecutive_blocks = 0
                record_price(prices, card, info)
                done += 1

            if (i + 1) % SAVE_EVERY == 0:
                save_json(PRICES_FILE, prices)
                print(f"  [SAVE] progression sauvegardee ({done} prix cette session).")

            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    save_json(PRICES_FILE, prices)
    print(f"Termine. {done} prix recuperes cette session.")


if __name__ == "__main__":
    main()
