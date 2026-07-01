"""Generic HTML section parser for recipe blogs without Schema.org Recipe."""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

INGREDIENTS_HEADING = re.compile(
    r"^\s*(?:"
    r"ingredienser?|"
    r"du behöver|"
    r"till detta behöver du|"
    r"till maten behöver du|"
    r"det behövs"
    r")\s*:?\s*$",
    re.IGNORECASE,
)
INSTRUCTIONS_HEADING = re.compile(
    r"^\s*(?:"
    r"gör\s*så\s*här|"
    r"gor\s*så\s*här|"
    r"instruktioner?|"
    r"tillagningssätt|"
    r"så här gör du|"
    r"så gör du"
    r")\s*:?\s*$",
    re.IGNORECASE,
)
YIELD_PATTERN = re.compile(r"(\d+)\s*port(?:ioner?)?", re.IGNORECASE)
STEP_LINE = re.compile(r"^\s*\d+[\.\)]\s+")
INGREDIENT_HINT = re.compile(
    r"^\d|½|¼|¾|\d+\s*/\s*\d+|\b("
    r"g|kg|ml|dl|l|msk|tsk|krm|st|styck|knippe|burk|paket|påse|tetror?|"
    r"klyftor?|portioner?|nypa|skiva|kruka"
    r")\b",
    re.IGNORECASE,
)
SKIP_TAGS = frozenset(
    {"script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"}
)
PROMO_PREFIXES = (
    "missa inte",
    "mer med",
    "följ mig",
    "följ gärna",
    "annat gott",
    "populära recept",
    "gillar du receptet",
    "hittar du inte",
    "prova denna",
    "dela:",
    "videoinnehåll",
)


@dataclass
class _SectionCandidate:
    score: float
    ingredients_marker: Tag
    instructions_marker: Tag
    ingredients: list[str]
    steps: list[str]


CONTENT_ROOT_SELECTORS = (
    "[itemtype*='Recipe']",
    ".elementor-location-single",
    ".et_pb_post_content",
    "section.content",
    "div.recipe",
    "main .entry-content",
    ".entry-content",
    "main",
    "article",
)
PROSE_INGREDIENT_SKIP = re.compile(
    r"\b("
    r"recept för det här|"
    r"kommer inte publiceras|"
    r"obligatoriska fält|"
    r"skicka kommentar|"
    r"e-postadress|"
    r"webbplats"
    r")\b",
    re.IGNORECASE,
)


def _has_ingredients_heading(node: Tag) -> bool:
    for element in node.find_all(["h2", "h3", "h4", "p", "strong", "b"]):
        if element.find_parent(SKIP_TAGS):
            continue
        label = _normalized_section_label(element)
        if label and _is_ingredients_heading(label):
            return True
    return False


def _has_instructions_heading_in(node: Tag) -> bool:
    for element in node.find_all(["h2", "h3", "h4", "p", "strong", "b", "span"]):
        if element.find_parent(SKIP_TAGS):
            continue
        label = _normalized_section_label(element)
        if label and _is_instructions_heading(label):
            return True
    return False


def _has_recipe_steps_list(node: Tag) -> bool:
    ordered_list = node.find("ol")
    if ordered_list is None:
        return False
    return len(ordered_list.find_all("li", recursive=False)) >= 2


def _score_content_root(node: Tag) -> float:
    score = 0.0
    if _has_ingredients_heading(node):
        score += 25.0
    if node.select("p.recipe-step, .recipe-step"):
        score += 25.0
    if _has_instructions_heading_in(node) and _has_recipe_steps_list(node):
        score += 20.0
    if node.find("h1"):
        score += 5.0

    classes = " ".join(node.get("class", [])).lower()
    if "recipe" in classes:
        score += 15.0
    if "grid__post" in classes and not _has_ingredients_heading(node):
        score -= 20.0
    if "ecs-post-loop" in classes or "elementor-grid-item" in classes:
        score -= 30.0
    if "et_pb_title_container" in classes:
        score -= 25.0

    return score


