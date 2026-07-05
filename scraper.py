import random
import time

from playwright.sync_api import sync_playwright

from cardmarket_common import (
    BASE_DIR,
    USER_AGENT,
    already_ran_today,
    fetch_card,
    fetch_versions,
    load_json,
    record_price,
    record_version_price,
    save_json,
)

CARDS_FILE = BASE_DIR / "cards.json"
PRICES_FILE = BASE_DIR / "prices.json"
PRICES_VERSIONS_FILE = BASE_DIR / "prices_versions.json"


def main():
    cards = load_json(CARDS_FILE, [])
    prices = load_json(PRICES_FILE, {})
    prices_versions = load_json(PRICES_VERSIONS_FILE, {})

    if not cards:
        print("Aucune carte dans cards.json, rien à faire.")
        return

    if already_ran_today(prices):
        print("Déjà scrapé aujourd'hui, on ne fait rien.")
        return

    cards_changed = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for i, card in enumerate(cards):
            print(f"[{i + 1}/{len(cards)}] {card['nom']}...")
            try:
                info = fetch_card(page, card)
            except Exception as exc:
                print(f"  [ERREUR] Exception pour {card['nom']}: {exc}")
                info = None

            if info is not None:
                record_price(prices, card, info)

            # Pause plus longue avant la 2e requete (page Versions) pour eviter
            # que deux acces rapproches ne declenchent le challenge Cloudflare.
            time.sleep(random.uniform(12, 20))

            # Prix par version, tout est sur la page /Versions (une seule requête)
            try:
                versions = fetch_versions(page, card)
            except Exception as exc:
                print(f"  [ERREUR] Exception versions pour {card['nom']}: {exc}")
                versions = None

            if versions:
                card["versions"] = [{"nom": v["nom"], "url": v["url"]} for v in versions]
                cards_changed = True
                for v in versions:
                    if v["prix_min"] is not None:
                        record_version_price(prices_versions, card["id"], v["nom"], v)

            if i < len(cards) - 1:
                time.sleep(random.uniform(4, 8))

        browser.close()

    save_json(PRICES_FILE, prices)
    save_json(PRICES_VERSIONS_FILE, prices_versions)
    if cards_changed:
        save_json(CARDS_FILE, cards)
    print("Terminé.")


if __name__ == "__main__":
    main()
