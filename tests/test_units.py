"""Tests for measurement hint detection."""

from app.units import detect_measurement_hints


def test_detects_tbsp_and_lb():
    groups = [{"title": None, "ingredients": ["1 tbsp Olive oil", "450 g/1 lbs Ground Beef"]}]
    hints = detect_measurement_hints(groups, "8 servings")
    keys = {hint["from"] for hint in hints}
    assert "1 tbsp" in keys
    assert "1 lb" in keys
    assert "servings" in keys


def test_swedish_recipe_has_no_hints():
    groups = [{"title": None, "ingredients": ["2 dl mjölk", "500 g köttfärs"]}]
    hints = detect_measurement_hints(groups, "4 portioner")
    assert hints == []


def test_detects_cup_in_dual_format():
    groups = [{"title": None, "ingredients": ["250ml/1 cup water"]}]
    hints = detect_measurement_hints(groups)
    assert any(hint["from"] == "1 cup" for hint in hints)
