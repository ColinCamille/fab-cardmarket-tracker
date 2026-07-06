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
    info = {"prix_min": None, "prix_moyen": None, "nb_vendeurs": None}
    for dt in soup.find_all("dt"):
        label = dt.get_text(strip=True)
        dd = dt.find_next_sibling("dd")
        if dd is None:
            continue
        if label == "Available from":
            info["prix_min"] = parse_price(dd.get_text())
        elif label == "Price Trend":
            info["prix_moyen"] = parse_price(dd.get_text())
        elif label == "No. of Available Items":
            info["nb_vendeurs"] = parse_int(dd.get_text())
    return info


def is_blocked(title):
    return "Just a moment" in title or "Attention Required" in title


def extract_versions(html):
    """Extrait les versions et leur prix depuis la page /Versions d'une carte.

    Chaque tuile de version contient une image dont l'attribut alt se termine par
    "(Nom de la version)" et un prix "From X €". Tout est sur cette page unique,
    qui reste accessible (contrairement aux pages produit /Products/Singles/...).
    """
    soup = BeautifulSoup(html, "html.parser")
    versions = []
    seen_urls = set()
    for a in soup.select("a[href*='/Products/Singles/']"):
        img = a.find("img")
        alt = img.get("alt") if img else None
        if not alt:
            continue
        match = re.search(r"\(([^)]+)\)\s*$", alt)
        nom = match.group(1).strip() if match else None
        if not nom:
            continue

        href = a.get("href")
        url = href if href.startswith("http") else "https://www.cardmarket.com" + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        prix_min = None
        nb_vendeurs = None
        for para in a.find_all("p"):
            text = para.get_text()
            if "From" in text and prix_min is None:
                prix_min = parse_price(text)
            if "Available" in text and nb_vendeurs is None:
                nb_vendeurs = parse_int(text)

        versions.append({
            "nom": nom,
            "url": url,
            "prix_min": prix_min,
            "prix_moyen": None,
            "nb_vendeurs": nb_vendeurs,
        })
    return versions


def fetch_versions(page, card):
    versions_url = card["url"].rstrip("/") + "/Versions"
    page.goto(versions_url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(6000)
    title = page.title()
    if is_blocked(title):
        print(f"  [BLOQUE] Cloudflare a bloqué la page Versions de {card['nom']}")
        return None
    return extract_versions(page.content())


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


def _new_page(browser):
    context = browser.new_context(
        user_agent=USER_AGENT,
        locale="en-US",
        viewport={"width": 1280, "height": 800},
    )
    return context.new_page()


def fetch_card_isolated(p, card):
    """Récupère le prix d'une carte dans un navigateur neuf (une session par carte).

    Cardmarket ne tolère qu'environ une requête par session de navigateur ; relancer
    le navigateur à chaque carte fait que chaque requête est une "première requête"
    et contourne ainsi le challenge Cloudflare.
    """
    browser = p.chromium.launch(headless=True)
    try:
        return fetch_card(_new_page(browser), card)
    finally:
        browser.close()


def fetch_versions_isolated(p, card):
    browser = p.chromium.launch(headless=True)
    try:
        return fetch_versions(_new_page(browser), card)
    finally:
        browser.close()


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
        "prix_moyen": info.get("prix_moyen"),
        "nb_vendeurs": info["nb_vendeurs"],
    }
    prices.setdefault(card["id"], []).append(entry)
    print(f"  -> {entry['prix_min']} € (tendance {entry['prix_moyen']}) ({entry['nb_vendeurs']} vendeurs)")


def record_version_price(prices_versions, card_id, version_nom, info):
    entry = {
        "date": datetime.now(timezone.utc).isoformat(),
        "prix_min": info["prix_min"],
        "prix_moyen": info.get("prix_moyen"),
        "nb_vendeurs": info["nb_vendeurs"],
    }
    prices_versions.setdefault(card_id, {}).setdefault(version_nom, []).append(entry)
    print(f"    [{version_nom}] -> {entry['prix_min']} € (tendance {entry['prix_moyen']})")