def _heading_ancestor_candidates(soup: BeautifulSoup) -> list[Tag]:
    h1 = soup.find("h1")
    if h1 is None:
        return []

    ancestors: list[Tag] = []
    node = h1.parent
    depth = 0
    while isinstance(node, Tag) and depth < 8:
        ancestors.append(node)
        node = node.parent
        depth += 1
    return ancestors


def _find_content_root(soup: BeautifulSoup) -> Tag:
    candidates: list[Tag] = []
    seen: set[int] = set()

    for selector in CONTENT_ROOT_SELECTORS:
        for node in soup.select(selector):
            node_id = id(node)
            if node_id in seen:
                continue
            seen.add(node_id)
            candidates.append(node)

    for node in _heading_ancestor_candidates(soup):
        node_id = id(node)
        if node_id in seen:
            continue
        seen.add(node_id)
        candidates.append(node)

    if soup.body is not None and id(soup.body) not in seen:
        candidates.append(soup.body)

    if not candidates:
        return soup.body or soup

    return max(candidates, key=_score_content_root)


def _normalized_section_label(element: Tag) -> str | None:
    if element.name in SKIP_TAGS:
        return None

    if element.name in {"strong", "b", "span"}:
        text = element.get_text(" ", strip=True)
        return text if text and len(text) <= 40 else None

    if element.name not in {"h1", "h2", "h3", "h4", "h5", "h6", "p"}:
        return None

    if element.name == "p" and len(element.find_all("a")) > 2:
        return None

    text = element.get_text(" ", strip=True)
    if not text or len(text) > 80:
        return None

    return text


def _is_ingredients_heading(text: str) -> bool:
    normalized = text.strip()
    if INGREDIENTS_HEADING.match(normalized):
        return True

    lowered = normalized.lower().rstrip(":")
    if lowered in {"du behöver", "det behövs", "till detta behöver du"}:
        return True
    if "behöver du" in lowered and len(normalized) <= 50:
        return True
    return False


def _is_instructions_heading(text: str) -> bool:
    normalized = text.strip()
    if INSTRUCTIONS_HEADING.match(normalized):
        return True

    lowered = normalized.lower()
    compact = re.sub(r"\s+", "", lowered)
    if "gör så" in lowered and len(normalized) <= 40:
        return True
    if "såhärgör" in compact and len(normalized) <= 50:
        return True
    if compact.startswith("stegförsteg"):
        return True
    if "tillaga" in lowered and len(normalized) <= 60:
        return True
    if ("så här gör" in lowered or "så gör du" in lowered) and len(normalized) <= 50:
        return True
    return False


def _marker_start_element(marker: Tag) -> Tag:
    if marker.name in {"strong", "b"} and marker.parent and marker.parent.name == "p":
        return marker.parent
    return marker


def _document_position(root: Tag, element: Tag) -> int:
    for index, candidate in enumerate(root.find_all(True)):
        if candidate is element:
            return index
    return -1


def _find_all_section_markers(content: Tag, *, kind: str) -> list[Tag]:
    predicate = _is_ingredients_heading if kind == "ingredients" else _is_instructions_heading
    markers: list[Tag] = []

    for element in content.find_all(["h2", "h3", "h4", "h5", "h6", "p", "strong", "b", "span"]):
        if element.find_parent(SKIP_TAGS):
            continue
        label = _normalized_section_label(element)
        if label and predicate(label):
            markers.append(element)

    return markers


def _is_promo_line(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(prefix) for prefix in PROMO_PREFIXES)


def _looks_like_ingredient(text: str) -> bool:
    line = text.strip()
    if not line or len(line) > 200:
        return False
    if _is_promo_line(line):
        return False
    if _is_ingredients_heading(line) or _is_instructions_heading(line):
        return False
    if line.endswith(":") and not INGREDIENT_HINT.search(line):
        return False
    if line.count("http") or "<" in line:
        return False
    return bool(INGREDIENT_HINT.search(line)) or len(line) <= 80


def _looks_like_prose_ingredient_line(text: str) -> bool:
    line = text.strip()
    if not line or len(line) > 120:
        return False
    if _is_promo_line(line) or PROSE_INGREDIENT_SKIP.search(line):
        return False
    if _is_ingredients_heading(line) or _is_instructions_heading(line):
        return False
    if line.count(".") >= 2 and not INGREDIENT_HINT.search(line.split(".", 1)[0]):
        return False
    return bool(INGREDIENT_HINT.search(line))


