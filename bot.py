import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

TOKEN = os.environ["DISCORD_TOKEN"].strip()
CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"].strip()

NEWS_URL = "https://www.starstable.com/fr/news"
STATE_FILE = Path("published.json")

HEADERS = {
    "User-Agent": "MistyPearlsNews/1.0"
}

DISCORD_HEADERS = {
    "Authorization": f"Bot {TOKEN}",
    "Content-Type": "application/json"
}


def get_page(url):
    response = requests.get(
        url, headers=HEADERS, timeout=30
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_articles():
    soup = get_page(NEWS_URL)
    articles = []

    for link in soup.find_all("a", href=True):
        url = urljoin(NEWS_URL, link["href"])
        parsed = urlparse(url)

        if parsed.netloc != "www.starstable.com":
            continue

        if not parsed.path.startswith("/fr/article/"):
            continue

        url = url.split("?")[0].split("#")[0]

        if url not in articles:
            articles.append(url)

    if not articles:
        raise RuntimeError("Aucun article SSO trouve.")

    return articles


def get_meta(soup, name):
    tag = soup.find("meta", property=name)

    if not tag:
        tag = soup.find("meta", attrs={"name": name})

    return tag.get("content", "") if tag else ""


def get_article(url):
    soup = get_page(url)
    heading = soup.find("h1")

    title = (
        heading.get_text(" ", strip=True)
        if heading else get_meta(soup, "og:title")
    )

    description = (
        get_meta(soup, "og:description")
        or get_meta(soup, "description")
        or "Decouvrez les dernieres actualites de Jorvik !"
    )

    image = get_meta(soup, "og:image")

    return title, description, image


def publish_article(url):
    title, description, image = get_article(url)

    embed = {
        "author": {
            "name": "The Pearl Gazette | Star Stable Online"
        },
        "title": title[:256],
        "url": url,
        "description": description[:1500],
        "color": 10123721,
        "fields": [
            {
                "name": "📰 Article officiel",
                "value": f"[Lire la suite]({url})"
            }
        ],
        "footer": {
            "text": "Misty Pearls • Actualites automatiques"
        }
    }

    if image:
        embed["image"] = {
            "url": urljoin(url, image)
        }

    payload = {
        "content": "✦ Une nouvelle actualite de Jorvik !",
        "embeds": [embed],
        "allowed_mentions": {"parse": []}
    }

    response = requests.post(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
        headers=DISCORD_HEADERS,
        json=payload,
        timeout=30
    )

    response.raise_for_status()
    print(f"Article publie : {title}")


def main():
    articles = get_articles()

    first_run = not STATE_FILE.exists()

    if first_run:
        published = set()
        pending = articles[:1]
    else:
        published = set(
            json.loads(STATE_FILE.read_text(encoding="utf-8"))
        )
        pending = [
            url for url in articles
            if url not in published
        ]

    for url in reversed(pending):
        publish_article(url)
        published.add(url)

        STATE_FILE.write_text(
            json.dumps(sorted(published), indent=2),
            encoding="utf-8"
        )

    if first_run:
        published.update(articles)

    STATE_FILE.write_text(
        json.dumps(sorted(published), indent=2),
        encoding="utf-8"
    )

    print("Verification terminee.")


if __name__ == "__main__":
    main()
