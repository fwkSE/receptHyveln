"""Tests for recipe extraction and instruction splitting."""

import pytest

from app.extractor import (
    ExtractionError,
    _normalize_ingredient_text,
    _parse_ingredient_groups_from_html_structure,
    _parse_table_ingredient_groups,
    _split_instructions,
    extract_recipe,
)
from bs4 import BeautifulSoup

JSON_LD_RECIPE = """
<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Testpannkakor",
  "recipeYield": "4 portioner",
  "recipeIngredient": [
    "2 dl vetemjöl",
    "3 dl mjölk",
    "2 ägg"
  ],
  "recipeInstructions": [
    {"@type": "HowToStep", "text": "Blanda mjöl och mjölk."},
    {"@type": "HowToStep", "text": "Tillsätt äggen och vispa."},
    {"@type": "HowToStep", "text": "Stek pannkakorna."}
  ]
}
</script>
</head>
<body><p>Lots of ads and clutter here</p></body>
</html>
"""

NO_RECIPE_HTML = "<html><body><p>Just a blog post, no recipe.</p></body></html>"

LANDLEYSKOK_HTML = """
<html><body>
<div itemtype="http://schema.org/Recipe">
  <p class="ingredient ingredients" itemprop="ingredients">
    500g fläskytterfilé<br/>
    salt, svartpeppar<br/>
    100g pak choi<br/>
    2 salladslökar<br/>
    1 lime
  </p>
  <h2 class="ingredients">Topping:</h2>
  <p class="ingredient ingredients" itemprop="ingredients">
    4 ägg<br/>
    1 röd chilifrukt<br/>
    1 kruka färsk koriander
  </p>
</div>
</body></html>
"""

ARLA_TABLE_HTML = """
<html><body>
<h2 class="c-recipe__ingredients-title">Ingredienser</h2>
<h3 class="u-font-size-h5">Buljong:</h3>
<table>
  <tr><td>Vatten</td><td>1½ liter</td></tr>
  <tr><td>Vitlöksklyftor</td><td>4</td></tr>
</table>
<h3 class="u-font-size-h5">Tare:</h3>
<table>
  <tr><td>Misopasta</td><td>3 msk</td></tr>
</table>
<h3 class="u-font-size-h5">Toppings:</h3>
<table>
  <tr><td>Ägg</td><td>4</td></tr>
</table>
<h2>Gör så här</h2>
<h3 class="u-font-size-h5 u-ml--m">Buljong:</h3>
<ul><li>Koka upp vatten.</li></ul>
</body></html>
"""


def test_parse_table_ingredient_groups():
    groups = _parse_table_ingredient_groups(BeautifulSoup(ARLA_TABLE_HTML, "html.parser"))
    assert groups is not None
    assert len(groups) == 3
    assert groups[0]["title"] == "Buljong"
    assert groups[0]["ingredients"] == ["1½ liter Vatten", "4 Vitlöksklyftor"]
    assert groups[1]["title"] == "Tare"
    assert groups[2]["title"] == "Toppings"


def test_parse_ingredient_groups_from_html_structure():
    groups = _parse_ingredient_groups_from_html_structure(LANDLEYSKOK_HTML)
    assert groups is not None
    assert len(groups) == 2
    assert groups[0]["title"] is None
    assert groups[0]["ingredients"] == [
        "500g fläskytterfilé",
        "salt, svartpeppar",
        "100g pak choi",
        "2 salladslökar",
        "1 lime",
    ]
    assert groups[1]["title"] == "Topping"
    assert groups[1]["ingredients"] == [
        "4 ägg",
        "1 röd chilifrukt",
        "1 kruka färsk koriander",
    ]


def test_split_instructions_multiline():
    text = "Hacka löken.\nBryn färsen.\nTillsätt tomater."
    assert _split_instructions(text) == [
        "Hacka löken.",
        "Bryn färsen.",
        "Tillsätt tomater.",
    ]


def test_split_instructions_numbered():
    text = "1. Hacka löken.\n2. Bryn färsen.\n3. Tillsätt tomater."
    assert _split_instructions(text) == [
        "Hacka löken.",
        "Bryn färsen.",
        "Tillsätt tomater.",
    ]


JSON_LD_GROUPED_RECIPE = """
<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Yakiniku",
  "recipeYield": "4 portioner",
  "recipeIngredient": [
    "500g entrecôte",
    "1 dl soja",
    "<strong><u>Kimchimajonnäs</u></strong>",
    "1 dl majonnäs",
    "<strong><u>Tillbehör</u></strong>",
    "Jasminris",
    "Koriander"
  ],
  "recipeInstructions": "Stek köttet. Servera."
}
</script>
</head>
<body></body>
</html>
"""


