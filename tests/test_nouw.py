"""Tests for Nouw blog recipe extraction."""

from app.extractor import extract_recipe
from app.nouw import (
    _build_recipe_html,
    parse_nouw_post_id,
    try_extract_nouw_recipe,
)

NOUW_POST_JSON = {
    "ID": 37216186,
    "Title": "Camillas heta kycklinggratäng 2.0",
    "Content": (
        '[{"areas":[{"contents":[{"type":"body","data":[{"type":"src","value":'
        '"<p>För 4 portioner</p><ul><li>Smör att steka i</li><li>3-4 st kycklingfiléer</li>'
        '<li>5 dl grädde</li></ul><p>Gör såhär:</p><p>Ställ ugnen på 180 grader.</p>'
        '<p>Servera med sallad.</p>"}]}]}]}]'
    ),
}

NOUW_SHELL_HTML = "<html><body><div id='root'></div></body></html>"


def test_parse_nouw_post_id_from_url():
    assert (
        parse_nouw_post_id(
            "https://nouw.com/lchfmedcamilla/camillas-heta-kycklinggratang-20--37216186"
        )
        == 37216186
    )
    assert parse_nouw_post_id("https://example.com/post--123") is None


def test_build_recipe_html_from_nouw_post():
    built = _build_recipe_html(NOUW_POST_JSON)
    assert built is not None
    html, yield_text = built
    assert yield_text == "4 portioner"
    assert "Ingredienser" in html
    assert "kycklingfiléer" in html
    assert "Ställ ugnen" in html


def test_extract_recipe_from_nouw_shell_html(monkeypatch):
    def fake_fetch(post_id: int):
        assert post_id == 37216186
        return NOUW_POST_JSON

    monkeypatch.setattr("app.nouw.fetch_nouw_post", fake_fetch)

    result = extract_recipe(
        NOUW_SHELL_HTML,
        "https://nouw.com/lchfmedcamilla/camillas-heta-kycklinggratang-20--37216186",
    )
    assert result["title"] == "Camillas heta kycklinggratäng 2.0"
    assert "grädde" in result["ingredients"][-1]
    assert len(result["ingredients"]) == 3
    assert len(result["steps"]) == 2
    assert result["yield"] == "4 portioner"


def test_try_extract_nouw_recipe_returns_none_without_post_id():
    assert try_extract_nouw_recipe("https://nouw.com/blogg/utan-id") is None
