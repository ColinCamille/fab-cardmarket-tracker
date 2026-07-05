import math
import random
import time

from playwright.sync_api import sync_playwright

from cardmarket_common import BASE_DIR, USER_AGENT, fetch_card, load_json, record_price, save_json

CATALOG_FILE = BASE_DIR / "catalog.json"
PRICES_FILE = BASE_DIR / "prices.json"
STATE_FILE = BASE_DIR / "catalog_state.json"

DAYS_PER_CYCLE = 7


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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for i, card in enumerate(slice_cards):
            print(f"[{i + 1}/{len(slice_cards)}] {card['nom']}...")
            try:
                info = fetch_card(page, card)
            except Exception as exc:
                print(f"  [ERREUR] Exception pour {card['nom']}: {exc}")
                info = None

            if info is not None:
                record_price(prices, card, info)

            if i < len(slice_cards) - 1:
                time.sleep(random.uniform(4, 8))

        browser.close()

    save_json(PRICES_FILE, prices)
    save_json(STATE_FILE, {"offset": (offset + chunk_size) % len(catalog)})
    print("Terminé.")


if __name__ == "__main__":
    main()
