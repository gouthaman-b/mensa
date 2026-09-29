import json
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import cache
from .client import fetch_canteens_raw, fetch_meals_raw
from .constants import APP_NAME
from .error import MensaError
from .loader import load_canteens, load_menu
from .model import (
    CLIMATE_RATINGS,
    SUBSTANCE_CATALOG,
    DietCategory,
    DietClass,
    DietPreference,
    Meal,
    PriceRole,
    describe_substance,
    expand_substance_codes,
)

console = Console()
app = typer.Typer(help="Browse mensa meals and generate plans.")


def _pkg_version() -> str:
    try:
        return version(APP_NAME)
    except PackageNotFoundError:
        return "0.0.1"


CLIMATE_STYLE = {
    "A": "bold green",
    "B": "green",
    "C": "yellow",
    "D": "dark_orange",
    "E": "bold red",
}
DIET_STYLE = {
    DietCategory.VEGAN: "bold green",
    DietCategory.VEGETARIAN: "green",
    DietCategory.FISH: "cyan",
    DietCategory.MEAT: "red",
    DietCategory.UNKNOWN: "dim",
}


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _parse_date_value(value: str) -> date | None:
    text = (value or "").strip().lower()
    if not text:
        return None
    if text == "today":
        return _today()
    if text == "tomorrow":
        return _today() + timedelta(days=1)

    try:
        return date.fromisoformat(text)
    except ValueError:
        pass

    try:
        day_text, month_text, year_text = text.split(".")
        return date(int(year_text), int(month_text), int(day_text))
    except (ValueError, TypeError):
        return None


def _meal_is_allowed(meal: Meal, diet: DietPreference) -> bool:
    if diet == DietPreference.ANY:
        return True
    from .model import preference_allows

    return preference_allows(diet, meal.diet_category)


def _meal_passes_exclusions(meal: Meal, excluded: Sequence[DietClass]) -> bool:
    if not excluded:
        return True
    return not (meal.diet & set(excluded))


def _meal_passes_avoid(meal: Meal, codes: Sequence[str]) -> bool:
    if not codes:
        return True
    return not any(code in set(expand_substance_codes(codes)) for code in meal.substances)


def _meal_passes_min_climate(meal: Meal, max_rating: str | None) -> bool:
    if max_rating is None:
        return True
    current = meal.climate_score
    if current is None:
        return True
    max_index = CLIMATE_RATINGS.index(max_rating.upper())
    return current <= max_index


def _meal_passes_max_price(meal: Meal, role: str, max_price: float | None) -> bool:
    if max_price is None:
        return True
    price = meal.price_for(role)
    return price is not None and price <= max_price


def _matches_kind(meal: Meal, kind: str) -> bool:
    if kind == "all":
        return True
    return meal.kind.value == kind


def _load_menu_or_file(file: Path | None, refresh: bool) -> object:
    if file is not None:
        return load_menu(file)
    return load_menu(use_cache=not refresh)


def _format_price(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}€"


def _format_climate(letter: str | None) -> str:
    return Text(letter or "–", style=CLIMATE_STYLE.get(letter or "", "dim"))


def _format_diet(meal: Meal) -> Text:
    label = ", ".join(sorted(c.value for c in meal.diet)) or "?"
    return Text(label, style=DIET_STYLE[meal.diet_category])


def _format_day(d: date) -> str:
    return d.strftime("%a %d.%m.%y")


def render_meals_table(
    meals: Sequence[Meal], *, role: PriceRole = PriceRole.STUDENT, title: str | None = None
) -> Table:
    table = Table(
        title=f"{title} · {role.value} prices" if title else None,
        show_header=True,
        header_style="bold cyan",
    )
    for col in (
        "ID",
        "Date",
        "Canteen",
        "Dish",
        "Diet",
        "Climate Score",
        f"Price - {role.value}",
        "Codes",
    ):
        table.add_column(col, overflow="fold")

    for meal in meals:
        table.add_row(
            str(meal.id),
            _format_day(meal.date),
            meal.canteen_name,
            meal.name,
            _format_diet(meal),
            _format_climate(meal.climate_rating),
            _format_price(meal.price_for(role)),
            ", ".join(meal.substances) or "-",
        )
    return table


