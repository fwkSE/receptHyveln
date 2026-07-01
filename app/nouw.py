"""Extract recipes from Nouw blog posts (client-rendered SPA with a JSON API)."""

import json
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.section_parser import YIELD_PATTERN, parse_recipe_from_sections

NOUW_API_BASE = "https://nouw-ms-blog.azurewebsites.net/api/blogpost"
NOUW_POST_ID_RE = re.compile(r"--(\d+)/?$")
NOUW_FETCH_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def parse_nouw_post_id(url: str) -> int | None:
    """Extract Nouw blog post ID from URLs like .../slug--37216186."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if not hostname.endswith("nouw.com"):
        return None

    match = NOUW_POST_ID_RE.search(parsed.path.rstrip("/"))
    if not match:
        return None

    return int(match.group(1))


def _collect_src_html(content) -> str:
    parts: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            if node.get("type") == "src":
                value = node.get("value")
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                for item in node.get("data") or []:
                    if isinstance(item, dict):
                        nested = item.get("value")
                        if isinstance(nested, str) and nested.strip():
                            parts.append(nested)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(content)
    return "".join(parts)


def _build_recipe_html(post: dict) -> tuple[str, str | None] | None:
    title = (post.get("Title") or "").strip()
    raw_content = post.get("Content")
    if not raw_content:
        return None

    if isinstance(raw_content, str):
        try:
            content = json.loads(raw_content)
        except json.JSONDecodeError:
            return None
    else:
        content = raw_content

    fragment = _collect_src_html(content)
    if not fragment.strip():
        return None

    soup = BeautifulSoup(fragment, "html.parser")
    ingredient_list = soup.find("ul")
    if ingredient_list is None:
        return None

    steps: list[str] = []
    after_instructions = False
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if not text:
            continue
        lowered = text.lower().replace(" ", "")
        if "görsåhär" in lowered or ("görså" in lowered and "här" in lowered):
            after_instructions = True
            continue
        if after_instructions:
            steps.append(text)

    if len(steps) < 2:
        return None

    yield_text: str | None = None
    yield_html = ""
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        match = YIELD_PATTERN.search(text)
        if match and len(text) <= 60:
            yield_text = f"{match.group(1)} portioner"
            yield_html = str(paragraph)
            break

    step_items = "".join(f"<li>{step}</li>" for step in steps)
    html = (
        f"<article><h1>{title}</h1>{yield_html}"
        f"<h2>Ingredienser</h2>{ingredient_list}"
        f"<h2>Gör så här</h2><ol>{step_items}</ol></article>"
    )
    return html, yield_text


def fetch_nouw_post(post_id: int) -> dict | None:
    """Fetch a Nouw blog post from the public API."""
    response = httpx.get(
        f"{NOUW_API_BASE}/{post_id}",
        headers={"User-Agent": "ReceptHyveln/1.0"},
        timeout=NOUW_FETCH_TIMEOUT,
        follow_redirects=True,
    )
    if response.status_code >= 400:
        return None
    data = response.json()
    return data if isinstance(data, dict) else None


def try_extract_nouw_recipe(url: str) -> dict | None:
    """Return a normalized recipe dict for a Nouw URL, or None."""
    post_id = parse_nouw_post_id(url)
    if post_id is None:
        return None

    post = fetch_nouw_post(post_id)
    if not post:
        return None

    built = _build_recipe_html(post)
    if not built:
        return None

    html, yield_override = built
    recipe = parse_recipe_from_sections(html)
    if not recipe:
        return None

    title = (post.get("Title") or recipe.get("title") or "Recept").strip()
    recipe["title"] = title
    if yield_override and not recipe.get("yield"):
        recipe["yield"] = yield_override
    return recipe
