from datetime import date

from mensa.model import MealKind
from mensa.parser import classify_meal, parse_meal


def test_classify_meal_uses_section_and_dish_name():
    assert classify_meal("Frühstück", "Haferbrei") is MealKind.BREAKFAST
    assert classify_meal("Beilagen", "Kartoffeln") is MealKind.SIDE
    assert classify_meal("Menü", "Tomatensauce") is MealKind.SIDE
    assert classify_meal("Menü", "Pasta mit Tomatensauce") is MealKind.MAIN


def test_parse_meal_maps_fields_and_parses_items():
    raw = {
        "PRODUKTIONSNUMMER": 42,
        "PRODUKTIONSDATUM": "21.09.2026",
        "VERBRAUCHSORTNR": 7,
        "PRODUKTIONSORTNAME": "Mensa A",
        "PRODUKTIONSBEZEICHNUNG": "Gemüse-Curry",
        "PRODUKTIONSNAME": "Vegetarisches Menü",
        "FREIKENNZEICHEN": "N, B",
        "ZUSATZSTOFFNUMMERN": "20a,4",
        "AUSGABETEXTZEILE1": "Reis (20a)|Gemüse (4)",
        "VKPREISSTUD": 2.5,
        "VKPREISBED": 3.5,
        "VKPREISGAST": 4.5,
        "KLIMATELLER": "A",
        "HINWEISE": "contains sesame",
    }

    meal = parse_meal(raw)

    assert meal.id == 42
    assert meal.date == date(2026, 9, 21)
    assert meal.kind is MealKind.MAIN
    assert meal.diet_classes == ["N", "B"]
    assert meal.substances == ["20a", "4"]
    assert [(item.text_de, item.substances) for item in meal.items] == [
        ("Reis", ["20a"]),
        ("Gemüse", ["4"]),
    ]
    assert meal.price_student == 2.5
    assert meal.climate_rating == "A"


def test_parse_meal_handles_missing_optional_values():
    meal = parse_meal({"PRODUKTIONSNUMMER": 1})

    assert meal.date is None
    assert meal.canteen_id is None
    assert meal.items == []
    assert meal.substances == []
