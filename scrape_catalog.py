import math
import random
import time

from playwright.sync_api import sync_playwright

from cardmarket_common import BASE_DIR, fetch_card_isolated, load_json, record_price, save_json

CATALOG_FILE = BASE_DIR / "catalog.json"
PRICES_FILE = BASE_DIR / "prices.json"
STATE_FILE = BASE_DIR / "catalog_state.json"

DAYS_PER_CYCLE = 7
SAVE_EVERY = 10
MAX_CONSECUTIVE_BLOCKS = 8


def main():
    catalog = load_json(CATALOG_FILE, [])
    if not catalog:
        print("Catalogue vide, rien à faire.")
        return

    prices = load_json(PRICES_FILE, {})
    state = load_json(STATE_FILE, {"offset": 0})

    chunk_size = math.ceil(len(catalog) / DAYS_PER_CYCLE)
    offset = state.get("offset", 0) % len(catalog)
    slice_cards = (catalog + catalog)[offset:offset + chunk_size]  # wrap-around

    print(f"Catalogue : {len(catalog)} cartes, tranche du jour : {len(slice_cards)} (offset {offset}).")

    consecutive_blocks = 0

    with sync_playwright() as p:
        for i, card in enumerate(slice_cards):
            print(f"[{i + 1}/{len(slice_cards)}] {card['nom']}...")
            try:
                info = fetch_card_isolated(p, card)
            except Exception as exc:
                print(f"  [ERREUR] Exception pour {card['nom']}: {exc}")
                info = None

            if info is None:
                consecutive_blocks += 1
                if consecutive_blocks >= MAX_CONSECUTIVE_BLOCKS:
                    print(f"  [STOP] {consecutive_blocks} echecs consecutifs, IP probablement bloquee. Arret propre.")
                    break
            else:
                consecutive_blocks = 0
                record_price(prices, card, info)

            if (i + 1) % SAVE_EVERY == 0:
                save_json(PRICES_FILE, prices)

            if i < len(slice_cards) - 1:
                time.sleep(random.uniform(8, 12))

    save_json(PRICES_FILE, prices)
    # On n'avance le curseur que si on a bien parcouru toute la tranche (pas d'arret anticipe).
    if consecutive_blocks < MAX_CONSECUTIVE_BLOCKS:
        save_json(STATE_FILE, {"offset": (offset + chunk_size) % len(catalog)})
    print("Terminé.")


if __name__ == "__main__":
    main()