def render_canteens_table(canteens: Sequence[object]) -> Table:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID")
    table.add_column("Name")
    for canteen in canteens:
        table.add_row(
            str(canteen.id),
            canteen.name,
        )
    return table


def render_allergens_table() -> Table:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Code")
    table.add_column("Name")
    table.add_column("Type")
    for code in SUBSTANCE_CATALOG:
        substance = SUBSTANCE_CATALOG[code]
        table.add_row(code, substance.name, "allergen" if substance.is_allergen else "additive")
    return table


def render_meal_panel(meal: Meal) -> Panel:
    lines = Text()
    lines.append(f"{meal.name}\n", style="bold")
    lines.append(
        f"{meal.canteen_name} · {meal.section or '—'} · {_format_day(meal.date)} · {meal.kind.value}\n"
    )
    lines.append("Diet: ")
    lines.append_text(_format_diet(meal))
    lines.append("   Climate: ")
    lines.append_text(_format_climate(meal.climate_rating))
    lines.append(
        f"\nPrices: student {_format_price(meal.price_student)} · staff {_format_price(meal.price_staff)}"
        f" · guest {_format_price(meal.price_guest)}\n"
    )
    if meal.notes:
        lines.append(f"Notes: {meal.notes}\n")
    lines.append("\nComponents\n", style="bold")
    for item in meal.items:
        substances = f" ({', '.join(item.substances)})" if item.substances else ""
        lines.append(f"  • {item.text_de}{substances}\n")
    if meal.substances:
        lines.append("\nAllergens & additives\n", style="bold")
        for substance in meal.substances:
            lines.append(f"  {substance:>4}  {describe_substance(substance)}\n")
    return Panel(lines, title=f"#{meal.id}", expand=False)


def _print_meal_rows(meals: Sequence[Meal], *, json_mode: bool = False) -> None:
    if json_mode:
        typer.echo(json.dumps([meal.to_dict() for meal in meals], ensure_ascii=False, indent=2))
        return
    if not meals:
        console.print("No meals found.")
        return
    console.print(render_meals_table(meals, role=PriceRole.STUDENT))


@app.callback()
def callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=lambda value: (
            (typer.echo(f"{APP_NAME} {_pkg_version()}") or (_ for _ in ()).throw(typer.Exit()))
            if value
            else None
        ),
        is_eager=True,
        help="Show version and exit.",
    ),
):
    return None


