# Mensa

Mensa is a command-line tool for browsing meals from Studierendenwerk Dortmund and building optimized multi-day meal plans. It retrieves current canteen menus, filters meals by dietary needs and allergens, and uses an integer linear programming model to balance price and climate impact.

## Functions

- Browse canteens and upcoming meals with prices, dietary labels, climate ratings, ingredients, and allergen/additive codes.
- Filter menus by date, canteen, diet, excluded ingredients, price, and climate rating; emit meal listings as JSON.
- Optimize a plan across multiple days with total and per-day budgets, optional breakfast or sides, category repetition limits, and price/climate preferences.
- Load menu data from a local JSON file instead of making live API requests. Responses from the Studentwerk API can also be cached locally.

The planner's objective and constraints are described in [ILP.md](ILP.md).

## Get Started

Requirements: Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

From the project directory, install the package and its dependencies:

```sh
uv sync
uv run mensa --help
```

The first live menu request needs an internet connection to reach the Studierendenwerk Dortmund API.

### Browse menus

```sh
# List available canteens and their IDs
uv run mensa canteens

# Show today's vegan main dishes
uv run mensa meals --date today --diet vegan

# Filter menu and save it to JSON
uv run mensa meals --date tomorrow --kind all --max-price 5 --json > meals.json

# Show a meal's components, prices, and allergen/additive details
uv run mensa show 12345

# Print the supported allergen and additive codes
uv run mensa allergens
```

Dates accept `YYYY-MM-DD`, `DD.MM.YYYY`, `today`, or `tomorrow`. Repeat `--date`, `--canteen`, and `--avoid` to provide multiple values. Price roles are `student`, `staff`, and `guest`; diet choices are `any`, `pescatarian`, `vegetarian`, and `vegan`.

### Plan meals

```sh
uv run mensa plan \
        --diet vegetarian \
        --file examples/demo.json \
        --budget 15 \
        --role staff \
        --max-category-repeat vegan=2
```

The planner selects one main meal for each requested date and minimizes the weighted price and climate score. Use `uv run mensa plan --help` to see options for requiring breakfast or a side, setting climate score limits, excluding meal IDs, or applying nutrition constraints. Nutrition constraints require nutrition values in the input data.

### Use saved menu data

The `meals`, `plan`, and `show` commands accept `--file path/to/menu.json`. The file may contain a Studentwerk API response or normalized menu data with `canteens` and `meals` arrays. This is useful for offline runs and reproducible input.

API data is cached by default. Inspect or manage the cache with:

```sh
uv run mensa cache info
uv run mensa cache refresh
uv run mensa cache clear
```

## Help

- Run `uv run mensa --help` or `uv run mensa <command> --help` for command documentation.
- See [ILP.md](ILP.md) for the meal-planning model.
- For a bug report or usage question, open an issue in the project's Github page.

## Maintainers and Contributions

Contributions are welcome as pull requests. For changes, install the development dependencies, run the tests, and check formatting/lint:

```sh
uv sync --group dev
uv run pytest
uv run ruff check .
```

