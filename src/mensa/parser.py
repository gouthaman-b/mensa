from __future__ import annotations

import re
from datetime import date, datetime, timezone

from .model import Meal, MealItem, MealKind

DE_LINE_FIELDS = [f"AUSGABETEXTZEILE{i}" for i in range(1, 8)]

_ALLERGEN_TAG_RE = re.compile(r"\(([0-9a-zA-Z,\s]+)\)\s*$")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").replace(tzinfo=timezone.utc).date()
    except ValueError:
        return None


def classify_meal(section: str | None, dish_name: str | None) -> MealKind:
    section = section or ""
    dish_name = dish_name or ""
    breakfast_section = re.compile(r"fr[üu]e?h|breakfast", re.IGNORECASE)
    side_section = re.compile(r"beilage|side\s*dish|\bsides?\b", re.IGNORECASE)
    side_name = re.compile(
        r"(so(ß|ss)e|sauce|dip|dressing|ketchup|mayonnaise|mayo|remoulade|chutney)\b",
        re.IGNORECASE,
    )
    # words that signal "this is a full dish that merely *has* a sauce"
    dish_connector = re.compile(r"\b(mit|with|an|auf|und|and|zu|on)\b", re.IGNORECASE)

    if breakfast_section.search(section):
        return MealKind.BREAKFAST
    if side_section.search(section):
        return MealKind.SIDE
    if side_name.search(dish_name) and not dish_connector.search(dish_name):
        return MealKind.SIDE
    return MealKind.MAIN


def _split_text_and_allergens(line: str | None) -> tuple[str, list[str]]:
    if not line:
        return "", []
    match = _ALLERGEN_TAG_RE.search(line)
    if not match:
        return line.strip(), []
    codes = [c.strip() for c in match.group(1).split(",") if c.strip()]
    text = line[: match.start()].strip()
    return text, codes


def _parse_items(raw: dict) -> list[MealItem]:
    items: list[MealItem] = []
    for de_field in DE_LINE_FIELDS:
        de_raw = raw.get(de_field)
        if not de_raw:
            continue
        multiple_items = de_raw.split("|")
        for item in multiple_items:
            text_de, allergens_de = _split_text_and_allergens(item)
            if not text_de:
                continue
            items.append(
                MealItem(
                    text_de=text_de,
                        substances=allergens_de,
                )
            )
    return items


def parse_meal(raw: dict) -> Meal:
    diet_raw = raw.get("FREIKENNZEICHEN") or ""
    diet_classes = [c.strip() for c in diet_raw.split(",") if c.strip()]

    allergen_raw = raw.get("ZUSATZSTOFFNUMMERN") or ""
    allergens_overall = [a.strip() for a in allergen_raw.split(",") if a.strip()]

    return Meal(
        id=raw["PRODUKTIONSNUMMER"],
        date=_parse_date(raw.get("PRODUKTIONSDATUM")),
        canteen_id=raw.get("VERBRAUCHSORTNR"),
        canteen_name=raw.get("PRODUKTIONSORTNAME") or "",
        name=raw.get("PRODUKTIONSBEZEICHNUNG") or "",
        section=raw.get("PRODUKTIONSNAME") or "",
        kind=classify_meal(raw.get("PRODUKTIONSNAME"), raw.get("PRODUKTIONSBEZEICHNUNG")),
        diet_classes=diet_classes,
        items=_parse_items(raw),
        substances=allergens_overall,
        price_student=raw.get("VKPREISSTUD") or 0.0,
        price_staff=raw.get("VKPREISBED") or 0.0,
        price_guest=raw.get("VKPREISGAST") or 0.0,
        climate_rating=raw.get("KLIMATELLER"),
        notes=raw.get("HINWEISE") or "",
        nutrition=None,
    )


def parse_meals(raw_list: list[dict]) -> list[Meal]:
    return [parse_meal(r) for r in raw_list]