@app.command("meals", help="List meals for the next days, with filters.")
def meals_command(
    date: Annotated[
        list[str] | None,
        typer.Option("-d", "--date", help="YYYY-MM-DD, DD.MM.YYYY, today, tomorrow (repeatable)."),
    ] = None,
    canteen: Annotated[
        list[str] | None,
        typer.Option("-c", "--canteen", help="Canteen id or name part (repeatable)."),
    ] = None,
    diet: Annotated[
        DietPreference,
        typer.Option(help="Show only meals matching this diet."),
    ] = DietPreference.ANY,
    exclude: Annotated[
        list[DietClass] | None,
        typer.Option("-x", "--exclude", help="Hide meals with this class, e.g. pork (repeatable)."),
    ] = None,
    avoid: Annotated[
        list[str] | None,
        typer.Option(
            "-a", "--avoid", help="Hide meals containing this allergen/additive code (repeatable).."
        ),
    ] = None,
    max_price: Annotated[
        float | None,
        typer.Option(help="Maximum price in the chosen role."),
    ] = None,
    min_climate: Annotated[
        str | None,
        typer.Option(help="Worst acceptable Klimateller rating (A-E)."),
    ] = None,
    role: Annotated[
        PriceRole,
        typer.Option(help="Which price to show/filter on."),
    ] = PriceRole.STUDENT,
    kind: Annotated[str, typer.Option(help="main | side | breakfast | all")] = "main",
    json: Annotated[bool, typer.Option(help="Machine-readable output.")] = False,
    file: Annotated[
        Path | None,
        typer.Option(help="Read from a json file instead of calling the API."),
    ] = None,
    refresh: Annotated[bool, typer.Option(help="Ignore the cache and re-fetch.")] = False,
) -> None:
    menu = _load_menu_or_file(file, refresh)
    meals = list(menu.meals)

    if date:
        allowed = {value for token in date if (value := _parse_date_value(token)) is not None}
        meals = [meal for meal in meals if meal.date in allowed]

    if canteen:
        tokens = {token.lower() for token in canteen}
        meals = [
            meal
            for meal in meals
            if str(meal.canteen_id).lower() in tokens
            or any(token in meal.canteen_name.lower() for token in tokens)
        ]

    if diet != DietPreference.ANY:
        meals = [meal for meal in meals if _meal_is_allowed(meal, diet)]
    meals = [meal for meal in meals if _meal_passes_exclusions(meal, exclude or [])]
    meals = [meal for meal in meals if _meal_passes_avoid(meal, avoid or [])]
    meals = [meal for meal in meals if _meal_passes_max_price(meal, role.value, max_price)]
    meals = [meal for meal in meals if _meal_passes_min_climate(meal, min_climate)]
    meals = [meal for meal in meals if _matches_kind(meal, kind)]

    _print_meal_rows(meals, json_mode=json)


@app.command("canteens", help="List the canteens.")
def canteens_command(
    refresh: Annotated[bool, typer.Option(help="Ignore the cache and re-fetch.")] = False,
) -> None:
    canteens = load_canteens(use_cache=not refresh)
    if len(canteens) == 0:
        console.print("No canteens found.")
        return
    console.print(render_canteens_table(canteens))


@app.command("show", help="Show every detail of one meal (components, allergens, prices).")
def show_command(
    meal_id: Annotated[int, typer.Argument(help="ID number of the meal.")],
    file: Annotated[
        Path | None,
        typer.Option(help="Read a saved API response instead of calling the API."),
    ] = None,
    refresh: Annotated[bool, typer.Option(help="Ignore the cache and re-fetch.")] = False,
) -> None:
    menu = _load_menu_or_file(file, refresh)
    meal = next((item for item in menu.meals if item.id == meal_id), None)
    if meal is None:
        typer.echo(f"Meal {meal_id} not found.")
        raise typer.Exit(code=1)
    console.print(render_meal_panel(meal))


@app.command("allergens", help="Print the allergen / additive code table.")
def allergens_command() -> None:
    console.print(render_allergens_table())


cache_app = typer.Typer(help="Inspect or clear the local API cache.")


@cache_app.command("info")
def cache_info_command() -> None:
    info = cache.info()
    description = (
        f"Cache directory: [bold]{info['cache_dir']}[/]\n"
        f"Number of entries: [bold]{info['num_entries']}[/]\n"
        f"Total bytes: [bold]{info['total_bytes']}[/]"
    )
    console.print(description)


@cache_app.command("clear")
def cache_clear_command() -> None:
    count = cache.clear()
    typer.echo(f"Removed {count} cached file(s).")


@cache_app.command("refresh")
def cache_refresh_command() -> None:
    canteens = fetch_canteens_raw(use_cache=False)
    cache.set("canteens", canteens)
    for canteen in canteens:
        canteen_id = int(canteen.get("id", canteen.get("VERBRAUCHSORTNR", 0)))
        cache.set(f"meals:{canteen_id}", fetch_meals_raw(canteen_id, use_cache=False))
    typer.echo("Cache refreshed.")


app.add_typer(cache_app, name="cache")


def main() -> int:
    try:
        app()
    except MensaError as err:
        typer.echo(f"Encountered an error! {err}", err=True)
        return 1
    return 0


if __name__ == "__main__":
    main()
