import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent
CARDS_FILE = BASE_DIR / "cards.json"
PRICES_FILE = BASE_DIR / "prices.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def parse_price(text):
    match = re.search(r"([\d.,]+)\s*€", text)
    if not match:
        return None
    number = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def parse_int(text):
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def extract_price_info(html):
    soup = BeautifulSoup(html, "html.parser")
    info = {"prix_min": None, "nb_vendeurs": None}
    for dt in soup.find_all("dt"):
        label = dt.get_text(strip=True)
        dd = dt.find_next_sibling("dd")
        if dd is None:
            continue
        if label == "Available from":
            info["prix_min"] = parse_price(dd.get_text())
        elif label == "No. of Available Items":
            info["nb_vendeurs"] = parse_int(dd.get_text())
    return info


def fetch_card(page, card):
    page.goto(card["url"], wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(6000)
    title = page.title()
    html = page.content()
    if "Just a moment" in title:
        print(f"  [BLOQUE] Cloudflare a bloqué la requête pour {card['nom']}")
        return None
    info = extract_price_info(html)
    if info["prix_min"] is None:
        print(f"  [ERREUR] Prix introuvable pour {card['nom']} (page chargée mais sélecteur non trouvé)")
        print(f"  [DEBUG] title={title!r} html_len={len(html)}")
        print(f"  [DEBUG] html_head={html[:1000]!r}")
        return None
    return info


def get_proxy_config():
    server = os.environ.get("PROXY_SERVER")
    if not server:
        return None
    config = {"server": server}
    username = os.environ.get("PROXY_USERNAME")
    password = os.environ.get("PROXY_PASSWORD")
    if username:
        config["username"] = username
    if password:
        config["password"] = password
    return config


def main():
    cards = load_json(CARDS_FILE, [])
    prices = load_json(PRICES_FILE, {})

    if not cards:
        print("Aucune carte dans cards.json, rien à faire.")
        return

    proxy = get_proxy_config()
    print(f"Proxy {'activé' if proxy else 'désactivé'}.")

    with sync_playwright() as p:
        launch_args = {"headless": True}
        if proxy:
            launch_args["proxy"] = proxy
        browser = p.chromium.launch(**launch_args)
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
                entry = {
                    "date": datetime.now(timezone.utc).isoformat(),
                    "prix_min": info["prix_min"],
                    "nb_vendeurs": info["nb_vendeurs"],
                }
                prices.setdefault(card["id"], []).append(entry)
                print(f"  -> {entry['prix_min']} € ({entry['nb_vendeurs']} vendeurs)")

            if i < len(cards) - 1:
                time.sleep(random.uniform(4, 8))

        browser.close()

    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)

    print("Terminé.")


if __name__ == "__main__":
    main()
