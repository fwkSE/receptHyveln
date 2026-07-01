"""Recipe extraction via recipe-scrapers with normalized output."""

import json
import re
from html import unescape

from bs4 import BeautifulSoup, NavigableString, Tag
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import (
    NoSchemaFoundInWildMode,
    WebsiteNotImplementedError,
)
from app.nouw import try_extract_nouw_recipe
from app.section_parser import (
    parse_recipe_from_sections,
    parse_section_ingredient_groups,
    parse_standalone_ingredients,
)
from app.units import detect_measurement_hints

STEP_NUMBER_PATTERN = re.compile(r"^\s*\d+[\.\)]\s*")
MAX_JSON_LD_CHARS = 500_000
JSON_LD_PATTERN = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
INGREDIENT_HEADER_PATTERN = re.compile(r"<strong[^>]*>.*?</strong>", re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
INGREDIENT_PREFIX_CHARS = "▢□■▪▫●○◦•·‣⁃⬤⦁☐☑☒✓✔✗✘"


class ExtractionError(Exception):
    pass


def _strip_html(text: str) -> str:
    return unescape(TAG_PATTERN.sub("", text)).replace("\xa0", " ").strip()


def _normalize_ingredient_text(text: str) -> str:
    """Strip decorative list/checkbox prefixes from ingredient lines."""
    cleaned = text.strip()
    while cleaned:
        first = cleaned[0]
        if first in INGREDIENT_PREFIX_CHARS:
            cleaned = cleaned[1:].lstrip()
            continue
        if first in "-*" and len(cleaned) > 1 and cleaned[1].isspace():
            cleaned = cleaned[1:].lstrip()
            continue
        break
    return cleaned


def _recipe_node(data):
    if isinstance(data, dict):
        node_type = data.get("@type")
        if node_type == "Recipe" or (isinstance(node_type, list) and "Recipe" in node_type):
            return data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                found = _recipe_node(node)
                if found:
                    return found
    elif isinstance(data, list):
        for item in data:
            found = _recipe_node(item)
            if found:
                return found
    return None


def _extract_instruction_text(item) -> str:
    """Flatten Schema.org HowToStep / HowToDirection nodes to plain text."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, list):
        parts = [_extract_instruction_text(part) for part in item]
        return " ".join(part for part in parts if part)
    if isinstance(item, dict):
        text = item.get("text") or item.get("name")
        if text:
            return str(text).strip()
        nested = item.get("itemListElement")
        if nested:
            return _extract_instruction_text(nested)
    return ""


def _parse_steps_from_json_ld(html: str) -> list[str] | None:
    """Parse recipe instructions from JSON-LD when recipe-scrapers fails."""
    for match in JSON_LD_PATTERN.finditer(html):
        raw_json = match.group(1)
        if len(raw_json) > MAX_JSON_LD_CHARS:
            continue
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        recipe = _recipe_node(data)
        if not recipe:
            continue

        raw_instructions = recipe.get("recipeInstructions")
        if not raw_instructions:
            continue

        if isinstance(raw_instructions, str):
            steps = _split_instructions(raw_instructions)
            return steps if steps else None

        if not isinstance(raw_instructions, list):
            continue

        steps: list[str] = []
        for item in raw_instructions:
            text = _extract_instruction_text(item)
            if text:
                steps.append(text)

        if steps:
            return steps

    return None


def _ingredient_text_from_json_ld(raw) -> str | None:
    if isinstance(raw, str):
        return _strip_html(raw) or None
    if isinstance(raw, list):
        parts = [_ingredient_text_from_json_ld(part) for part in raw]
        joined = ", ".join(part for part in parts if part)
        return joined or None
    if isinstance(raw, dict):
        name = raw.get("name") or raw.get("text")
        if name:
            return _strip_html(str(name)) or None
    return None


def _parse_ingredient_groups_from_json_ld(html: str) -> list[dict] | None:
    """Parse grouped ingredients from JSON-LD section headers."""
    for match in JSON_LD_PATTERN.finditer(html):
        raw_json = match.group(1)
        if len(raw_json) > MAX_JSON_LD_CHARS:
            continue
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        recipe = _recipe_node(data)
        if not recipe:
            continue

        raw_ingredients = recipe.get("recipeIngredient")
        if not raw_ingredients:
            continue

        groups: list[dict] = []
        current_title: str | None = None
        current_items: list[str] = []

        for raw in raw_ingredients:
            if isinstance(raw, list):
                for nested in raw:
                    item = _ingredient_text_from_json_ld(nested)
                    if item:
                        current_items.append(item)
                continue

            raw_str = raw if isinstance(raw, str) else str(raw.get("name", raw))
            if INGREDIENT_HEADER_PATTERN.search(raw_str):
                if current_items:
                    groups.append({"title": current_title, "ingredients": current_items})
                current_title = _strip_html(raw_str)
                current_items = []
                continue

            item = _strip_html(raw_str)
            if item:
                current_items.append(item)

        if current_items:
            groups.append({"title": current_title, "ingredients": current_items})

        if groups:
            return groups

    return None


def _recipe_search_root(soup: BeautifulSoup) -> Tag:
    recipe_root = soup.find(attrs={"itemtype": lambda value: value and "Recipe" in str(value)})
    return recipe_root or soup


def _split_element_to_ingredients(element: Tag) -> list[str]:
    if element.name in ("ul", "ol"):
        return [
            li.get_text(" ", strip=True)
            for li in element.find_all("li", recursive=False)
            if li.get_text(strip=True)
        ]

    lines: list[str] = []
    current_parts: list[str] = []

    for child in element.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                current_parts.append(text)
            continue

        if not isinstance(child, Tag):
            continue

        if child.name == "br":
            line = " ".join(current_parts).strip()
            if line:
                lines.append(line)
            current_parts = []
            continue

        text = child.get_text(" ", strip=True)
        if text:
            current_parts.append(text)

    line = " ".join(current_parts).strip()
    if line:
        lines.append(line)

    return lines


def _is_ingredient_header(element: Tag) -> bool:
    if element.name not in ("h2", "h3", "h4"):
        return False
    classes = " ".join(element.get("class", [])).lower()
    return "ingredient" in classes or "wprm-recipe-group" in classes


def _is_ingredient_block(element: Tag) -> bool:
    if element.name == "p":
        classes = " ".join(element.get("class", [])).lower()
        return "ingredient" in classes or element.get("itemprop") == "ingredients"
    return False


def _parse_ingredient_table(table: Tag) -> list[str]:
    items: list[str] = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        cells = [cell for cell in cells if cell]
        if not cells:
            continue
        if len(cells) == 1:
            items.append(cells[0])
            continue

        name, amount = cells[0], cells[1]
        if name.lower().startswith("energi") or "näringsvärde" in name.lower():
            continue

        items.append(f"{amount} {name}".strip())

    return items


def _find_ingredients_heading(soup: BeautifulSoup) -> Tag | None:
    heading = soup.select_one("h2.c-recipe__ingredients-title")
    if heading:
        return heading

    for candidate in soup.find_all("h2"):
        if "ingrediens" in candidate.get_text(strip=True).lower():
            return candidate

    return None


def _find_instructions_heading(soup: BeautifulSoup) -> Tag | None:
    for candidate in soup.find_all("h2"):
        text = candidate.get_text(strip=True).lower()
        if "gör så här" in text or "instruktion" in text:
            return candidate

    return None


def _parse_table_ingredient_groups(soup: BeautifulSoup) -> list[dict] | None:
    """Parse h3/h4 section headers followed by ingredient tables (e.g. Arla)."""
    ingredients_heading = _find_ingredients_heading(soup)
    if not ingredients_heading:
        return None

    instructions_heading = _find_instructions_heading(soup)
    groups: list[dict] = []

    for element in ingredients_heading.find_all_next():
        if instructions_heading is not None and element is instructions_heading:
            break

        if getattr(element, "name", None) not in ("h3", "h4"):
            continue

        table = element.find_next_sibling("table")
        if table is None:
            continue

        title = element.get_text(strip=True).rstrip(":").strip() or None
        items = _parse_ingredient_table(table)
        if items:
            groups.append({"title": title, "ingredients": items})

    return groups if groups else None


def _parse_ingredient_groups_from_html_structure(html: str) -> list[dict] | None:
    """Parse grouped ingredients from common HTML recipe markup."""
    soup = BeautifulSoup(html, "html.parser")
    search_root = _recipe_search_root(soup)

    table_groups = _parse_table_ingredient_groups(soup)
    if table_groups:
        return table_groups

    wprm_groups = search_root.select(".wprm-recipe-ingredient-group")
    if wprm_groups:
        groups: list[dict] = []
        for group_el in wprm_groups:
            title_el = group_el.select_one(
                ".wprm-recipe-group-name, .wprm-recipe-ingredient-group-name"
            )
            title = title_el.get_text(strip=True).rstrip(":").strip() if title_el else None
            items = [
                li.get_text(" ", strip=True)
                for li in group_el.select(".wprm-recipe-ingredient")
                if li.get_text(strip=True)
            ]
            if items:
                groups.append({"title": title or None, "ingredients": items})
        if groups:
            return groups

    groups = []
    current_title: str | None = None

    for element in search_root.find_all(["h2", "h3", "h4", "p"]):
        if _is_ingredient_header(element):
            current_title = element.get_text(strip=True).rstrip(":").strip() or None
            continue

        if not _is_ingredient_block(element):
            continue

        items = _split_element_to_ingredients(element)
        if not items:
            continue

        groups.append({"title": current_title, "ingredients": items})
        current_title = None

    if not groups:
        return None

    total_items = sum(len(group["ingredients"]) for group in groups)
    if total_items <= 1 and len(groups) == 1:
        return None

    return groups


def _count_grouped_ingredients(groups: list[dict]) -> int:
    return sum(len(group["ingredients"]) for group in groups)


def _resolve_ingredient_groups(html: str, flat_ingredients: list[str]) -> list[dict]:
    candidates: list[list[dict]] = []

    json_ld_groups = _parse_ingredient_groups_from_json_ld(html)
    if json_ld_groups:
        candidates.append(json_ld_groups)

    html_groups = _parse_ingredient_groups_from_html_structure(html)
    if html_groups:
        candidates.append(html_groups)

    section_groups = parse_section_ingredient_groups(html)
    if section_groups:
        candidates.append(section_groups)

    if candidates:
        best = max(
            candidates,
            key=lambda groups: (_count_grouped_ingredients(groups), len(groups)),
        )
        if len(best) > 1:
            return best
        if not flat_ingredients:
            return best

    return _single_ingredient_group(flat_ingredients)


def _single_ingredient_group(ingredients: list[str]) -> list[dict]:
    return [{"title": None, "ingredients": ingredients}]


def _split_instructions(text: str) -> list[str]:
    """Split a block of instructions into individual steps."""
    if not text or not text.strip():
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return [STEP_NUMBER_PATTERN.sub("", line) for line in lines]

    numbered = re.split(r"\n\s*\d+[\.\)]\s*", text)
    numbered = [part.strip() for part in numbered if part.strip()]
    if len(numbered) > 1:
        return numbered

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ])", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) > 1:
        return sentences

    return [text.strip()]


def _normalize_yield(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return ", ".join(str(item) for item in raw if item)
    return str(raw).strip() or None


def _normalize_ingredient_groups(groups: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for group in groups:
        items = [
            item
            for item in (_normalize_ingredient_text(i) for i in group.get("ingredients", []))
            if item
        ]
        if items:
            normalized.append({**group, "ingredients": items})
    return normalized or groups


def _finalize_recipe(recipe: dict) -> dict:
    ingredient_groups = _normalize_ingredient_groups(recipe["ingredient_groups"])
    ingredients = [item for group in ingredient_groups for item in group["ingredients"]]
    measurement_hints = detect_measurement_hints(ingredient_groups, recipe.get("yield"))
    return {
        **recipe,
        "ingredients": ingredients,
        "ingredient_groups": ingredient_groups,
        "measurement_hints": measurement_hints,
    }


def _try_fallback_parsers(html: str) -> dict | None:
    fallback = parse_recipe_from_sections(html)
    if fallback is None:
        return None
    return _finalize_recipe(fallback)


def _safe_scraper_value(getter, default=None):
    try:
        return getter()
    except Exception:
        return default


def _steps_from_scraper_or_html(scraper, html: str) -> list[str]:
    instructions_text = (_safe_scraper_value(scraper.instructions, "") or "").strip()
    steps = _split_instructions(instructions_text) if instructions_text else []
    if steps:
        return steps

    json_ld_steps = _parse_steps_from_json_ld(html)
    if json_ld_steps:
        return json_ld_steps

    fallback = parse_recipe_from_sections(html)
    if fallback and fallback.get("steps"):
        return fallback["steps"]

    return []


def extract_recipe(html: str, url: str) -> dict:
    """Extract and normalize recipe data from HTML."""
    nouw_recipe = try_extract_nouw_recipe(url)
    if nouw_recipe is not None:
        return _finalize_recipe(nouw_recipe)

    scraper = None
    scraper_error: Exception | None = None

    try:
        scraper = scrape_html(html, url, supported_only=False)
    except (WebsiteNotImplementedError, NoSchemaFoundInWildMode) as exc:
        scraper_error = exc
    except Exception as exc:
        scraper_error = exc

    if scraper is None:
        fallback = _try_fallback_parsers(html)
        if fallback is None:
            raise ExtractionError("Kunde inte hitta recept på den här sidan.") from scraper_error
        return fallback

    title = (_safe_scraper_value(scraper.title, "") or "").strip()
    ingredients = [
        i.strip()
        for i in (_safe_scraper_value(scraper.ingredients, []) or [])
        if i and i.strip()
    ]
    if not ingredients:
        standalone_ingredients = parse_standalone_ingredients(html)
        if standalone_ingredients:
            ingredients = standalone_ingredients

    ingredient_groups = _resolve_ingredient_groups(html, ingredients)
    steps = _steps_from_scraper_or_html(scraper, html)
    yield_text = _normalize_yield(_safe_scraper_value(scraper.yields))

    recipe = _finalize_recipe(
        {
            "title": title or "Recept",
            "yield": yield_text,
            "ingredients": ingredients,
            "ingredient_groups": ingredient_groups,
            "steps": steps,
            "measurement_hints": None,
        }
    )
    ingredients = recipe["ingredients"]

    if not title and not ingredients and not steps:
        fallback = _try_fallback_parsers(html)
        if fallback is not None:
            return fallback
        raise ExtractionError("Kunde inte hitta recept på den här sidan.")

    if not ingredients and not steps:
        fallback = _try_fallback_parsers(html)
        if fallback is not None:
            return fallback
        raise ExtractionError("Kunde inte hitta recept på den här sidan.")

    return recipe
