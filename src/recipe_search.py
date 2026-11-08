
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "database" / "recipe_database.db"


def get_connection():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection



def search_recipes(keyword, limit=10):

    keyword = keyword.strip().casefold()

    if not keyword:
        return []

    connection = get_connection()

    try:
        query = """
            SELECT
                r.recipe_id,
                r.original_id,
                r.title,
                r.source,
                r.instructions,

                CASE
                    WHEN LOWER(COALESCE(r.title, '')) LIKE ?
                    THEN 'title'
                    ELSE 'ingredient'
                END AS match_type,

                (
                    SELECT GROUP_CONCAT(
                        DISTINCT i2.original_text
                    )
                    FROM ingredients i2
                    WHERE i2.recipe_id = r.recipe_id
                    AND (
                        LOWER(i2.original_text) LIKE ?
                        OR LOWER(i2.normalized_name) LIKE ?
                    )
                ) AS matching_ingredients

            FROM recipes r

            WHERE
                LOWER(COALESCE(r.title, '')) LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM ingredients i
                    WHERE i.recipe_id = r.recipe_id
                    AND (
                        LOWER(i.original_text) LIKE ?
                        OR LOWER(i.normalized_name) LIKE ?
                    )
                )

            ORDER BY r.title
            LIMIT ?
        """

        pattern = f"%{keyword}%"

        results = connection.execute(
            query,
            (
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                limit
            )
        ).fetchall()

        return [dict(row) for row in results]

    finally:
        connection.close()





def get_recipe(recipe_id):
    """
    Retrieve a complete recipe using its stable ID.
    """

    connection = get_connection()

    try:
        recipe = connection.execute(
            """
            SELECT *
            FROM recipes
            WHERE recipe_id = ?
            """,
            (recipe_id,)
        ).fetchone()

        if recipe is None:
            return None

        recipe = dict(recipe)

        ingredients = connection.execute(
            """
            SELECT original_text, normalized_name
            FROM ingredients
            WHERE recipe_id = ?
            ORDER BY position
            """,
            (recipe_id,)
        ).fetchall()

        recipe["ingredients"] = [
            dict(row) for row in ingredients
        ]

        return recipe

    finally:
        connection.close()



def display_results(results):

    if not results:
        print("\nNo matching recipes found.")
        return

    print(f"\nFound {len(results)} recipes:\n")

    for index, recipe in enumerate(results, start=1):

        print(f"{index}. {recipe['title']}")
        print(f"   Recipe ID: {recipe['recipe_id']}")
        print(f"   Source: {recipe['source']}")
        print(f"   Match type: {recipe['match_type']}")

        matching = recipe.get("matching_ingredients")

        if matching:
            print(f"   Matching ingredients: {matching}")
        else:
            print("   Matching ingredients: Title match only")

        print("-" * 60)
if __name__ == "__main__":

    print("=" * 50)
    print("RECIPE SEARCH ENGINE")
    print("=" * 50)

    keyword = input("\nEnter a dish or ingredient: ")

    results = search_recipes(keyword)

    display_results(results)