
import sqlite3
import re
import statistics
from collections import Counter
from pathlib import Path


# =====================================================
# CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "database" / "recipe_database.db"


def connect_db():
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# INGREDIENT NORMALIZATION
# =====================================================

def normalize_ingredient(name):
    if not name:
        return ""

    name = name.lower().strip()
    name = re.sub(r"\s+", " ", name)

    aliases = {
        "garlic cloves": "garlic",
        "minced garlic": "garlic",
        "garlic powder": "garlic",
        "onion powder": "onion",
        "yellow onions": "onion",
        "red onions": "onion",
        "green onions": "green onion",
        "spring onions": "green onion",
        "tomatoes": "tomato",
        "tomato paste": "tomato",
        "tomato sauce": "tomato"
    }

    if name in aliases:
        return aliases[name]

    return name


def contains_ingredient(name, target):
    name = normalize_ingredient(name)

    if target == "garlic":
        return bool(re.search(r"\bgarlic\b", name))

    if target == "onion":
        return bool(re.search(r"\bonion\b", name))

    if target == "tomato":
        return bool(re.search(r"\btomatoes?\b", name))

    return bool(re.search(r"\b" + re.escape(target) + r"\b", name))


# =====================================================
# INSTRUCTION STEP COUNTING
# =====================================================

def count_instruction_steps(instructions):

    if not instructions or not instructions.strip():
        return None

    instructions = instructions.strip()

    # Prefer separate non-empty lines.
    lines = [
        line.strip()
        for line in instructions.splitlines()
        if line.strip()
    ]

    if len(lines) > 1:
        return len(lines)

    # For a single paragraph, count sentences.
    # This is an estimated step-counting rule.
    sentences = re.split(
        r"(?<=[.!?])\s+(?=[A-Z0-9])",
        instructions
    )

    sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]

    return max(1, len(sentences))


# =====================================================
# LOAD DATA
# =====================================================

def load_dataset(conn):

    recipe_columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(recipes)"
        ).fetchall()
    }

    ingredient_columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(ingredients)"
        ).fetchall()
    }

    required_recipe_columns = {
        "recipe_id", "title"
    }

    required_ingredient_columns = {
        "recipe_id", "original_text"
    }

    if not required_recipe_columns.issubset(recipe_columns):
        raise RuntimeError(
            f"Unexpected recipes schema: {recipe_columns}"
        )

    if not required_ingredient_columns.issubset(
        ingredient_columns
    ):
        raise RuntimeError(
            f"Unexpected ingredients schema: {ingredient_columns}"
        )

    instruction_column = next(
        (
            col for col in
            ["instructions", "instruction", "directions"]
            if col in recipe_columns
        ),
        None
    )

    if instruction_column is None:
        raise RuntimeError(
            "No instructions column found in recipes table. "
            f"Available columns: {recipe_columns}"
        )

    normalized_column = (
        "normalized_name"
        if "normalized_name" in ingredient_columns
        else None
    )

    recipes = conn.execute(
        f"""
        SELECT recipe_id, title, "{instruction_column}" AS instructions
        FROM recipes
        """
    ).fetchall()

    ingredients = conn.execute(
        """
        SELECT recipe_id, original_text
        """
        + (
            ", normalized_name"
            if normalized_column
            else ""
        )
        + """
        FROM ingredients
        """
    ).fetchall()

    return recipes, ingredients


# =====================================================
# MAIN ANALYTICS
# =====================================================

