from collections import defaultdict
from dataclasses import dataclass, field

import pulp

from .model import (
    DietPreference,
    Meal,
    MealKind,
    PriceRole,
    expand_substance_codes,
    preference_allows,
)


@dataclass
class UserPreferences:
    role: str = "student"
    diet_mode: str = "any"
    excluded_allergens: list[str] = field(default_factory=list)

    budget_total: float | None = None
    budget_per_day: float | None = None

    want_breakfast: bool = False
    want_side: bool = False

    max_category_repeat: dict[str, int] = field(default_factory=dict)
    max_avg_sustainability: float | None = None

    price_weight: float = 1.0
    sustainability_weight: float = 1.0

    blacklist_ids: list[str] = field(default_factory=list)

    min_calories_per_day: float | None = None
    max_calories_per_day: float | None = None
    max_sugar_per_day: float | None = None
    max_saturated_fat_per_day: float | None = None
    max_salt_per_day: float | None = None
    min_protein_per_day: float | None = None


_NUTRITION_FIELDS = {
    "calories": "calories_kcal",
    "protein": "protein_g",
    "sugar": "sugar_g",
    "saturated_fat": "saturated_fat_g",
    "salt": "salt_g",
}


def _nutrition_value(meal: Meal, name: str) -> float | None:
    if meal.nutrition is None:
        return None
    return getattr(meal.nutrition, _NUTRITION_FIELDS[name])


def _diet_preference(value: str) -> DietPreference:
    if value == "none":
        return DietPreference.ANY
    return DietPreference(value)


def _sustainability_score(meal: Meal) -> int:
    # Missing climate ratings are treated as the worst score, not as a benefit.
    return meal.climate_score if meal.climate_score is not None else 4


