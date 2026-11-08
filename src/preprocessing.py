
import json
import re
import unicodedata
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "processed" / "recipes.jsonl"

OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "recipes_normalized.jsonl"
)

REPORT_FILE = (
    BASE_DIR / "data" / "processed" / "cleaning_report.json"
)


# Conservative aliases: only merge clearly equivalent names.
INGREDIENT_ALIASES = {
    "scallions": "green onion",
    "spring onions": "green onion",
    "green onions": "green onion",
    "garbanzo beans": "chickpeas",
    "chick peas": "chickpeas",
    "cilantro leaves": "cilantro",
    "coriander leaves": "cilantro",
}


def normalize_text(value):
    """Normalize text for searching without changing original data."""

    if not isinstance(value, str):
        return ""

    value = unicodedata.normalize("NFKC", value)
    value = value.casefold()
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_ingredient(value):
    """Normalize an ingredient name conservatively."""

    normalized = normalize_text(value)

    # Remove surrounding whitespace and common trailing punctuation.
    normalized = normalized.strip(" \t\r\n,;")

    # Apply only explicitly defined aliases.
    normalized = INGREDIENT_ALIASES.get(
        normalized, normalized
    )

    return normalized


def process_recipes():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    total = 0
    missing = Counter()
    empty_ingredients = 0
    invalid_ingredient_items = 0

    print("Starting recipe preprocessing...")

    with open(
        INPUT_FILE, "r", encoding="utf-8"
    ) as source, open(
        OUTPUT_FILE, "w", encoding="utf-8"
    ) as destination:

        for line in source:

            recipe = json.loads(line)

            # Preserve all original fields.
            processed = recipe.copy()

            title = recipe.get("title")
            ingredients = recipe.get("ingredients")
            instructions = recipe.get("instructions")

            # Add normalized title separately.
            processed["normalized_title"] = normalize_text(title)

            # Preserve original ingredient list.
            normalized_ingredients = []

            if isinstance(ingredients, list):

                if not ingredients:
                    empty_ingredients += 1

                for item in ingredients:

                    if isinstance(item, str):
                        normalized = normalize_ingredient(item)

                        if not normalized:
                            invalid_ingredient_items += 1

                        normalized_ingredients.append(normalized)

                    else:
                        # Preserve unsupported item as text,
                        # but do not pretend it was parsed.
                        invalid_ingredient_items += 1
                        normalized_ingredients.append("")

            else:
                missing["ingredients"] += 1

            processed["normalized_ingredients"] = (
                normalized_ingredients
            )

            # Preserve original instructions exactly.
            processed["instructions"] = instructions

            # Add explicit quality flags.
            processed["quality_flags"] = {
                "missing_title": not bool(title),
                "missing_ingredients": (
                    not isinstance(ingredients, list)
                    or len(ingredients) == 0
                ),
                "missing_instructions": (
                    not isinstance(instructions, str)
                    or not instructions.strip()
                )
            }

            for field in ["title", "instructions"]:
                if not recipe.get(field):
                    missing[field] += 1

            destination.write(
                json.dumps(processed, ensure_ascii=False) + "\n"
            )

            total += 1

            if total % 25000 == 0:
                print(f"Processed {total:,} recipes")

    report = {
        "total_recipes_processed": total,
        "missing_fields": dict(missing),
        "empty_ingredient_lists": empty_ingredients,
        "invalid_ingredient_items": invalid_ingredient_items,
        "alias_mappings": INGREDIENT_ALIASES,
        "output_file": "data/processed/recipes_normalized.jsonl"
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("\nPreprocessing completed!")
    print(f"Total recipes processed: {total:,}")
    print(f"Empty ingredient lists: {empty_ingredients}")
    print(f"Invalid ingredient items: {invalid_ingredient_items}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    process_recipes()
