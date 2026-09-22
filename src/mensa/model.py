import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

try:
    from enum import StrEnum
except ImportError:  # Python 3.10 compatibility

    class StrEnum(str, Enum):
        pass


# Meals can carry combinations, e.g. "N,B" or "S,R"
CLIMATE_RATINGS: tuple[str, ...] = ("A", "B", "C", "D", "E")

DIET_CLASS_CODES: dict[str, str] = {
    "N": "Vegan",
    "V": "Vegetarian",
    "G": "Poultry",
    "S": "Pork",
    "R": "Beef",
    "F": "Fish",
    "B": "Organic",
    "L": "Lamb",
    "A": "Species-appropriate",
}


class DietClass(StrEnum):
    VEGAN = "vegan"  # N
    VEGETARIAN = "vegetarian"  # V
    POULTRY = "poultry"  # G
    PORK = "pork"  # S
    BEEF = "beef"  # R
    FISH = "fish"  # F
    LAMB = "lamb"  # L
    ORGANIC = "organic"  # B
    SPECIES_APPROPRIATE = "species-appropriate"  # A


DIET_CLASS_BY_CODE: dict[str, DietClass] = {
    code: DietClass(label.lower().replace(" ", "-")) for code, label in DIET_CLASS_CODES.items()
}

MEAT_CLASSES = frozenset({DietClass.POULTRY, DietClass.PORK, DietClass.BEEF, DietClass.LAMB})


class DietCategory(StrEnum):
    VEGAN = "vegan"
    VEGETARIAN = "vegetarian"
    FISH = "fish"
    MEAT = "meat"
    UNKNOWN = "unknown"


class DietPreference(StrEnum):
    ANY = "any"
    PESCATARIAN = "pescatarian"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"


_ALLOWED_DIET: dict[DietPreference, frozenset[DietCategory]] = {
    DietPreference.ANY: frozenset(DietCategory),
    DietPreference.PESCATARIAN: frozenset(
        {DietCategory.VEGAN, DietCategory.VEGETARIAN, DietCategory.FISH}
    ),
    DietPreference.VEGETARIAN: frozenset({DietCategory.VEGAN, DietCategory.VEGETARIAN}),
    DietPreference.VEGAN: frozenset({DietCategory.VEGAN}),
}


def preference_allows(pref: DietPreference, category: DietCategory) -> bool:
    return category in _ALLOWED_DIET[pref]


class PriceRole(StrEnum):
    STUDENT = "student"
    STAFF = "staff"
    GUEST = "guest"


class MealKind(StrEnum):
    MAIN = "main"
    SIDE = "side"  # side dishes, sauces, dips
    BREAKFAST = "breakfast"


@dataclass(frozen=True)
class MealItem:
    text_de: str
    substances: list[str] = field(default_factory=list)


@dataclass
class NutritionInfo:
    calories_kcal: float
    protein_g: float
    fat_g: float
    saturated_fat_g: float
    sugar_g: float
    salt_g: float


@dataclass(frozen=True)
class Canteen:
    id: int
    name: str


@dataclass
class Meal:
    id: int
    date: date | None
    canteen_id: int | None
    canteen_name: str
    name: str
    section: str
    kind: MealKind
    diet_classes: list[str]
    items: list[MealItem]
    substances: list[str]
    price_student: float | None
    price_staff: float | None
    price_guest: float | None
    climate_rating: str | None
    notes: str | None
    nutrition: NutritionInfo | None

    @property
    def diet(self) -> frozenset[DietClass]:
        return frozenset(
            DIET_CLASS_BY_CODE[code] for code in self.diet_classes if code in DIET_CLASS_BY_CODE
        )

    @property
    def diet_label(self) -> str:
        return "+".join(DIET_CLASS_CODES.get(code, code) for code in self.diet_classes) or "-"

    @property
    def diet_category(self) -> DietCategory:
        if DietClass.VEGAN in self.diet:
            return DietCategory.VEGAN
        if DietClass.VEGETARIAN in self.diet:
            return DietCategory.VEGETARIAN
        if self.diet & MEAT_CLASSES:
            return DietCategory.MEAT
        if DietClass.FISH in self.diet:
            return DietCategory.FISH
        return DietCategory.UNKNOWN

    def price_for(self, role: str) -> float | None:
        prices = {
            PriceRole.STUDENT: self.price_student,
            PriceRole.STAFF: self.price_staff,
            PriceRole.GUEST: self.price_guest,
        }
        return prices[PriceRole(role.lower())]

    @property
    def allergen_codes(self) -> tuple[str, ...]:
        return tuple(code for code in self.substances if is_allergen(code))

    @property
    def additive_codes(self) -> tuple[str, ...]:
        return tuple(code for code in self.substances if not is_allergen(code))

    @property
    def climate_score(self) -> int | None:
        return CLIMATE_RATINGS.index(self.climate_rating) if self.climate_rating else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "name": self.name,
            "canteen_id": self.canteen_id,
            "canteen": self.canteen_name,
            "section": self.section,
            "diet": sorted(c.value for c in self.diet),
            "diet_category": self.diet_category.value,
            "components": [
                {"de": item.text_de, "codes": list(item.substances)} for item in self.items
            ],
            "allergens": list(self.allergen_codes),
            "additives": list(self.additive_codes),
            "price": {
                "student": self.price_student,
                "staff": self.price_staff,
                "guest": self.price_guest,
            },
            "climate_rating": self.climate_rating,
            "notes": self.notes,
        }


