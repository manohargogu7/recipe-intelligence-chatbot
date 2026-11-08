
import sqlite3
import re
import json
from pathlib import Path
from collections import defaultdict


# =====================================================
# CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "database" / "recipe_database.db"

RESTRICTIONS = {
    "dairy": [
        "milk", "butter", "cheese", "cream", "yogurt",
        "yoghurt", "parmesan", "mozzarella", "ghee",
        "whey", "casein", "buttermilk", "ricotta"
    ],
    "peanut": ["peanut", "groundnut"],
    "vegetarian": [
        "chicken", "beef", "pork", "lamb", "fish",
        "salmon", "tuna", "shrimp", "prawn", "crab",
        "bacon", "ham", "turkey", "anchovy", "gelatin"
    ]
}

UNITS = {
    "cups", "cup", "tablespoons", "tablespoon", "tbsp",
    "teaspoons", "teaspoon", "tsp", "grams", "gram",
    "g", "kg", "kilograms", "ml", "milliliters",
    "millilitres", "liters", "litres", "oz", "ounces",
    "pounds", "lb", "lbs", "cloves", "clove",
    "pieces", "piece", "slices", "slice", "cans", "can",
    "packages", "package", "pinches", "pinch"
}

PREPARATION_WORDS = {
    "chopped", "diced", "minced", "sliced", "grated",
    "crushed", "ground", "peeled", "freshly", "fresh",
    "finely", "roughly", "coarsely", "optional",
    "divided", "cooked", "boiled", "roasted",
    "melted", "softened", "drained", "rinsed",
    "packed", "boneless", "skinless"
}

ALIASES = {
    "tomatoes": "tomato",
    "red onions": "onion",
    "yellow onions": "onion",
    "white onions": "onion",
    "garlic cloves": "garlic",
    "minced garlic": "garlic",
    "spring onions": "green onion",
    "scallions": "green onion",
    "cilantro leaves": "cilantro",
    "coriander leaves": "cilantro",
    "chick peas": "chickpeas"
}


# =====================================================
# DATABASE
# =====================================================

