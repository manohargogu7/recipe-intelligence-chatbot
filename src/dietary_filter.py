
import sqlite3
import json
import re
from pathlib import Path


# =====================================================
# 1. PROJECT CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DB_FILE = BASE_DIR / "database" / "recipe_database.db"


# =====================================================
# 2. DIETARY RESTRICTIONS
# =====================================================

RESTRICTIONS = {

    "dairy": [
        "milk",
        "butter",
        "cheese",
        "cream",
        "yogurt",
        "yoghurt",
        "parmesan",
        "mozzarella",
        "ghee",
        "whey",
        "casein",
        "buttermilk",
        "ricotta",
        "cheddar",
        "feta",
        "condensed milk",
        "evaporated milk"
    ],

    "peanut": [
        "peanut",
        "groundnut"
    ],

    "vegetarian": [
        "chicken",
        "beef",
        "pork",
        "lamb",
        "fish",
        "salmon",
        "tuna",
        "shrimp",
        "prawn",
        "crab",
        "bacon",
        "ham",
        "turkey",
        "anchovy",
        "gelatin",
        "fish sauce",
        "oyster sauce",
        "beef broth",
        "chicken broth"
    ]
}


# Plant-based or otherwise non-dairy phrases.
DAIRY_EXCEPTIONS = [
    "butter beans",
    "butter lettuce",
    "peanut butter",
    "almond butter",
    "cocoa butter",
    "vegan butter",
    "coconut cream",
    "coconut milk",
    "oat milk",
    "soy milk",
    "almond milk",
    "cashew milk",
    "rice milk",
    "vegan cream",
    "non dairy cream",
    "non-dairy cream"
]


# =====================================================
# 3. DATABASE CONNECTION
# =====================================================

def get_connection():

    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_FILE}"
        )

    connection = sqlite3.connect(DB_FILE)

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# =====================================================
# 4. INGREDIENT KEYWORD MATCHING
# =====================================================

def contains_term(text, term):

    pattern = (
        r"(?<!\w)"
        + re.escape(term)
        + r"(?!\w)"
    )

    return re.search(
        pattern,
        text,
        re.IGNORECASE
    ) is not None


# =====================================================
# 5. FIND DIETARY VIOLATIONS
# =====================================================

def find_violations(ingredients, restrictions):

    violations = []

    for original_text in ingredients:

        text = original_text.casefold()

        for restriction in restrictions:

            searchable_text = text

            # Remove known non-dairy exceptions.
            if restriction == "dairy":

                for exception in DAIRY_EXCEPTIONS:

                    searchable_text = re.sub(
                        re.escape(exception),
                        " ",
                        searchable_text,
                        flags=re.IGNORECASE
                    )

            keywords = RESTRICTIONS[restriction]

            for keyword in keywords:

                if contains_term(
                    searchable_text,
                    keyword
                ):

                    violations.append({

                        "restriction": restriction,

                        "matched_term": keyword,

                        "original_ingredient": original_text

                    })

    return violations


# =====================================================
# 6. SEARCH AND FILTER RECIPES
# =====================================================

def filter_recipes(
    keyword,
    restrictions=None,
    limit=10
):

    restrictions = restrictions or []

    keyword = keyword.strip().casefold()

    if not keyword:
        raise ValueError(
            "Search keyword cannot be empty."
        )

    if limit < 1:
        raise ValueError(
            "Limit must be at least 1."
        )

    # Validate requested restrictions.
    for restriction in restrictions:

        if restriction not in RESTRICTIONS:

            raise ValueError(
                f"Unsupported restriction: {restriction}"
            )

    connection = get_connection()

    try:

        pattern = f"%{keyword}%"

        # Retrieve matching recipes AND all their ingredients.
        # The CTE first identifies matching recipes.
        # The LEFT JOIN then retrieves their complete ingredient lists.

        query = """

            WITH candidates AS (

                SELECT
                    r.recipe_id,
                    r.title,
                    r.quality_flags

                FROM recipes r

                WHERE

                    LOWER(COALESCE(r.title, '')) LIKE ?

                    OR EXISTS (

                        SELECT 1

                        FROM ingredients search_i

                        WHERE search_i.recipe_id = r.recipe_id

                        AND (

                            LOWER(
                                COALESCE(search_i.original_text, '')
                            ) LIKE ?

                            OR LOWER(
                                COALESCE(search_i.normalized_name, '')
                            ) LIKE ?

                        )

                    )

            )

            SELECT

                c.recipe_id,
                c.title,
                c.quality_flags,

                i.position,
                i.original_text

            FROM candidates c

            LEFT JOIN ingredients i

                ON c.recipe_id = i.recipe_id

            ORDER BY
                c.recipe_id,
                i.position

        """

        rows = connection.execute(

            query,

            (pattern, pattern, pattern)

        ).fetchall()

        # -------------------------------------------------
        # GROUP ALL INGREDIENTS BY RECIPE
        # -------------------------------------------------

        candidates = {}

        for row in rows:

            recipe_id = row["recipe_id"]

            if recipe_id not in candidates:

                try:

                    quality_flags = json.loads(
                        row["quality_flags"] or "{}"
                    )

                except (json.JSONDecodeError, TypeError):

                    quality_flags = {}

                candidates[recipe_id] = {

                    "recipe_id": recipe_id,

                    "title": row["title"],

                    "ingredients": [],

                    "quality_flags": quality_flags

                }

            if row["original_text"]:

                candidates[recipe_id][
                    "ingredients"
                ].append(
                    row["original_text"]
                )

        # -------------------------------------------------
        # CLASSIFY CANDIDATE RECIPES
        # -------------------------------------------------

        eligible = []

        excluded = []

        unknown = []

        for recipe in candidates.values():

            ingredients = recipe["ingredients"]

            flags = recipe["quality_flags"]

            # Missing ingredients cannot be considered safe.
            if (

                flags.get(
                    "missing_ingredients",
                    False
                )

                or not ingredients

            ):

                recipe["status"] = "unknown"

                unknown.append(recipe)

                continue

            # Check every original ingredient.
            violations = find_violations(

                ingredients,

                restrictions

            )

            if violations:

                recipe["status"] = "excluded"

                recipe["violations"] = violations

                excluded.append(recipe)

            else:

                recipe["status"] = (
                    "no_listed_conflicts_found"
                )

                eligible.append(recipe)

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        total_candidates = len(candidates)

        classified_count = (

            len(eligible)

            + len(excluded)

            + len(unknown)

        )

        print("\nDATABASE VALIDATION")

        print(
            "Total matching recipes:",
            total_candidates
        )

        print(
            "Classified recipes:",
            classified_count
        )

        assert classified_count == total_candidates, (
            "Classification count mismatch!"
        )

        # -------------------------------------------------
        # RETURN RESULTS
        # -------------------------------------------------

        return {

            "keyword": keyword,

            "restrictions": restrictions,

            "total_candidates": total_candidates,

            "eligible": eligible[:limit],

            "eligible_count": len(eligible),

            "excluded": excluded,

            "excluded_count": len(excluded),

            "unknown": unknown,

            "unknown_count": len(unknown)

        }

    finally:

        connection.close()