def _elements_before(stop: Tag, start: Tag) -> list[Tag]:
    elements: list[Tag] = []
    for element in start.find_all_next():
        if element is stop:
            break
        if isinstance(element, Tag) and element.name in {"p", "ul"}:
            elements.append(element)
    return elements


def _looks_like_prose_ingredient_support_line(text: str) -> bool:
    line = text.strip()
    if not line or len(line) > 80:
        return False
    if _is_promo_line(line) or PROSE_INGREDIENT_SKIP.search(line):
        return False
    if _is_ingredients_heading(line) or _is_instructions_heading(line):
        return False
    if line.count(".") >= 2:
        return False
    return True


def _collect_prose_ingredient_block(lines: list[str]) -> list[str]:
    if not lines:
        return []

    strong_matches = [line for line in lines if _looks_like_prose_ingredient_line(line)]
    if not strong_matches:
        return []

    return [line for line in lines if _looks_like_prose_ingredient_support_line(line)]


def _collect_prose_ingredients_between(marker: Tag, ordered_list: Tag) -> list[str]:
    items: list[str] = []
    start = _marker_start_element(marker)

    for element in _elements_before(ordered_list, start):
        if element.name != "p":
            continue
        block_items = _collect_prose_ingredient_block(_lines_from_paragraph(element))
        items.extend(block_items)

    return items


def _score_prose_section_candidate(
    ingredients: list[str],
    steps: list[str],
) -> float:
    if len(ingredients) < 2 or len(steps) < 2:
        return -1.0

    score = min(len(ingredients), 12) * 2.0
    score += min(len(steps), 12) * 3.0

    hint_matches = sum(1 for item in ingredients if INGREDIENT_HINT.search(item))
    score += (hint_matches / len(ingredients)) * 10.0

    return score


def _find_prose_section_candidate(content: Tag) -> _SectionCandidate | None:
    """Recipes embedded in prose: instructions heading, ingredient lines, then ol."""
    instructions_markers = _find_all_section_markers(content, kind="instructions")
    if not instructions_markers:
        return None

    best: _SectionCandidate | None = None

    for instructions_marker in instructions_markers:
        ordered_list = instructions_marker.find_next("ol")
        if not isinstance(ordered_list, Tag):
            continue

        steps = _steps_from_ordered_list(ordered_list)
        ingredients = _collect_prose_ingredients_between(instructions_marker, ordered_list)
        score = _score_prose_section_candidate(ingredients, steps)
        if score < 0:
            continue

        candidate = _SectionCandidate(
            score=score,
            ingredients_marker=instructions_marker,
            instructions_marker=instructions_marker,
            ingredients=ingredients,
            steps=steps,
        )
        if best is None or candidate.score > best.score:
            best = candidate

    return best


def _lines_from_list(element: Tag) -> list[str]:
    return [
        li.get_text(" ", strip=True)
        for li in element.find_all("li", recursive=False)
        if li.get_text(strip=True)
    ]


def _lines_from_paragraph(element: Tag) -> list[str]:
    if element.name in {"ul", "ol"}:
        return _lines_from_list(element)

    if element.name != "p" or element.find("br") is None:
        text = element.get_text(" ", strip=True)
        return [text] if text else []

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