def connect_db():
    if not DB_FILE.exists():
        raise FileNotFoundError(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# INGREDIENT NORMALIZATION
# =====================================================

def normalize_ingredient(text):

    if not text:
        return ""

    text = text.lower().strip()

    # Remove advertisement artifacts.
    text = re.sub(r"\badvertisement\b", "", text)

    # Remove leading quantities.
    text = re.sub(
        r"^\s*\d+\s+\d+/\d+\s*",
        "",
        text
    )

    text = re.sub(
        r"^\s*\d+/\d+\s*",
        "",
        text
    )

    text = re.sub(
        r"^\s*\d+(?:\.\d+)?\s*",
        "",
        text
    )

    # Remove measurement units.
    words = text.split()

    while words and words[0].strip(".,") in UNITS:
        words.pop(0)

    # Remove preparation descriptions.
    words = [
        word for word in words
        if word.strip(".,") not in PREPARATION_WORDS
    ]

    text = " ".join(words)

    text = re.sub(r"[^a-z\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if text in ALIASES:
        text = ALIASES[text]

    # Basic singular normalization.
    if text.endswith("ies") and len(text) > 4:
        text = text[:-3] + "y"
    elif text.endswith("s") and not text.endswith("ss"):
        text = text[:-1]

    return ALIASES.get(text, text)


# =====================================================
# RESTRICTION CHECKING
# =====================================================

def get_violations(ingredients, restrictions):

    violations = []

    for ingredient in ingredients:

        text = ingredient.lower()

        for restriction in restrictions:

            for term in RESTRICTIONS[restriction]:

                pattern = (
                    r"(?<!\w)" +
                    re.escape(term) +
                    r"(?!\w)"
                )

                if re.search(pattern, text):

                    # Exclude known non-dairy phrases.
                    if restriction == "dairy":
                        exceptions = [
                            "butter beans",
                            "peanut butter",
                            "almond butter",
                            "cocoa butter",
                            "coconut milk",
                            "coconut cream",
                            "oat milk",
                            "soy milk",
                            "almond milk"
                        ]

                        if any(
                            exception in text
                            for exception in exceptions
                        ):
                            continue

                    violations.append({
                        "restriction": restriction,
                        "ingredient": ingredient,
                        "matched_term": term
                    })

    return violations


# =====================================================
# INSTRUCTION STEP COUNTING
# =====================================================

def count_steps(instructions):

    if not instructions or not instructions.strip():
        return None

    lines = [
        line.strip()
        for line in instructions.splitlines()
        if line.strip()
    ]

    if len(lines) > 1:
        return len(lines)

    sentences = re.split(
        r"(?<=[.!?])\s+(?=[A-Z0-9])",
        instructions.strip()
    )

    return max(1, len(sentences))


# =====================================================
# RECIPE MATCHING ENGINE
# =====================================================

def match_recipes(
    available_ingredients,
    restrictions=None,
    max_steps=None,
    limit=5
):

    restrictions = restrictions or []

    for restriction in restrictions:
        if restriction not in RESTRICTIONS:
            raise ValueError(
                f"Unsupported restriction: {restriction}"
            )

    if max_steps is not None and max_steps < 1:
        raise ValueError("Maximum steps must be positive.")

    available = {
        normalize_ingredient(item)
        for item in available_ingredients
        if normalize_ingredient(item)
    }

    if not available:
        raise ValueError("Provide at least one valid ingredient.")

    conn = connect_db()

    try:

        # Load ALL recipes.
        recipes = conn.execute("""
            SELECT recipe_id, title, instructions, quality_flags
            FROM recipes
            ORDER BY recipe_id
        """).fetchall()

        # Load ALL ingredient records.
        rows = conn.execute("""
            SELECT recipe_id, original_text
            FROM ingredients
            ORDER BY recipe_id, position
        """).fetchall()

        ingredient_map = defaultdict(list)

        for row in rows:
            if row["original_text"]:
                ingredient_map[row["recipe_id"]].append(
                    row["original_text"]
                )

        eligible = []
        alternatives = []
        unknown = []

        for recipe in recipes:

            recipe_id = recipe["recipe_id"]

            original_ingredients = ingredient_map[recipe_id]

            try:
                flags = json.loads(
                    recipe["quality_flags"] or "{}"
                )
            except (json.JSONDecodeError, TypeError):
                flags = {}

            if (
                not original_ingredients
                or flags.get("missing_ingredients", False)
            ):
                unknown.append(recipe_id)
                continue

            normalized = {
                normalize_ingredient(item)
                for item in original_ingredients
                if normalize_ingredient(item)
            }

            matched = available & normalized

            missing = available - normalized

            extra = normalized - available

            steps = count_steps(recipe["instructions"])

            violations = get_violations(
                original_ingredients,
                restrictions
            )

            # Hard constraints must never be relaxed.
            if violations:
                alternatives.append({
                    "recipe_id": recipe_id,
                    "title": recipe["title"],
                    "violations": violations
                })
                continue

            if max_steps is not None:
                if steps is None or steps > max_steps:
                    continue

            if not matched:
                continue

            # Explainable score.
            ingredient_coverage = (
                len(matched) / len(available)
            ) * 60

            recipe_coverage = (
                len(matched) / len(normalized)
            ) * 30

            extra_penalty = min(
                len(extra) * 2,
                20
            )

            step_bonus = (
                max(0, 10 - steps)
                if steps is not None
                else 0
            )

            score = max(
                0,
                ingredient_coverage
                + recipe_coverage
                + step_bonus
                - extra_penalty
            )

            eligible.append({

                "recipe_id": recipe_id,

                "title": recipe["title"],

                "score": round(score, 2),

                "matched": sorted(matched),

                "missing": sorted(missing),

                "extra": sorted(extra),

                "steps": steps,

                "quantity_verified": False

            })

        # Rank by score, then fewer additional ingredients,
        # then fewer instruction steps.
        eligible.sort(
            key=lambda item: (
                -item["score"],
                len(item["extra"]),
                item["steps"] if item["steps"] is not None else float("inf"),
                item["recipe_id"]
            )
        )

        return {
            "available": sorted(available),
            "restrictions": restrictions,
            "max_steps": max_steps,
            "total_recipes": len(recipes),
            "eligible_count": len(eligible),
            "eligible": eligible[:limit],
            "unknown_count": len(unknown),
            "alternatives": alternatives[:5]
        }

    finally:
        conn.close()


# =====================================================
# DISPLAY RESULTS
# =====================================================

def display_results(results):

    print("\n" + "=" * 60)
    print("INGREDIENT-BASED RECIPE MATCHING")
    print("=" * 60)

    print("Dataset recipes:", results["total_recipes"])

    print("Available ingredients:", results["available"])

    print("Hard restrictions:", results["restrictions"])

    print("Maximum steps:", results["max_steps"])

    print("Eligible matching recipes:", results["eligible_count"])

    print("Unknown recipes skipped:", results["unknown_count"])

    if not results["eligible"]:

        print("\nNO ELIGIBLE MATCH FOUND.")

        print("\nClosest alternatives (not eligible):")

        for recipe in results["alternatives"]:

            print("\n", recipe["title"])

            print("Recipe ID:", recipe["recipe_id"])

            print("Constraint violations:")

            for violation in recipe["violations"]:
                print(
                    violation["restriction"],
                    "->",
                    violation["ingredient"]
                )

        return

    print("\nRANKED RECIPE MATCHES")

    for rank, recipe in enumerate(
        results["eligible"],
        start=1
    ):

        print("\n" + "-" * 50)

        print("Rank:", rank)

        print("Title:", recipe["title"])

        print("Recipe ID:", recipe["recipe_id"])

        print("Match score:", recipe["score"])

        print("Matched ingredients:", recipe["matched"])

        print("Unused available ingredients:", recipe["missing"])

        print("Additional required ingredients:", recipe["extra"])

        print("Instruction steps:", recipe["steps"])

        print(
            "Quantity sufficiency verified:",
            recipe["quantity_verified"]
        )

    print("\nRanking formula:")
    print("60% available ingredient coverage")
    print("30% recipe ingredient coverage")
    print("Up to 10 points for fewer steps")
    print("Penalty of 2 points per additional ingredient,")
    print("capped at 20 points.")


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RECIPE INGREDIENT MATCHER")
    print("=" * 60)

    ingredients_input = input(
        "\nEnter available ingredients separated by commas:\n"
    )

    available = [
        item.strip()
        for item in ingredients_input.split(",")
        if item.strip()
    ]

    restrictions_input = input(
        "\nHard restrictions (dairy, peanut, vegetarian), "
        "comma separated; Enter for none:\n"
    )

    restrictions = [
        item.strip().lower()
        for item in restrictions_input.split(",")
        if item.strip()
    ]

    steps_input = input(
        "\nMaximum instruction steps (Enter for no limit): "
    ).strip()

    max_steps = (
        int(steps_input)
        if steps_input
        else None
    )

    try:

        results = match_recipes(
            available_ingredients=available,
            restrictions=restrictions,
            max_steps=max_steps,
            limit=5
        )

        display_results(results)

    except (ValueError, sqlite3.Error, FileNotFoundError) as error:
        print("\nError:", error)
