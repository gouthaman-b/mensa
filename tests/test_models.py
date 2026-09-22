from datetime import date

from mensa.model import (
    DietCategory,
    DietPreference,
    Meal,
    MealItem,
    expand_substance_codes,
    preference_allows,
    split_substance_codes,
)


def test_split_substance_codes_normalizes_sorts_and_deduplicates():
    assert split_substance_codes("4, 20a, 20E; 20a") == ("4", "20a", "20e")


def test_expand_substance_codes_expands_known_groups_and_keeps_exact_codes():
    codes = expand_substance_codes(["20", "27", "4", "99"])
    assert "20a" in codes
    assert "27g" in codes
    assert "4" in codes
    assert "99" not in codes


def test_meal_properties_and_serialization():
    meal = Meal(
        id=42,
        date=date(2026, 9, 21),
        canteen_id=7,
        canteen_name="Mensa A",
        section="vegetarisches Menü",
        kind="main",
        name="Gemüse-Curry",
        notes="contains sesame",
        diet_classes=["N", "B"],
        substances=["20a", "4"],
        items=[MealItem(text_de="Reis", substances=["20a"])],
        price_student=2.5,
        price_staff=3.5,
        price_guest=4.5,
        climate_rating="A",
        nutrition=None,
    )

    assert meal.diet_label == "Vegan+Organic"
    assert meal.diet_category is DietCategory.VEGAN
    assert meal.allergen_codes == ("20a",)
    assert meal.additive_codes == ("4",)
    assert meal.to_dict()["allergens"] == ["20a"]
    assert meal.to_dict()["additives"] == ["4"]
    assert meal.climate_score == 0
    assert meal.price_for("student") == 2.5
    assert meal.to_dict()["price"] == {"student": 2.5, "staff": 3.5, "guest": 4.5}


def test_preference_allows_expected_categories():
    assert preference_allows(DietPreference.VEGAN, DietCategory.VEGAN)
    assert not preference_allows(DietPreference.VEGAN, DietCategory.VEGETARIAN)
    assert preference_allows(DietPreference.PESCATARIAN, DietCategory.FISH)
