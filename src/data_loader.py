
import json
from pathlib import Path
from collections import Counter

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

OUTPUT_FILE = PROCESSED_DIR / "recipes.jsonl"
SUMMARY_FILE = PROCESSED_DIR / "dataset_summary.json"

# Original dataset files
DATA_FILES = [
    "recipes_raw_nosource_ar.json",
    "recipes_raw_nosource_epi.json",
    "recipes_raw_nosource_fn.json",
]


def load_and_combine():

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    total_recipes = 0
    source_counts = {}
    missing_fields = Counter()
    duplicate_ids = Counter()

    seen_original_ids = set()

    print("=" * 60)
    print("RECIPE DATA LOADING STARTED")
    print("=" * 60)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as output:

        for filename in DATA_FILES:

            file_path = RAW_DIR / filename

            if not file_path.exists():
                raise FileNotFoundError(
                    f"Dataset file not found: {file_path}"
                )

            source = filename.replace(
                "recipes_raw_nosource_", ""
            ).replace(".json", "")

            print(f"\nLoading: {filename}")

            with open(file_path, "r", encoding="utf-8") as file:
                recipes = json.load(file)

            if not isinstance(recipes, dict):
                raise ValueError(
                    f"Unexpected structure in {filename}. "
                    "Expected a dictionary."
                )

            source_count = 0

            for original_id, recipe in recipes.items():

                if not isinstance(recipe, dict):
                    raise ValueError(
                        f"Invalid recipe record: {original_id}"
                    )

                original_id = str(original_id)

                # Detect IDs repeated across source files
                if original_id in seen_original_ids:
                    duplicate_ids[original_id] += 1

                seen_original_ids.add(original_id)

                # Preserve original recipe fields
                title = recipe.get("title")
                ingredients = recipe.get("ingredients")
                instructions = recipe.get("instructions")
                picture_link = recipe.get("picture_link")

                # Track missing required fields
                if not title:
                    missing_fields["title"] += 1

                if not ingredients:
                    missing_fields["ingredients"] += 1

                if not instructions:
                    missing_fields["instructions"] += 1

                # Create a stable, source-specific ID
                stable_id = f"{source}:{original_id}"

                # Keep original record unchanged
                record = {
                    "recipe_id": stable_id,
                    "original_id": original_id,
                    "source": source,
                    "source_file": filename,
                    "title": title,
                    "ingredients": ingredients,
                    "instructions": instructions,
                    "picture_link": picture_link,
                    "original_record": recipe
                }

                output.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )

                source_count += 1
                total_recipes += 1

            source_counts[source] = source_count

            print(f"Recipes loaded: {source_count:,}")

            del recipes

    # Create validation summary
    summary = {
        "total_recipes": total_recipes,
        "source_counts": source_counts,
        "duplicate_original_ids": sum(duplicate_ids.values()),
        "missing_required_fields": dict(missing_fields),
        "output_file": "data/processed/recipes.jsonl"
    }

    with open(SUMMARY_FILE, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=4)

    print("\n" + "=" * 60)
    print("DATA LOADING COMPLETED")
    print("=" * 60)

    print(f"Total recipes: {total_recipes:,}")
    print(f"Duplicate original IDs: {sum(duplicate_ids.values())}")
    print(f"Missing fields: {dict(missing_fields)}")

    print(f"\nCombined dataset: {OUTPUT_FILE}")
    print(f"Validation report: {SUMMARY_FILE}")


if __name__ == "__main__":
    load_and_combine()
