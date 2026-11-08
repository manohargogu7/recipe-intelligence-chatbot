
import sqlite3
import re
import json
from pathlib import Path
from collections import defaultdict, Counter


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "database" / "recipe_database.db"

RESTRICTIONS = {
    "dairy": [
        "milk", "butter", "cheese", "cream", "yogurt",
        "yoghurt", "parmesan", "mozzarella", "ghee",
        "whey", "casein", "buttermilk", "ricotta"
    ],

    "peanut": [
        "peanut", "groundnut"
    ],

    "vegetarian": [
        "chicken", "beef", "pork", "lamb", "fish",
        "salmon", "tuna", "shrimp", "prawn", "crab",
        "bacon", "ham", "turkey", "anchovy", "gelatin"
    ]
}

# Explicit exceptions to avoid false dairy matches.
DAIRY_EXCEPTIONS = [
    "peanut butter",
    "almond butter",
    "cocoa butter",
    "butter beans",
    "butter lettuce",
    "coconut milk",
    "coconut cream",
    "oat milk",
    "soy milk",
    "almond milk",
    "cashew milk",
    "rice milk"
]

# Ingredient roles are approximate functional categories.
# Similar roles do not prove direct substitution equivalence.
ROLE_GROUPS = {
    "binding": [
        "egg", "banana", "applesauce",
        "flaxseed", "breadcrumbs"
    ],

    "moisture": [
    "cream", "heavy whipping cream",
    "milk", "buttermilk", "yogurt",
    "sour cream", "coconut milk",
    "coconut cream", "cashew cream",
    "broth"
],

    "fat": [
        "butter", "olive oil",
        "vegetable oil", "coconut oil",
        "margarine"
    ],

    "thickening": [
        "cornstarch", "flour",
        "potato starch", "arrowroot"
    ],

    "protein": [
        "chicken", "tofu", "beans",
        "lentils", "chickpeas", "mushrooms"
    ]
}

ALIASES = {
    "tomatoes": "tomato",
    "eggs": "egg",
    "onions": "onion",
    "garlic cloves": "garlic",
    "minced garlic": "garlic",
    "chick peas": "chickpeas",
    "spring onions": "green onion",
    "scallions": "green onion",
    "coriander leaves": "cilantro"
}

UNITS = {
    "cup", "cups",
    "tablespoon", "tablespoons", "tbsp",
    "teaspoon", "teaspoons", "tsp",
    "gram", "grams", "g",
    "kg", "ml", "l",
    "ounce", "ounces", "oz",
    "pound", "pounds", "lb", "lbs",
    "clove", "cloves",
    "piece", "pieces",
    "slice", "slices",
    "can", "cans",
    "package", "packages"
}

PREPARATION_WORDS = {
    "chopped", "diced", "minced", "sliced",
    "grated", "crushed", "peeled",
    "freshly", "finely", "roughly",
    "coarsely", "optional", "divided",
    "melted", "softened", "drained",
    "rinsed", "packed", "ground"
}


# ============================================================
# 2. DATABASE CONNECTION
# ============================================================

def get_connection():

    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_FILE}"
        )

    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row

    return connection


