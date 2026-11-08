
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_FILE = BASE_DIR / "database" / "recipe_database.db"

connection = sqlite3.connect(DB_FILE)
connection.execute("PRAGMA foreign_keys = ON")

cursor = connection.cursor()

print("\n========== DATABASE TESTING ==========\n")

# Test 1: Total recipes
cursor.execute("SELECT COUNT(*) FROM recipes")
print("1. Total recipes:", cursor.fetchone()[0])

# Test 2: Total ingredients
cursor.execute("SELECT COUNT(*) FROM ingredients")
print("2. Total ingredient records:", cursor.fetchone()[0])

# Test 3: Sample recipes
print("\n3. Sample recipes:")

cursor.execute("""
    SELECT recipe_id, title
    FROM recipes
    WHERE title IS NOT NULL
    LIMIT 5
""")

for row in cursor.fetchall():
    print(row)

# Test 4: Search recipe by title
print("\n4. Search for recipes containing 'chicken':")

cursor.execute("""
    SELECT recipe_id, title
    FROM recipes
    WHERE normalized_title LIKE ?
    LIMIT 5
""", ("%chicken%",))

for row in cursor.fetchall():
    print(row)

# Test 5: Search by ingredient
print("\n5. Recipes containing garlic:")

cursor.execute("""
    SELECT DISTINCT r.recipe_id, r.title
    FROM recipes r
    JOIN ingredients i
      ON r.recipe_id = i.recipe_id
    WHERE i.normalized_name LIKE ?
    LIMIT 5
""", ("%garlic%",))

for row in cursor.fetchall():
    print(row)

# Test 6: Source-wise recipe counts
print("\n6. Source-wise recipe counts:")

cursor.execute("""
    SELECT source, COUNT(*)
    FROM recipes
    GROUP BY source
""")

for row in cursor.fetchall():
    print(row)

connection.close()

print("\n========== TESTING COMPLETED ==========")