def solve_meal_plan(meals: list[Meal], prefs: UserPreferences) -> dict[str, object]:
    prob = pulp.LpProblem("CanteenMealPlan", pulp.LpMinimize)
    role = PriceRole(prefs.role.lower())
    diet = _diet_preference(prefs.diet_mode.lower())
    excluded_allergens = set(expand_substance_codes(prefs.excluded_allergens))
    blacklist = {str(meal_id) for meal_id in prefs.blacklist_ids}

    def allowed(meal: Meal) -> bool:
        price = meal.price_for(role.value)
        return (
            meal.date is not None
            and price is not None
            and str(meal.id) not in blacklist
            and not excluded_allergens.intersection(meal.allergen_codes)
            and preference_allows(diet, meal.diet_category)
        )

    candidates = [meal for meal in meals if allowed(meal)]
    if not candidates:
        return {"status": "Infeasible", "reason": "No meals satisfy planner filters"}

    nutrition_targets = {
        "calories": prefs.min_calories_per_day is not None
        or prefs.max_calories_per_day is not None,
        "sugar": prefs.max_sugar_per_day is not None,
        "saturated_fat": prefs.max_saturated_fat_per_day is not None,
        "salt": prefs.max_salt_per_day is not None,
        "protein": prefs.min_protein_per_day is not None,
    }
    candidates = [
        meal
        for meal in candidates
        if all(
            not requested or _nutrition_value(meal, attribute) is not None
            for attribute, requested in nutrition_targets.items()
        )
    ]
    if not candidates:
        return {
            "status": "Infeasible",
            "reason": "No meals have the requested nutrition data available",
        }

    variables = {
        index: pulp.LpVariable(f"meal_{index}", cat="Binary") for index in range(len(candidates))
    }
    indexed_candidates = list(enumerate(candidates))
    by_day_kind: dict[tuple[object, MealKind], list[tuple[int, Meal]]] = defaultdict(list)
    for index, meal in indexed_candidates:
        by_day_kind[(meal.date, meal.kind)].append((index, meal))
    days = sorted({meal.date for meal in candidates})

    price_expr = pulp.lpSum(
        meal.price_for(role.value) * variables[index] for index, meal in indexed_candidates
    )

    for day in days:
        mains = by_day_kind.get((day, MealKind.MAIN), [])
        prob += pulp.lpSum(variables[index] for index, _ in mains) == 1, f"one_main_{day}"

        breakfasts = by_day_kind.get((day, MealKind.BREAKFAST), [])
        breakfast_sum = pulp.lpSum(variables[index] for index, _ in breakfasts)
        prob += (
            breakfast_sum == (1 if prefs.want_breakfast else 0)
            if prefs.want_breakfast
            else breakfast_sum <= 1
        )

        sides = by_day_kind.get((day, MealKind.SIDE), [])
        side_sum = pulp.lpSum(variables[index] for index, _ in sides)
        if prefs.want_side:
            prob += side_sum == 1, f"side_{day}"
        else:
            prob += side_sum <= 1, f"side_{day}"

    if prefs.budget_total is not None:
        prob += price_expr <= prefs.budget_total, "total_budget"

    if prefs.budget_per_day is not None:
        for day in days:
            day_meals = [(index, meal) for index, meal in indexed_candidates if meal.date == day]
            prob += (
                pulp.lpSum(
                    meal.price_for(role.value) * variables[index] for index, meal in day_meals
                )
                <= prefs.budget_per_day,
                f"day_budget_{day}",
            )

    for category, cap in prefs.max_category_repeat.items():
        category_meals = [
            (index, meal)
            for index, meal in indexed_candidates
            if meal.kind is MealKind.MAIN and meal.diet_category.value == category
        ]
        if category_meals:
            prob += (
                pulp.lpSum(variables[index] for index, _ in category_meals) <= cap,
                f"max_repeat_{category}",
            )

    main_meals = [(index, meal) for index, meal in indexed_candidates if meal.kind is MealKind.MAIN]
    if prefs.max_avg_sustainability is not None:
        prob += (
            pulp.lpSum(_sustainability_score(meal) * variables[index] for index, meal in main_meals)
            <= prefs.max_avg_sustainability * len(days),
            "sustainability_cap",
        )

    for day in days:
        day_meals = [(index, meal) for index, meal in indexed_candidates if meal.date == day]

        if prefs.min_calories_per_day is not None or prefs.max_calories_per_day is not None:
            calories = pulp.lpSum(
                _nutrition_value(meal, "calories") * variables[index] for index, meal in day_meals
            )
            if prefs.min_calories_per_day is not None:
                prob += calories >= prefs.min_calories_per_day, f"min_calories_{day}"
            if prefs.max_calories_per_day is not None:
                prob += calories <= prefs.max_calories_per_day, f"max_calories_{day}"

        for attribute, limit, operator in (
            ("sugar", prefs.max_sugar_per_day, "max"),
            ("saturated_fat", prefs.max_saturated_fat_per_day, "max"),
            ("salt", prefs.max_salt_per_day, "max"),
            ("protein", prefs.min_protein_per_day, "min"),
        ):
            if limit is None:
                continue
            amount = pulp.lpSum(
                _nutrition_value(meal, attribute) * variables[index] for index, meal in day_meals
            )
            if operator == "max":
                prob += amount <= limit, f"max_{attribute}_{day}"
            else:
                prob += amount >= limit, f"min_{attribute}_{day}"

    sustainability_expr = pulp.lpSum(
        _sustainability_score(meal) * variables[index] for index, meal in indexed_candidates
    )
    prob += prefs.price_weight * price_expr + prefs.sustainability_weight * sustainability_expr

    status_code = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus[status_code]
    selected = [meal for index, meal in indexed_candidates if pulp.value(variables[index]) == 1]
    selected.sort(key=lambda meal: (meal.date, meal.kind.value))

    result: dict[str, object] = {
        "status": status,
        "selected_meals": selected,
        "total_price": pulp.value(price_expr),
        "total_sustainability": sum(_sustainability_score(meal) for meal in selected),
    }
    if status != "Optimal":
        result["reason"] = "No plan satisfies all requested constraints"
    return result
