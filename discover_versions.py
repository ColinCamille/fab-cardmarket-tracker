import re
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from cardmarket_common import BASE_DIR, USER_AGENT, is_blocked, load_json, save_json

CARDS_FILE = BASE_DIR / "cards.json"


def card_slug(card_url):
    return card_url.rstrip("/").split("/")[-1]


def version_label(product_url, slug):
    last = product_url.rstrip("/").split("/")[-1]
    if last.startswith(slug + "-"):
        last = last[len(slug) + 1:]
    return last.replace("-", " ").strip() or "Standard"


def discover_versions_for_card(page, card):
    versions_url = card["url"].rstrip("/") + "/Versions"
    page.goto(versions_url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(6000)
    title = page.title()
    if is_blocked(title):
        print(f"  [BLOQUE] Cloudflare a bloqué la requête pour {card['nom']} (Versions)")
        return None

    slug = card_slug(card["url"])
    hrefs = page.eval_on_selector_all(
        "a[href*='/Products/Singles/']",
        "els => els.map(e => e.getAttribute('href'))",
    )
    seen = {}
    for href in hrefs:
        if not href:
            continue
        full_url = href if href.startswith("http") else "https://www.cardmarket.com" + href
        parsed = urlparse(full_url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        label = version_label(clean_url, slug)
        seen[clean_url] = label

    versions = [{"nom": label, "url": url} for url, label in seen.items()]
    return versions


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
                versions = discover_versions_for_card(page, card)
            except Exception as exc:
                print(f"  [ERREUR] Exception pour {card['nom']}: {exc}")
                versions = None

            if versions:
                card["versions"] = versions
                print(f"  -> {len(versions)} version(s) trouvée(s): {[v['nom'] for v in versions]}")
            else:
                print("  -> aucune version trouvée.")

            if i < len(cards) - 1:
                time.sleep(6)

        browser.close()

    save_json(CARDS_FILE, cards)
    print("Terminé.")


if __name__ == "__main__":
    main()
