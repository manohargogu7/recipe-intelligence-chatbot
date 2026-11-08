
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "processed" / "recipes_normalized.jsonl"
DB_FILE = BASE_DIR / "database" / "recipe_database.db"


def create_tables(connection):

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            recipe_id TEXT PRIMARY KEY,
            original_id TEXT NOT NULL,
            source TEXT NOT NULL,
            source_file TEXT NOT NULL,
            title TEXT,
            normalized_title TEXT,
            instructions TEXT,
            picture_link TEXT,
            quality_flags TEXT,
            original_record_json TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            original_text TEXT,
            normalized_name TEXT,
            FOREIGN KEY (recipe_id)
                REFERENCES recipes(recipe_id)
                ON DELETE CASCADE
        )
    """)

    # Indexes for faster searching and filtering.
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_recipe_title
        ON recipes(normalized_title)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ingredient_name
        ON ingredients(normalized_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ingredient_recipe
        ON ingredients(recipe_id)
    """)

    connection.commit()


def load_recipes(connection):

    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    recipe_batch = []
    ingredient_batch = []

    total_recipes = 0
    total_ingredients = 0
    batch_size = 2000

    cursor = connection.cursor()

    print("Loading recipes into SQLite...")

    with open(INPUT_FILE, "r", encoding="utf-8") as file:

        for line in file:

            recipe = json.loads(line)

            recipe_id = recipe["recipe_id"]

            original_record = recipe.get("original_record", {})
            original_ingredients = original_record.get("ingredients")

            normalized_ingredients = recipe.get(
                "normalized_ingredients", []
            )

            flags = json.dumps(
                recipe.get("quality_flags", {}),
                ensure_ascii=False
            )

            original_json = json.dumps(
                original_record,
                ensure_ascii=False
            )

            recipe_batch.append((
                recipe_id,
                recipe["original_id"],
                recipe["source"],
                recipe["source_file"],
                recipe.get("title"),
                recipe.get("normalized_title"),
                recipe.get("instructions"),
                recipe.get("picture_link"),
                flags,
                original_json
            ))

            if isinstance(original_ingredients, list):

                for position, original_item in enumerate(
                    original_ingredients
                ):

                    original_text = (
                        original_item
                        if isinstance(original_item, str)
                        else json.dumps(original_item, ensure_ascii=False)
                    )

                    normalized_name = (
                        normalized_ingredients[position]
                        if position < len(normalized_ingredients)
                        else ""
                    )

                    ingredient_batch.append((
                        recipe_id,
                        position,
                        original_text,
                        normalized_name
                    ))

            total_recipes += 1
            total_ingredients += len(
                original_ingredients
                if isinstance(original_ingredients, list)
                else []
            )

            if total_recipes % batch_size == 0:

                cursor.executemany("""
                    INSERT INTO recipes VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, recipe_batch)

                cursor.executemany("""
                    INSERT INTO ingredients (
                        recipe_id,
                        position,
                        original_text,
                        normalized_name
                    )
                    VALUES (?, ?, ?, ?)
                """, ingredient_batch)

                connection.commit()

                recipe_batch.clear()
                ingredient_batch.clear()

                print(
                    f"Inserted {total_recipes:,} recipes..."
                )

    # Insert remaining records.
    if recipe_batch:

        cursor.executemany("""
            INSERT INTO recipes VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, recipe_batch)

        cursor.executemany("""
            INSERT INTO ingredients (
                recipe_id,
                position,
                original_text,
                normalized_name
            )
            VALUES (?, ?, ?, ?)
        """, ingredient_batch)

        connection.commit()

    return total_recipes, total_ingredients


def validate_database(connection):

    cursor = connection.cursor()

    recipe_count = cursor.execute(
        "SELECT COUNT(*) FROM recipes"
    ).fetchone()[0]

    ingredient_count = cursor.execute(
        "SELECT COUNT(*) FROM ingredients"
    ).fetchone()[0]

    unique_recipe_ids = cursor.execute(
        "SELECT COUNT(DISTINCT recipe_id) FROM recipes"
    ).fetchone()[0]

    foreign_key_errors = cursor.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    print("\nDATABASE VALIDATION")
    print("-" * 45)
    print(f"Recipes: {recipe_count:,}")
    print(f"Ingredients: {ingredient_count:,}")
    print(f"Unique recipe IDs: {unique_recipe_ids:,}")
    print(f"Foreign key errors: {len(foreign_key_errors)}")

    return recipe_count, ingredient_count


def main():

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Create a fresh database for reproducible loading.
    if DB_FILE.exists():
        DB_FILE.unlink()

    connection = sqlite3.connect(DB_FILE)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        create_tables(connection)

        recipes, ingredients = load_recipes(connection)

        validate_database(connection)

        print("\nDATABASE CREATION COMPLETED!")
        print(f"Database location: {DB_FILE}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()