def test_extract_recipe_groups_ingredients_from_json_ld_headers():
    result = extract_recipe(JSON_LD_GROUPED_RECIPE, "https://example.com/yakiniku")
    groups = result["ingredient_groups"]
    assert len(groups) == 3
    assert groups[0]["title"] is None
    assert groups[0]["ingredients"] == ["500g entrecôte", "1 dl soja"]
    assert groups[1]["title"] == "Kimchimajonnäs"
    assert groups[1]["ingredients"] == ["1 dl majonnäs"]
    assert groups[2]["title"] == "Tillbehör"
    assert groups[2]["ingredients"] == ["Jasminris", "Koriander"]


def test_extract_recipe_from_json_ld():
    result = extract_recipe(JSON_LD_RECIPE, "https://example.com/testpannkakor")
    assert result["title"] == "Testpannkakor"
    assert result["yield"] is not None
    assert "4" in result["yield"]
    assert len(result["ingredients"]) == 3
    assert "vetemjöl" in result["ingredients"][0]
    assert len(result["steps"]) == 3
    assert "Stek pannkakorna" in result["steps"][2]
    assert len(result["ingredient_groups"]) == 1
    assert result["ingredient_groups"][0]["title"] is None


def test_extract_recipe_fails_without_recipe():
    with pytest.raises(ExtractionError):
        extract_recipe(NO_RECIPE_HTML, "https://example.com/blog")


RECEPTEN_NESTED_INSTRUCTIONS = """
<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Pannkakor",
  "recipeYield": "10 servings",
  "recipeIngredient": ["2,5 dl vetemjöl", "0,5 tsk salt", "6 dl mjölk"],
  "recipeInstructions": [
    {
      "@type": "HowToStep",
      "itemListElement": [
        {"@type": "HowToDirection", "position": 1, "text": "Mät upp vetemjöl och salt."},
        {"@type": "HowToDirection", "position": 2, "text": "Blanda."}
      ]
    },
    {
      "@type": "HowToStep",
      "text": "Vispa i äggen."
    }
  ]
}
</script>
</head>
<body></body>
</html>
"""


def test_extract_recipe_nested_json_ld_instructions():
    result = extract_recipe(
        RECEPTEN_NESTED_INSTRUCTIONS,
        "https://www.recepten.se/recept/pannkakor.html",
    )
    assert result["title"] == "Pannkakor"
    assert len(result["steps"]) == 2
    assert "vetemjöl och salt" in result["steps"][0]
    assert "Blanda" in result["steps"][0]
    assert result["steps"][1] == "Vispa i äggen."


def test_normalize_ingredient_text_strips_checkbox_prefix():
    assert _normalize_ingredient_text("▢ 2 tbsp Oil") == "2 tbsp Oil"
    assert _normalize_ingredient_text("- 1 onion") == "1 onion"
    assert _normalize_ingredient_text("2 dl mjölk") == "2 dl mjölk"


TAMINGTWINS_STYLE_HTML = """
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Classic Spaghetti Bolognese",
  "recipeIngredient": [
    "▢ 2 tbsp Oil",
    "▢ 500 g Beef mince"
  ],
  "recipeInstructions": [
    {"@type": "HowToStep", "text": "Fry the pancetta."},
    {"@type": "HowToStep", "text": "Add the mince."}
  ]
}
</script>
</body></html>
"""


def test_extract_recipe_strips_checkbox_ingredient_prefixes():
    result = extract_recipe(
        TAMINGTWINS_STYLE_HTML,
        "https://www.tamingtwins.com/spaghetti-bolognese/",
    )
    assert result["ingredients"] == ["2 tbsp Oil", "500 g Beef mince"]


SCHEMA_WITH_NOISY_HTML = """
<html><body>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Recipe","name":"Pannkakor",
 "recipeIngredient":["2 dl mjöl","3 dl mjölk","2 ägg"],
 "recipeInstructions":[{"@type":"HowToStep","text":"Blanda."},{"@type":"HowToStep","text":"Stek."}]}
</script>
<h2>Ingredienser</h2>
<ul>
  <li>2 dl mjöl</li><li>3 dl mjölk</li><li>2 ägg</li><li>stekpanna</li><li>visp</li>
</ul>
<h2>Utrustning</h2>
<ul><li>stekpanna</li></ul>
</body></html>
"""


def test_extract_recipe_prefers_schema_ingredients_over_noisy_html():
    result = extract_recipe(SCHEMA_WITH_NOISY_HTML, "https://example.com/pannkakor")
    assert result["ingredients"] == ["2 dl mjöl", "3 dl mjölk", "2 ägg"]
    assert "stekpanna" not in result["ingredients"]