# =====================================================
# 7. DISPLAY RESULTS
# =====================================================

def display_results(results):

    print("\n" + "=" * 55)

    print("DIETARY RECIPE FILTER RESULTS")

    print("=" * 55)

    print(
        "Search keyword:",
        results["keyword"]
    )

    print(
        "Restrictions:",
        ", ".join(results["restrictions"])
    )

    print("\nSUMMARY")

    print("-" * 40)

    print(
        "Total candidates:",
        results["total_candidates"]
    )

    print(
        "Eligible candidates:",
        results["eligible_count"]
    )

    print(
        "Excluded candidates:",
        results["excluded_count"]
    )

    print(
        "Unknown candidates:",
        results["unknown_count"]
    )

    # -------------------------------------------------
    # ELIGIBLE RECIPES
    # -------------------------------------------------

    print("\nCOMPATIBLE CANDIDATES")

    print("-" * 40)

    if not results["eligible"]:

        print("No eligible recipes found.")

    for recipe in results["eligible"]:

        print(
            f"\nTitle: {recipe['title']}"
        )

        print(
            f"Recipe ID: {recipe['recipe_id']}"
        )

        print(
            "Status: No listed conflicts found"
        )

    # -------------------------------------------------
    # EXCLUDED RECIPES
    # -------------------------------------------------

    print("\nEXCLUDED CANDIDATES")

    print("-" * 40)

    if not results["excluded"]:

        print("No exclusions found.")

    for recipe in results["excluded"][:10]:

        print(
            f"\nTitle: {recipe['title']}"
        )

        print(
            f"Recipe ID: {recipe['recipe_id']}"
        )

        print("Violation evidence:")

        for violation in recipe["violations"]:

            print(

                f"  Restriction: "
                f"{violation['restriction']}"

            )

            print(

                f"  Matched term: "
                f"{violation['matched_term']}"

            )

            print(

                f"  Original ingredient: "
                f"{violation['original_ingredient']}"

            )

    # -------------------------------------------------
    # UNKNOWN RECIPES
    # -------------------------------------------------

    print("\nUNKNOWN CANDIDATES")

    print("-" * 40)

    if not results["unknown"]:

        print("No unknown candidates.")

    for recipe in results["unknown"][:10]:

        print(
            f"{recipe['title']} | "
            f"{recipe['recipe_id']}"
        )

    print("\n" + "=" * 55)


# =====================================================
# 8. MAIN PROGRAM
# =====================================================

if __name__ == "__main__":

    print("=" * 55)

    print("RECIPE DIETARY FILTER")

    print("=" * 55)

    keyword = input(
        "\nEnter dish or ingredient: "
    ).strip()

    print("\nAvailable restrictions:")

    print("1. dairy")

    print("2. peanut")

    print("3. vegetarian")

    selected = input(

        "\nEnter restrictions separated by commas: "

    ).strip()

    restrictions = [

        item.strip().lower()

        for item in selected.split(",")

        if item.strip()

    ]

    try:

        results = filter_recipes(

            keyword=keyword,

            restrictions=restrictions,

            limit=10

        )

        display_results(results)

    except (ValueError, sqlite3.Error) as error:

        print("\nError:", error)

    except Exception as error:

        print("\nUnexpected error:", error)

        raise