def get_columns(connection, table):

    return {
        row["name"]
        for row in connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


# ============================================================
# 3. INGREDIENT NORMALIZATION
# ============================================================

def normalize_ingredient(text):

    if not text:
        return ""

    text = text.casefold().strip()

    # Remove advertisement artifacts.
    text = re.sub(
        r"\badvertisement\b",
        " ",
        text
    )

    # Remove quantities at the beginning.
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

    # Remove preparation terms.
    words = [
        word for word in words
        if word.strip(".,") not in PREPARATION_WORDS
    ]

    text = " ".join(words)

    text = re.sub(
        r"[^a-z\s-]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    if text in ALIASES:
        return ALIASES[text]

    if text.endswith("ies") and len(text) > 4:
        text = text[:-3] + "y"

    elif text.endswith("s") and not text.endswith("ss"):
        text = text[:-1]

    return ALIASES.get(text, text)


def ingredient_matches(text, target):

    normalized_text = normalize_ingredient(text)
    normalized_target = normalize_ingredient(target)

    if not normalized_text or not normalized_target:
        return False

    # Match whole words or phrases, not partial words.
    pattern = (
        r"(?<!\w)"
        + re.escape(normalized_target)
        + r"(?!\w)"
    )

    return re.search(
        pattern,
        normalized_text
    ) is not None


# ============================================================
# 4. INGREDIENT ROLE IDENTIFICATION
# ============================================================

def identify_role(ingredient):

    normalized = normalize_ingredient(ingredient)

    for role, candidates in ROLE_GROUPS.items():

        for candidate in candidates:

            if ingredient_matches(normalized, candidate):
                return role

    return None


# ============================================================
# 5. DIETARY RESTRICTION CHECKING
# ============================================================

def check_restrictions(ingredient, restrictions):

    text = normalize_ingredient(ingredient)

    violations = []

    for restriction in restrictions:

        if restriction not in RESTRICTIONS:
            raise ValueError(
                f"Unsupported restriction: {restriction}"
            )

        # Known plant-based alternatives should not be
        # incorrectly classified as dairy.
        if restriction == "dairy":

            if any(
                ingredient_matches(text, exception)
                for exception in DAIRY_EXCEPTIONS
            ):
                continue

        for term in RESTRICTIONS[restriction]:

            if ingredient_matches(text, term):

                violations.append({
                    "restriction": restriction,
                    "matched_term": term,
                    "ingredient": ingredient
                })

    return violations


def validate_restrictions(restrictions):

    for restriction in restrictions:

        if restriction not in RESTRICTIONS:

            raise ValueError(
                f"Invalid restriction: {restriction}. "
                f"Choose from {list(RESTRICTIONS)}"
            )


# ============================================================
# 6. LOAD DATASET
# ============================================================

def load_dataset(connection):

    recipe_columns = get_columns(
        connection,
        "recipes"
    )

    ingredient_columns = get_columns(
        connection,
        "ingredients"
    )

    required_recipe_columns = {
        "recipe_id", "title"
    }

    required_ingredient_columns = {
        "recipe_id", "original_text"
    }

    if not required_recipe_columns.issubset(recipe_columns):

        raise RuntimeError(
            f"Unexpected recipes columns: {recipe_columns}"
        )

    if not required_ingredient_columns.issubset(
        ingredient_columns
    ):

        raise RuntimeError(
            f"Unexpected ingredients columns: "
            f"{ingredient_columns}"
        )

    instruction_column = next(
        (
            column for column in [
                "instructions",
                "instruction",
                "directions"
            ]
            if column in recipe_columns
        ),
        None
    )

    if instruction_column is None:

        raise RuntimeError(
            "No instructions column found in recipes table."
        )

    quality_column = (
        "quality_flags"
        if "quality_flags" in recipe_columns
        else None
    )

    query = f"""
        SELECT
            recipe_id,
            title,
            "{instruction_column}" AS instructions
            {', quality_flags' if quality_column else ''}
        FROM recipes
    """

    recipes = connection.execute(query).fetchall()

    order_column = (
        "position"
        if "position" in ingredient_columns
        else "rowid"
    )

    ingredient_rows = connection.execute(f"""
        SELECT recipe_id, original_text
        FROM ingredients
        ORDER BY recipe_id, {order_column}
    """).fetchall()

    ingredient_map = defaultdict(list)

    for row in ingredient_rows:

        if row["original_text"]:

            ingredient_map[row["recipe_id"]].append(
                row["original_text"]
            )

    return recipes, ingredient_map


# ============================================================
# 7. FIND ORIGINAL RECIPE
# ============================================================

def find_recipe(recipes, identifier):

    identifier = identifier.strip()

    # Exact recipe ID.
    for recipe in recipes:

        if recipe["recipe_id"] == identifier:
            return recipe

    # Exact title.
    exact = [
        recipe for recipe in recipes
        if recipe["title"]
        and recipe["title"].casefold() == identifier.casefold()
    ]

    if len(exact) == 1:
        return exact[0]

    if len(exact) > 1:

        print("\nMultiple recipes have this title.")

        for recipe in exact[:10]:

            print(
                recipe["title"],
                "|",
                recipe["recipe_id"]
            )

        return None

    # Partial title search.
    partial = [
        recipe for recipe in recipes
        if recipe["title"]
        and identifier.casefold() in recipe["title"].casefold()
    ]

    if len(partial) == 1:
        return partial[0]

    if partial:

        print("\nMultiple matches found. Use a recipe ID:")

        for recipe in partial[:10]:

            print(
                recipe["title"],
                "|",
                recipe["recipe_id"]
            )

        return None

    print("\nRecipe not found.")

    return None


# ============================================================
# 8. FIND RELATED RECIPES
# ============================================================

def title_tokens(title):

    ignored = {
        "and", "with", "the", "for",
        "of", "a", "an", "in", "style"
    }

    return {
        word for word in re.findall(
            r"[a-z]+",
            (title or "").casefold()
        )
        if word not in ignored and len(word) > 2
    }


def find_related_recipes(
    source_recipe,
    source_ingredients,
    unavailable,
    recipes,
    ingredient_map
):

    source_set = {
        normalize_ingredient(item)
        for item in source_ingredients
        if normalize_ingredient(item)
    }

    source_set.discard(
        normalize_ingredient(unavailable)
    )

    source_title = title_tokens(
        source_recipe["title"]
    )

    related = []

    for recipe in recipes:

        if recipe["recipe_id"] == source_recipe["recipe_id"]:
            continue

        candidate_raw = ingredient_map.get(
            recipe["recipe_id"], []
        )

        candidate_set = {
            normalize_ingredient(item)
            for item in candidate_raw
            if normalize_ingredient(item)
        }

        if not candidate_set:
            continue

        shared = source_set & candidate_set
        union = source_set | candidate_set

        ingredient_similarity = (
            len(shared) / len(union)
            if union else 0
        )

        candidate_title = title_tokens(
            recipe["title"]
        )

        title_union = source_title | candidate_title

        title_similarity = (
            len(source_title & candidate_title)
            / len(title_union)
            if title_union else 0
        )

        score = (
            ingredient_similarity * 0.75
            + title_similarity * 0.25
        )

        if len(shared) >= 1 or title_similarity >= 0.25:

            related.append({
                "recipe": recipe,
                "ingredients": candidate_raw,
                "score": score,
                "shared": shared
            })

    related.sort(
        key=lambda item: (
            -item["score"],
            item["recipe"]["recipe_id"]
        )
    )

    return related[:50]


# ============================================================
# 9. PRESERVE QUANTITY WHEN PROPOSING REPLACEMENT
# ============================================================

def extract_quantity_prefix(ingredient):

    text = ingredient.strip()

    # Preserve the original leading quantity and unit.
    pattern = (
        r"^("
        r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:cups?|tablespoons?|tbsp|teaspoons?|tsp|"
        r"grams?|g|kg|ml|liters?|litres?|ounces?|oz|"
        r"pounds?|lbs?|cloves?|cans?|packages?)?"
        r"\s*"
        r")"
    )

    match = re.match(
        pattern,
        text,
        flags=re.IGNORECASE
    )

    return match.group(1) if match else ""


def make_replacement_line(original, candidate):

    prefix = extract_quantity_prefix(original)

    if prefix:
        return (
            f"{prefix}{candidate} "
            "[quantity requires verification]"
        )

    return (
        f"{candidate} "
        "[quantity requires verification]"
    )


# ============================================================
# 10. EVIDENCE-BASED SUBSTITUTION
# ============================================================

def suggest_substitutions(
    recipe_identifier,
    unavailable,
    restrictions=None
):

    restrictions = restrictions or []

    validate_restrictions(restrictions)

    connection = get_connection()

    try:

        recipes, ingredient_map = load_dataset(
            connection
        )

        source_recipe = find_recipe(
            recipes,
            recipe_identifier
        )

        if source_recipe is None:
            return None

        original_ingredients = ingredient_map.get(
            source_recipe["recipe_id"],
            []
        )

        if not original_ingredients:

            print("\nOriginal recipe has no ingredient data.")

            return None

        # Identify the exact source ingredient entries.
        target_entries = [
            ingredient
            for ingredient in original_ingredients
            if ingredient_matches(
                ingredient,
                unavailable
            )
        ]

        if not target_entries:

            print(
                "\nThe requested unavailable ingredient "
                "was not found in this recipe."
            )

            print("\nAvailable ingredients:")

            for ingredient in original_ingredients:
                print("-", ingredient)

            return None

        role = identify_role(unavailable)

        print("\n" + "=" * 65)
        print("EVIDENCE-BASED RECIPE SUBSTITUTION")
        print("=" * 65)

        print("\nOriginal recipe:", source_recipe["title"])

        print("Recipe ID:", source_recipe["recipe_id"])

        print("Unavailable ingredient:", unavailable)

        print("Matching source entries:", len(target_entries))

        print("Identified functional role:", role or "Unknown")

        # Find related recipes.
        related = find_related_recipes(
            source_recipe,
            original_ingredients,
            unavailable,
            recipes,
            ingredient_map
        )

        # Build evidence from related recipes.
        evidence = defaultdict(dict)

        source_normalized = {
            normalize_ingredient(item)
            for item in original_ingredients
        }

        if role:

            for item in related:

                for ingredient in item["ingredients"]:

                    candidate = normalize_ingredient(
                        ingredient
                    )

                    if not candidate:
                        continue

                    if candidate in source_normalized:
                        continue

                    candidate_role = identify_role(
                        candidate
                    )

                    if candidate_role != role:
                        continue

                    violations = check_restrictions(
                        candidate,
                        restrictions
                    )

                    if violations:
                        continue

                    recipe_id = item["recipe"]["recipe_id"]

                    evidence[candidate][recipe_id] = {
                        "recipe_id": recipe_id,
                        "title": item["recipe"]["title"],
                        "similarity": round(item["score"], 3)
                    }

        # Rank candidates by repeated local evidence.
        ranked = sorted(
            evidence.items(),
            key=lambda item: (
                -len(item[1]),
                item[0]
            )
        )

        print("\n1. LOCAL DATASET EVIDENCE")
        print("-" * 50)

        print("Related recipes examined:", len(related))

        if not ranked:

            print(
                "No role-compatible alternative was supported "
                "by the retrieved local recipes."
            )

        else:

            print("\nPotential alternatives:")

            for candidate, source_map in ranked[:5]:

                sources = list(source_map.values())

                print("\nCandidate:", candidate)

                print(
                    "Supporting recipe count:",
                    len(sources)
                )

                print(
                    "Evidence strength:",
                    "Repeated examples"
                    if len(sources) >= 2
                    else "Weak - one example"
                )

                for source in sources[:3]:

                    print(
                        "Supporting recipe:",
                        source["title"]
                    )

                    print(
                        "Supporting ID:",
                        source["recipe_id"]
                    )

        # ----------------------------------------------------
        # 2. UPDATED INGREDIENT LIST
        # ----------------------------------------------------

        best_candidate = (
            ranked[0][0]
            if ranked
            else None
        )

        updated_ingredients = []

        for ingredient in original_ingredients:

            if ingredient_matches(
                ingredient,
                unavailable
            ):

                if best_candidate:

                    updated_ingredients.append(
                        make_replacement_line(
                            ingredient,
                            best_candidate
                        )
                    )

                else:

                    updated_ingredients.append(
                        f"[REPLACEMENT NEEDED: {ingredient}]"
                    )

            else:

                updated_ingredients.append(ingredient)

        print("\n2. UPDATED INGREDIENT LIST")
        print("-" * 50)

        for ingredient in updated_ingredients:
            print("-", ingredient)

        # ----------------------------------------------------
        # 3. REVISED INSTRUCTIONS
        # ----------------------------------------------------

        instructions = (
            source_recipe["instructions"] or ""
        )

        print("\n3. REVISED INSTRUCTIONS")
        print("-" * 50)

        if instructions:
            print(instructions)
        else:
            print("No instructions available.")

        if best_candidate:

            print(
                "\nADAPTATION NOTE:"
            )

            print(
                f"Consider replacing {unavailable} "
                f"with {best_candidate}."
            )

            print(
                "Apply the replacement at the corresponding "
                "preparation step."
            )

            print(
                "The original instructions have not been "
                "automatically rewritten because cooking "
                "method and timing may need adjustment."
            )

        # ----------------------------------------------------
        # 4. TRADE-OFFS AND LIMITATIONS
        # ----------------------------------------------------

        print("\n4. EXPECTED EFFECTS AND LIMITATIONS")
        print("-" * 50)

        if best_candidate:

            print(
                "The candidate shares a broad functional "
                "ingredient role with the unavailable ingredient."
            )

            print(
                "Actual taste, texture and cooking performance "
                "have not been experimentally verified."
            )

            print(
                "The original quantity is not assumed to be "
                "equivalent to the replacement quantity."
            )

            print(
                "Check product labels and cross-contact risks "
                "when dealing with allergies."
            )

        else:

            print(
                "Insufficient local evidence for a supported "
                "replacement."
            )

            print(
                "Do not treat an unsupported ingredient as "
                "a safe substitute."
            )

        print("\n" + "=" * 65)
        print("SUBSTITUTION ANALYSIS COMPLETED")
        print("=" * 65)

        return {
            "recipe_id": source_recipe["recipe_id"],
            "title": source_recipe["title"],
            "unavailable": unavailable,
            "role": role,
            "alternatives": [
                {
                    "ingredient": candidate,
                    "supporting_recipes": list(
                        source_map.values()
                    )
                }
                for candidate, source_map in ranked[:5]
            ],
            "updated_ingredients": updated_ingredients,
            "revised_instructions": instructions
        }

    finally:
        connection.close()


# ============================================================
# 11. COMMAND-LINE INTERFACE
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print("RECIPE SUBSTITUTION ENGINE")
    print("=" * 65)

    recipe_identifier = input(
        "\nEnter recipe title or recipe ID: "
    ).strip()

    unavailable = input(
        "\nEnter unavailable ingredient: "
    ).strip()

    restrictions_input = input(
        "\nEnter hard restrictions "
        "(dairy, peanut, vegetarian), "
        "comma separated; Enter for none: "
    ).strip()

    restrictions = [
        item.strip().lower()
        for item in restrictions_input.split(",")
        if item.strip()
    ]

    try:

        suggest_substitutions(
            recipe_identifier=recipe_identifier,
            unavailable=unavailable,
            restrictions=restrictions
        )

    except (
        ValueError,
        sqlite3.Error,
        FileNotFoundError,
        RuntimeError
    ) as error:

        print("\nERROR:", error)
