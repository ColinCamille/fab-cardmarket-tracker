"""Découvre les versions (Regular, Foil, etc.) de chaque carte de cards.json.

En pratique, le scraper récupère déjà les versions et leurs prix à chaque passage
(via la page /Versions). Ce script sert à peupler cards.json en une passe dédiée,
sans attendre le prochain scraping quotidien.
"""

import time

from playwright.sync_api import sync_playwright

from cardmarket_common import BASE_DIR, USER_AGENT, fetch_versions, load_json, save_json

CARDS_FILE = BASE_DIR / "cards.json"


def main():
    cards = load_json(CARDS_FILE, [])
    if not cards:
        print("Aucune carte dans cards.json, rien à faire.")
        return

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
                versions = fetch_versions(page, card)
            except Exception as exc:
                print(f"  [ERREUR] Exception pour {card['nom']}: {exc}")
                versions = None

            if versions:
                card["versions"] = [{"nom": v["nom"], "url": v["url"]} for v in versions]
                print(f"  -> {len(versions)} version(s): {[v['nom'] for v in versions]}")
            else:
                print("  -> aucune version trouvée.")

            if i < len(cards) - 1:
                time.sleep(6)

        browser.close()

    save_json(CARDS_FILE, cards)
    print("Terminé.")


if __name__ == "__main__":
    main()
