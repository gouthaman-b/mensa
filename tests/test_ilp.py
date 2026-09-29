from datetime import date

from mensa.ilp import UserPreferences, solve_meal_plan
from mensa.model import Meal, MealKind


def make_main(meal_id: int, name: str, price: float) -> Meal:
    return Meal(
        id=meal_id,
        date=date(2026, 9, 29),
        canteen_id=1,
        canteen_name="Mensa A",
        name=name,
        section="Menu",
        kind=MealKind.MAIN,
        diet_classes=["V"],
        items=[],
        substances=[],
        price_student=price,
        price_staff=price,
        price_guest=price,
        climate_rating="A",
        notes=None,
        nutrition=None,
    )


def test_solver_respects_total_budget():
    meals = [make_main(1, "Expensive curry", 5.0), make_main(2, "Lentil bowl", 3.0)]
    result = solve_meal_plan(meals, UserPreferences(budget_total=3.5))

    assert result["status"] == "Optimal"
    assert [meal.name for meal in result["selected_meals"]] == ["Lentil bowl"]
