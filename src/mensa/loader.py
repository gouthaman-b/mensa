import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .client import fetch_canteens_raw, fetch_meals_raw
from .model import Canteen, Meal
from .parser import parse_canteen, parse_meal, parse_meal_dict


@dataclass(frozen=True)
class LoadedMenu:
    canteens: tuple[Canteen, ...]
    meals: tuple[Meal, ...]

    @property
    def meals_by_date(self) -> dict[date, tuple[Meal, ...]]:
        grouped: dict[date, list[Meal]] = defaultdict(list)
        for meal in self.meals:
            if meal.date is not None:
                grouped[meal.date].append(meal)
        return {meal_date: tuple(meals) for meal_date, meals in grouped.items()}

    @property
    def canteens_by_id(self) -> dict[int, Canteen]:
        return {canteen.id: canteen for canteen in self.canteens}


def _parse_payload(payload: Any) -> LoadedMenu:
    if isinstance(payload, list):
        raw_canteens: list[Mapping[str, Any]] = []
        raw_meals = payload
    elif isinstance(payload, Mapping):
        raw_canteens = payload.get("canteens", payload.get("canteen", []))
        raw_meals = payload.get("meals", payload.get("meal", []))
    else:
        raise TypeError("menu data must be a JSON object or array")

    canteens = tuple(parse_canteen(raw) for raw in raw_canteens)
    meals = tuple(
        parse_meal(raw) if "PRODUKTIONSNUMMER" in raw else parse_meal_dict(raw) for raw in raw_meals
    )
    return LoadedMenu(canteens=canteens, meals=meals)


def load_menu(
    source: str | Path | Mapping[str, Any] | list[dict[str, Any]] | None = None,
    *,
    canteen_id: int | None = None,
    use_cache: bool = False,
) -> LoadedMenu:
    if source is not None:
        if isinstance(source, (str, Path)):
            with Path(source).open(encoding="utf-8") as file:
                source = json.load(file)
        return _parse_payload(source)

    canteens = load_canteens(use_cache=use_cache)
    selected = [canteen for canteen in canteens if canteen_id is None or canteen.id == canteen_id]
    raw_meals = [
        raw_meal
        for canteen in selected
        for raw_meal in fetch_meals_raw(canteen.id, use_cache=use_cache)
        if not all(
            raw_meal.get(price_field) == 0
            for price_field in ("VKPREISSTUD", "VKPREISBED", "VKPREISGAST")
        )
    ]
    return LoadedMenu(canteens=canteens, meals=tuple(parse_meal(raw) for raw in raw_meals))


def load_canteens(use_cache: bool = False) -> list[Canteen]:
    raw_canteens = fetch_canteens_raw(use_cache)
    return tuple(parse_canteen(raw) for raw in raw_canteens)