def _collect_ingredients_after(marker: Tag, *, stop_marker: Tag | None) -> list[str]:
    items: list[str] = []
    start = _marker_start_element(marker)
    stop = _marker_start_element(stop_marker) if stop_marker else None
    element = start

    while True:
        element = element.find_next_sibling()
        if element is None or element is stop:
            break
        if not isinstance(element, Tag) or element.name in SKIP_TAGS:
            continue

        if "recipe-step" in element.get("class", []):
            break

        label = _normalized_section_label(element)
        if label and _is_instructions_heading(label):
            break

        if element.name in {"h2", "h3", "h4", "h5", "h6"} and element is not start:
            break

        if element.name in {"ul", "ol"}:
            for line in _lines_from_list(element):
                if _looks_like_ingredient(line):
                    items.append(line)
            continue

        if element.name == "p":
            if _is_instructions_heading(element.get_text(" ", strip=True)):
                break

            for line in _lines_from_paragraph(element):
                if _looks_like_ingredient(line):
                    items.append(line)

    if len(items) >= 2:
        return items

    for element in start.find_all_next(["ul", "ol", "p", "h2", "h3", "h4", "h5", "h6"]):
        if stop is not None and (element is stop or stop in element.parents):
            break

        label = _normalized_section_label(element)
        if label and _is_instructions_heading(label):
            break

        if element.name in {"h2", "h3", "h4", "h5", "h6"} and element is not start:
            break

        if element.name in {"ul", "ol"}:
            for line in _lines_from_list(element):
                if _looks_like_ingredient(line):
                    items.append(line)
            if items:
                break
            continue

        if element.name == "p" and element is not start:
            for line in _lines_from_paragraph(element):
                if _looks_like_ingredient(line):
                    items.append(line)
            if items:
                break

    return items


def _extract_numbered_step(text: str) -> str | None:
    stripped = text.strip()
    if not STEP_LINE.match(stripped):
        return None
    return STEP_LINE.sub("", stripped).strip()


def _step_text_from_list_item(li: Tag) -> str | None:
    paragraph = li.find("p", recursive=False)
    text = paragraph.get_text(" ", strip=True) if paragraph else li.get_text(" ", strip=True)
    if not text or _is_promo_line(text):
        return None
    step = _extract_numbered_step(text) or text
    return step.strip() or None


def _steps_from_ordered_list(ol: Tag) -> list[str]:
    steps: list[str] = []
    for li in ol.find_all("li", recursive=False):
        step = _step_text_from_list_item(li)
        if step:
            steps.append(step)
    return steps


def _collect_steps_after(marker: Tag) -> list[str]:
    steps: list[str] = []
    start = _marker_start_element(marker)
    element = start

    while True:
        element = element.find_next_sibling()
        if element is None:
            break
        if not isinstance(element, Tag):
            continue
        if element.name in SKIP_TAGS or element.name in {"figure", "img"}:
            continue
        if element.name in {"h2", "h3"}:
            break

        if element.name in {"ul", "ol"}:
            for line in _lines_from_list(element):
                step = _extract_numbered_step(line) or line
                if step:
                    steps.append(step)
            continue

        if element.name == "p":
            text = element.get_text(" ", strip=True)
            if not text or _is_promo_line(text):
                continue
            step = _extract_numbered_step(text)
            if step:
                steps.append(step)

    if not steps:
        parent = start.parent
        if parent is not None:
            container = parent.find_next_sibling()
            if isinstance(container, Tag):
                ol = container.find("ol") if container.name != "ol" else container
                if isinstance(ol, Tag):
                    steps = _steps_from_ordered_list(ol)

    if not steps:
        ol = start.find_next("ol")
        if isinstance(ol, Tag):
            steps = _steps_from_ordered_list(ol)

    return steps


def _score_section_candidate(
    content: Tag,
    ingredients_marker: Tag,
    instructions_marker: Tag,
    ingredients: list[str],
    steps: list[str],
) -> float:
    if len(ingredients) < 2 or not steps:
        return -1.0

    ing_pos = _document_position(content, _marker_start_element(ingredients_marker))
    instr_pos = _document_position(content, _marker_start_element(instructions_marker))
    if ing_pos < 0 or instr_pos < 0 or instr_pos <= ing_pos:
        return -1.0

    score = 0.0
    score += min(len(ingredients), 20) * 2.0
    score += min(len(steps), 15) * 3.0

    hint_matches = sum(1 for item in ingredients if INGREDIENT_HINT.search(item))
    score += (hint_matches / len(ingredients)) * 12.0

    distance = instr_pos - ing_pos
    if 2 <= distance <= 80:
        score += 15.0
    elif distance <= 120:
        score += 8.0
    else:
        score -= 6.0

    if ingredients_marker.name in {"h2", "h3", "h4"}:
        score += 5.0
    if instructions_marker.name in {"h2", "h3", "h4"}:
        score += 5.0

    numbered_steps = sum(1 for step in steps if len(step) > 12)
    score += min(numbered_steps, 10) * 1.5

    return score