def run_analytics():

    conn = connect_db()

    try:

        recipes, ingredients = load_dataset(conn)

        total_recipes = len(recipes)

        recipe_ingredients = {}
        ingredient_frequency = Counter()

        garlic_recipes = set()
        onion_recipes = set()
        tomato_recipes = set()

        # Process every ingredient record.
        for item in ingredients:

            recipe_id = item["recipe_id"]

            original = item["original_text"]

            normalized = (
                item["normalized_name"]
                if "normalized_name" in item.keys()
                else None
            )

            ingredient_name = (
                normalized.strip()
                if normalized and normalized.strip()
                else original
            )

            if not ingredient_name:
                continue

            recipe_ingredients.setdefault(
                recipe_id, []
            ).append(ingredient_name)

            canonical = normalize_ingredient(
                ingredient_name
            )

            # Count ingredient frequency by recipe,
            # not by duplicate ingredient rows.
            if contains_ingredient(canonical, "garlic"):
                garlic_recipes.add(recipe_id)

            if contains_ingredient(canonical, "onion"):
                onion_recipes.add(recipe_id)

            if contains_ingredient(canonical, "tomato"):
                tomato_recipes.add(recipe_id)

        # Count each ingredient at most once per recipe.
        for recipe_id, names in recipe_ingredients.items():

            unique_names = set()

            for name in names:

                canonical = normalize_ingredient(name)

                if canonical:
                    unique_names.add(canonical)

            ingredient_frequency.update(unique_names)

        # -------------------------------------------------
        # 1. TOTAL RECIPE COUNT
        # -------------------------------------------------

        print("\n" + "=" * 60)
        print("RECIPE ANALYTICS REPORT")
        print("=" * 60)

        print("\n1. DATASET SUMMARY")
        print("-" * 45)

        print("Total recipes:", total_recipes)
        print("Recipes with ingredient records:",
              len(recipe_ingredients))
        print("Ingredient records:", len(ingredients))

        # -------------------------------------------------
        # 2. MOST COMMON INGREDIENTS
        # -------------------------------------------------

        print("\n2. TOP 15 COMMON INGREDIENTS")
        print("-" * 45)

        for name, count in ingredient_frequency.most_common(15):
            percentage = (
                count / total_recipes * 100
                if total_recipes else 0
            )

            print(
                f"{name}: {count} recipes "
                f"({percentage:.2f}%)"
            )

        # -------------------------------------------------
        # 3. AVERAGE AND MEDIAN INGREDIENT COUNTS
        # -------------------------------------------------

        print("\n3. INGREDIENT COUNT STATISTICS")
        print("-" * 45)

        counts = [
            len(names)
            for names in recipe_ingredients.values()
        ]

        if counts:

            print("Recipes analyzed:", len(counts))

            print(
                "Average ingredients:",
                round(statistics.mean(counts), 2)
            )

            print(
                "Median ingredients:",
                statistics.median(counts)
            )

            print(
                "Minimum ingredients:",
                min(counts)
            )

            print(
                "Maximum ingredients:",
                max(counts)
            )

        else:
            print("No ingredient records available.")

        # -------------------------------------------------
        # 4. GARLIC AND ONION STATISTICS
        # -------------------------------------------------

        print("\n4. RECIPES CONTAINING GARLIC AND ONION")
        print("-" * 45)

        both = garlic_recipes & onion_recipes

        percentage = (
            len(both) / total_recipes * 100
            if total_recipes else 0
        )

        print("Garlic recipes:", len(garlic_recipes))
        print("Onion recipes:", len(onion_recipes))
        print("Recipes containing both:", len(both))

        print("Denominator:", total_recipes)

        print(
            f"Percentage of dataset: {percentage:.2f}%"
        )

        print(
            "Calculation: both / total recipes * 100"
        )

        # -------------------------------------------------
        # 5. TOMATO RECIPES WITH FEWEST INSTRUCTION STEPS
        # -------------------------------------------------

        print("\n5. FIVE TOMATO RECIPES WITH FEWEST STEPS")
        print("-" * 45)

        recipe_lookup = {
            recipe["recipe_id"]: recipe
            for recipe in recipes
        }

        ranked = []

        for recipe_id in tomato_recipes:

            recipe = recipe_lookup.get(recipe_id)

            if recipe is None:
                continue

            steps = count_instruction_steps(
                recipe["instructions"]
            )

            if steps is not None:

                ranked.append({
                    "recipe_id": recipe_id,
                    "title": recipe["title"],
                    "steps": steps
                })

        ranked.sort(
            key=lambda item: (
                item["steps"],
                item["recipe_id"]
            )
        )

        print(
            "Tomato recipes with available instructions:",
            len(ranked)
        )

        print(
            "Step-count rule: non-empty lines; "
            "single paragraphs are split into sentences."
        )

        for index, recipe in enumerate(ranked[:5], start=1):

            print(f"\nRank: {index}")

            print("Title:", recipe["title"])

            print("Recipe ID:", recipe["recipe_id"])

            print("Instruction steps:", recipe["steps"])

        print("\n" + "=" * 60)
        print("ANALYTICS COMPLETED")
        print("=" * 60)

    finally:
        conn.close()


# =====================================================
# RUN PROGRAM
# =====================================================

if __name__ == "__main__":
    run_analytics()
