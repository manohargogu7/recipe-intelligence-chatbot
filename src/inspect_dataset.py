
import json
from pathlib import Path
import gc

# Location of the original JSON files
DATA_DIR = Path("data/raw")

files = [
    "recipes_raw_nosource_ar.json",
    "recipes_raw_nosource_epi.json",
    "recipes_raw_nosource_fn.json"
]


def inspect_file(filename):
    file_path = DATA_DIR / filename

    print("\n" + "=" * 65)
    print(f"FILE: {filename}")
    print("=" * 65)

    if not file_path.exists():
        print("File not found!")
        return

    print(f"File size: {file_path.stat().st_size:,} bytes")

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    print(f"Top-level data type: {type(data).__name__}")

    if isinstance(data, dict):
        print(f"Total recipes: {len(data):,}")

        if not data:
            print("No recipe records found.")
            return

        recipe_id = next(iter(data))
        recipe = data[recipe_id]

    elif isinstance(data, list):
        print(f"Total records: {len(data):,}")

        if not data:
            print("No recipe records found.")
            return

        recipe = data[0]
        recipe_id = recipe.get("id", "ID field not found")

    else:
        print("Unexpected JSON structure.")
        return

    print(f"\nSample Recipe ID: {recipe_id}")
    print(f"Record type: {type(recipe).__name__}")

    if isinstance(recipe, dict):
        print("\nAvailable fields:")

        for key, value in recipe.items():
            print(f"- {key}: {type(value).__name__}")

        print("\nSample recipe details:")

        for key in ["title", "name"]:
            if key in recipe:
                print(f"Title: {str(recipe[key])[:200]}")
                break

        for key in ["ingredients", "instructions", "directions"]:
            if key in recipe:
                value = recipe[key]
                print(f"\n{key}:")

                if isinstance(value, list):
                    print(f"Number of items: {len(value)}")
                    print("First 3 items:", value[:3])
                else:
                    print(str(value)[:500])

    del data
    gc.collect()


if __name__ == "__main__":
    for filename in files:
        inspect_file(filename)
