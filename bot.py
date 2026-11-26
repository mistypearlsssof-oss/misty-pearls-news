import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

TOKEN = os.environ["DISCORD_TOKEN"].strip()
CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"].strip()

NEWS_URL = "https://www.starstable.com/fr/news"
STATE_FILE = Path("published.json")

HEADERS = {
    "User-Agent": "MistyPearlsNews/2.0",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
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


def translate(text):
    if not text:
        return ""

    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "auto",
                "tl": "fr",
                "dt": "t",
                "q": text
            },
            timeout=20
        )
        response.raise_for_status()

        data = response.json()

        return "".join(
            part[0] for part in data[0]
            if part and part[0]
        )

    except Exception:
        print("Traduction indisponible.")
        return text


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
        raise RuntimeError("Aucun article SSO trouvé.")

    return articles


def get_meta(soup, name):
    tag = soup.find("meta", property=name)

    if not tag:
        tag = soup.find("meta", attrs={"name": name})

    return tag.get("content", "") if tag else ""


def get_category(title):
    text = title.lower()

    categories = [
        (
            ["bug fixes", "bug fix", "correction", "correctif"],
            "🔧 Corrections de bugs"
        ),
        (
            ["roadmap", "feuille de route", "coming soon"],
            "📅 Prochaines nouveautés"
        ),
        (
            ["redeem code", "promo code", "code promotionnel"],
            "🎁 Codes promotionnels"
        ),
        (
            ["festival", "christmas", "halloween", "noël",
             "event", "événement"],
            "🎉 Événements"
        ),
        (
            ["new horse", "nouveau cheval", "nouveaux chevaux"],
            "🐴 Nouveaux chevaux"
        ),
        (
            ["update", "mise à jour"],
            "✨ Mise à jour"
        )
    ]

    for keywords, category in categories:
        if any(word in text for word in keywords):
            return category

    return "📰 Actualité officielle"


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
        or "Découvrez les dernières actualités de Jorvik !"
    )

    image = get_meta(soup, "og:image")

    category = get_category(title)

    content = (
        soup.find("article")
        or soup.find("main")
        or soup.body
    )

    details = []
    seen = set()

    if content:
        for element in content.find_all(
            ["h2", "h3", "h4", "p", "li"]
        ):
            if element.find_parent(["nav", "footer", "header", "aside"]):
                continue

            if element.name == "p" and element.find_parent("li"):
                continue

            text = element.get_text(" ", strip=True)

            if len(text) < 5:
                continue
                
            if any(phrase in text.casefold() for phrase in [
                "for known issues",
                "pour les problèmes connus"
            ]):
                
                continue
            if text == description or text == title:
                continue

            key = " ".join(text.casefold().split())

            if key in seen:
                continue

            seen.add(key)

            if element.name in ["h2", "h3", "h4"]:
                text = f"**{text}**"

            elif element.name == "li":
                text = f"• {text}"

            details.append(text)

    summary = ""

    for paragraph in details:
        if len(summary) + len(paragraph) > 2200:
            remaining = 2200 - len(summary)
            if remaining > 150:
                summary += paragraph[:remaining].rsplit(" ", 1)[0]
                summary += "…"
            break

        summary += paragraph + "\n\n"

    title = translate(title)
    description = translate(description)

    if summary:
        summary = "\n\n".join(
            translate(paragraph.strip())
            for paragraph in summary.split("\n\n")
            if paragraph.strip()
        )

    return title, description, image, category, summary


def publish_article(url):
    title, description, image, category, summary = get_article(url)

    fields = [
        {
            "name": "✧ L'essentiel de l'actualité",
            "value": description[:1000]
        }
    ]

    if summary:
        chunks = []

        while summary and len(chunks) < 3:
            if len(summary) <= 950:
                chunks.append(summary)
                break

            cut = summary.rfind("\n", 0, 950)

            if cut < 100:
                cut = summary.rfind(" ", 0, 950)

            if cut < 100:
                cut = 950

            chunks.append(summary[:cut].strip())
            summary = summary[cut:].strip()

        for index, chunk in enumerate(chunks):
            fields.append({
                "name": (
                    f"✧ Les nouveautés en détail — {index + 1}/{len(chunks)}"
                    if len(chunks) > 1
                    else "✧ Les nouveautés en détail"
                ),
                "value": chunk
            })

    fields.append({
        "name": "🔗 Source officielle",
        "value": f"[Consulter l'article complet]({url})"
    })

    embed = {
        "author": {
            "name": "✦ THE PEARL GAZETTE — ÉDITION OFFICIELLE"
        },
        "title": title[:256],
        "url": url,
        "description": f"**{category}**",
        "color": 10123721,
        "fields": fields,
        "footer": {
            "text": "Misty Pearls • Votre journal de Jorvik"
        }
    }

    if image:
        embed["image"] = {
            "url": urljoin(url, image)
        }

    payload = {
        "content": "✦ Les dernières nouvelles de Jorvik !",
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

    print(f"Article publié : {title}")


def main():
    articles = get_articles()

    if os.getenv("TEST_MODE") == "true":
        print("Mode test activé.")
        if not articles:
            raise RuntimeError("Aucun article trouvé.")
        publish_article(articles[0])
        return

    first_run = not STATE_FILE.exists()

    if first_run:
        published = set()
        pending = articles[:1]

    else:
        published = set(
            json.loads(
                STATE_FILE.read_text(encoding="utf-8")
            )
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

    print("Vérification terminée.")


if __name__ == "__main__":
    main()
