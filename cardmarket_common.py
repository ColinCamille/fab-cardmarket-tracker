import json
import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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


def is_blocked(title):
    return "Just a moment" in title or "Attention Required" in title


def fetch_card(page, card):
    page.goto(card["url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(6000)
    title = page.title()
    html = page.content()
    if is_blocked(title):
        print(f"  [BLOQUE] Cloudflare a bloqué la requête pour {card['nom']}")
        return None
    info = extract_price_info(html)
    if info["prix_min"] is None:
        print(f"  [ERREUR] Prix introuvable pour {card['nom']} (page chargée mais sélecteur non trouvé)")
        print(f"  [DEBUG] title={title!r} html_len={len(html)}")
        return None
    return info


def already_ran_today(prices):
    today = datetime.now(timezone.utc).date()
    for entries in prices.values():
        if entries and datetime.fromisoformat(entries[-1]["date"]).date() == today:
            return True
    return False


def record_price(prices, card, info):
    entry = {
        "date": datetime.now(timezone.utc).isoformat(),
        "prix_min": info["prix_min"],
        "nb_vendeurs": info["nb_vendeurs"],
    }
    prices.setdefault(card["id"], []).append(entry)
    print(f"  -> {entry['prix_min']} € ({entry['nb_vendeurs']} vendeurs)")