def _find_best_section_candidate(content: Tag) -> _SectionCandidate | None:
    ingredients_markers = _find_all_section_markers(content, kind="ingredients")
    instructions_markers = _find_all_section_markers(content, kind="instructions")
    if not instructions_markers:
        return None

    if not ingredients_markers:
        return _find_prose_section_candidate(content)

    best: _SectionCandidate | None = None

    for ingredients_marker in ingredients_markers:
        for instructions_marker in instructions_markers:
            ingredients = _collect_ingredients_after(
                ingredients_marker,
                stop_marker=instructions_marker,
            )
            steps = _collect_steps_after(instructions_marker)
            score = _score_section_candidate(
                content,
                ingredients_marker,
                instructions_marker,
                ingredients,
                steps,
            )
            if score < 0:
                continue

            candidate = _SectionCandidate(
                score=score,
                ingredients_marker=ingredients_marker,
                instructions_marker=instructions_marker,
                ingredients=ingredients,
                steps=steps,
            )
            if best is None or candidate.score > best.score:
                best = candidate

    if best is not None:
        return best

    return _find_prose_section_candidate(content)


def _parse_title(content: Tag, soup: BeautifulSoup) -> str | None:
    scopes = [content]
    if content.parent is not None:
        scopes.append(content.parent)

    for scope in scopes:
        h1 = scope.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
            if title:
                return title

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    return None


def _parse_yield(content: Tag) -> str | None:
    for element in content.find_all(["h2", "h3", "p"], limit=40):
        text = element.get_text(" ", strip=True)
        match = YIELD_PATTERN.search(text)
        if match and len(text) <= 100:
            return f"{match.group(1)} portioner"
    return None


def _collect_recipe_step_paragraphs(content: Tag) -> list[str]:
    steps: list[str] = []
    for paragraph in content.select("p.recipe-step"):
        text = paragraph.get_text(" ", strip=True)
        if not text or _is_promo_line(text):
            continue
        step = _extract_numbered_step(text) or text
        if step:
            steps.append(step)
    return steps


def parse_standalone_ingredients(html: str) -> list[str] | None:
    """Parse ingredients from heading sections when no instruction block is paired."""
    soup = BeautifulSoup(html, "html.parser")
    content = _find_content_root(soup)
    markers = _find_all_section_markers(content, kind="ingredients")
    if not markers:
        return None

    best: list[str] = []
    for marker in markers:
        items = _collect_ingredients_after(marker, stop_marker=None)
        if len(items) > len(best):
            best = items

    return best if best else None


def parse_section_ingredient_groups(html: str) -> list[dict] | None:
    """Parse ingredient groups from the best heading + list match."""
    soup = BeautifulSoup(html, "html.parser")
    content = _find_content_root(soup)
    candidate = _find_best_section_candidate(content)
    if candidate is None:
        standalone = parse_standalone_ingredients(html)
        if standalone:
            return [{"title": None, "ingredients": standalone}]
        return None

    return [{"title": None, "ingredients": candidate.ingredients}]


def parse_recipe_from_sections(html: str) -> dict | None:
    """Best-effort recipe extraction from section headings and following lists."""
    soup = BeautifulSoup(html, "html.parser")
    content = _find_content_root(soup)
    candidate = _find_best_section_candidate(content)
    if candidate is None:
        ingredients = parse_standalone_ingredients(html)
        steps = _collect_recipe_step_paragraphs(content)
        if not ingredients or len(steps) < 2:
            return None

        title = _parse_title(content, soup)
        yield_text = _parse_yield(content)
        ingredient_groups = [{"title": None, "ingredients": ingredients}]
        return {
            "title": title or "Recept",
            "yield": yield_text,
            "ingredients": ingredients,
            "ingredient_groups": ingredient_groups,
            "steps": steps,
        }

    title = _parse_title(content, soup)
    yield_text = _parse_yield(content)
    ingredient_groups = [{"title": None, "ingredients": candidate.ingredients}]

    return {
        "title": title or "Recept",
        "yield": yield_text,
        "ingredients": candidate.ingredients,
        "ingredient_groups": ingredient_groups,
        "steps": candidate.steps,
    }