# Allergens & additives

_ADDITIVES = {
    "1": "with antioxidant",
    "2": "with preservatives",
    "3": "sulphured",
    "4": "with colouring",
    "5": "waxed",
    "6": "with flavour enhancer",
    "7": "with sweeteners",
    "8": "contains a source of phenylalanine",
    "9": "with phosphate",
    "10": "blackened",
    "11": "with alcohol",
    "12": "cocoa-containing fat glaze",
}

_ALLERGENS = {
    "20a": "Gluten from wheat & products thereof",
    "20b": "Gluten from rye & products thereof",
    "20c": "Gluten from barley & products thereof",
    "20d": "Gluten from oats & products thereof",
    "20e": "Gluten from spelt & products thereof",
    "20f": "Gluten from kamut & products thereof",
    "21": "Crustaceans & products thereof",
    "22": "Eggs & products thereof",
    "23": "Fish & products thereof",
    "24": "Peanuts & products thereof",
    "25": "Soy & products thereof",
    "26": "Milk & products thereof",
    "27a": "Almonds & products thereof",
    "27b": "Hazelnuts & products thereof",
    "27c": "Walnuts & products thereof",
    "27d": "Cashew nuts & products thereof",
    "27e": "Pecan nuts & products thereof",
    "27f": "Brazil nuts & products thereof",
    "27g": "Pistachios & products thereof",
    "28": "Celery & products thereof",
    "29": "Mustard & products thereof",
    "30": "Sesame seeds & products thereof",
    "31": "Sulphur dioxide/sulphites > 10mg/kg",
    "32": "Lupin & products thereof",
    "33": "Molluscs & products thereof",
}

_SUBSTANCE_CODE_RE = re.compile(r"^(\d+)([a-z]?)$")


@dataclass(frozen=True)
class Substance:
    code: str
    name: str
    is_allergen: bool


SUBSTANCE_CATALOG: dict[str, Substance] = {
    **{c: Substance(c, n, False) for c, n in _ADDITIVES.items()},
    **{c: Substance(c, n, True) for c, n in _ALLERGENS.items()},
}


def is_allergen(code: str) -> bool:
    sub = SUBSTANCE_CATALOG.get(code)
    return sub.is_allergen if sub else False


def describe_substance(code: str) -> str:
    sub = SUBSTANCE_CATALOG.get(code)
    return sub.name if sub else "unknown code"


def clean_substance_code(raw: str) -> str:
    return raw.strip().lower()


def substance_sort_key(code: str) -> tuple[int, str]:
    m = _SUBSTANCE_CODE_RE.match(code)
    return (int(m.group(1)), m.group(2)) if m else (10_000, code)


def split_substance_codes(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    codes = {clean_substance_code(t) for t in re.split(r"[,;]", text)}
    return tuple(sorted((c for c in codes if c), key=substance_sort_key))


# Expand a group code like '20' to its variants '20a'..'20f', for filtering
def expand_substance_codes(codes: Iterable[str]) -> frozenset[str]:
    out: set[str] = set()
    for raw in codes:
        code = clean_substance_code(raw)
        if not code:
            continue
        if code in SUBSTANCE_CATALOG:
            out.add(code)
            continue
        out.update(c for c in SUBSTANCE_CATALOG if re.fullmatch(rf"{re.escape(code)}[a-z]", c))
    return frozenset(out)
